"""
Product Expert System — Ingestion Orchestrator
004_ingestion_orchestrator.py

Bridges extraction pipeline → database writes.
Responsibilities:
  1. Job lifecycle management (queued → processing → completed/failed)
  2. Document dedup via SHA-256 checksums
  3. Model number → product resolution (find-or-create)
  4. Spec conflict detection & severity scoring
  5. Product versioning on spec changes
  6. Spec registry auto-discovery
  7. Document ↔ product linkage
  8. Chunking for RAG retrieval
"""
from __future__ import annotations
import hashlib
import logging
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum

from models import (
    DocType, DocStatus, ProductStatus, ApprovalStatus,
    ConflictSeverity, ConflictResolution, SpecDataType,
    ExtractedSpec, ExtractionResult,
    Product, Document, DocumentChunk, SpecConflict,
    Brand, ProductFamily, SpecRegistryEntry,
    parse_fraction, parse_certifications,
)
from extraction_pipeline import (
    DocumentExtractor, extract_document,
    classify_document, detect_brand, extract_model_numbers,
)

logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================

@dataclass
class IngestionConfig:
    """Tunable parameters for ingestion behavior."""
    # Conflict thresholds — numeric delta (%) that triggers conflict
    numeric_conflict_threshold: float = 0.05      # 5% diff = conflict
    numeric_critical_threshold: float = 0.20      # 20% diff = critical

    # Specs where ANY change is critical (safety/compliance)
    critical_specs: set[str] = field(default_factory=lambda: {
        'voltage_v', 'amperage', 'refrigerant', 'certifications',
        'nsf_ansi_456_certified', 'temp_range_min_c', 'temp_range_max_c',
        'nfpa_compliance', 'intrinsically_safe',
    })

    # Specs where minor formatting diffs should be ignored
    normalize_before_compare: set[str] = field(default_factory=lambda: {
        'compressor_type', 'condenser_type', 'evaporator_type',
        'defrost_type', 'controller_type', 'display_type',
        'exterior_material', 'interior_lighting', 'mounting_type',
    })

    # Max chunk size for RAG (tokens approx)
    chunk_max_tokens: int = 512
    chunk_overlap_tokens: int = 64

    # Auto-approve spec updates from newer doc revisions
    auto_accept_newer_revision: bool = True

    # Minimum extraction confidence to write to product
    min_confidence: float = 0.6

    # Whether to create products for unknown model numbers
    auto_create_products: bool = True


DEFAULT_CONFIG = IngestionConfig()

# ============================================================
# Model Number → Product Family Resolution
# ============================================================

MODEL_FAMILY_PATTERNS: list[tuple[str, dict[str, Any]]] = [
    # ABS Premier Chromatography: ABT-HC-CS-{capacity}
    (r'^ABT-HC-CS-(\d+)$', {
        'brand_code': 'ABS',
        'family_code': 'chromatography_ref',
        'product_line': 'Premier',
        'product_type': 'refrigerator',
        'capacity_group': 1,
    }),
    # ABS Premier Lab: ABT-HC-{capacity}{door}
    (r'^ABT-HC-(\d+)(S|G)$', {
        'brand_code': 'ABS',
        'family_code': 'premier_lab_ref',
        'product_line': 'Premier',
        'product_type': 'refrigerator',
        'capacity_group': 1,
        'door_map': {'S': 'solid', 'G': 'glass'},
        'door_group': 2,
    }),
    # ABS Standard Lab: ABT-HC-{capacity}R
    (r'^ABT-HC-(\d+)R$', {
        'brand_code': 'ABS',
        'family_code': 'standard_lab_ref',
        'product_line': 'Standard',
        'product_type': 'refrigerator',
        'capacity_group': 1,
    }),
    # ABS Pharmacy Premier: PH-ABT-HC-{capacity}{door}
    (r'^PH-ABT-HC-(\d+)(S|G)$', {
        'brand_code': 'ABS',
        'family_code': 'pharmacy_vaccine_ref',
        'product_line': 'Pharmacy Premier',
        'product_type': 'refrigerator',
        'capacity_group': 1,
        'door_map': {'S': 'solid', 'G': 'glass'},
        'door_group': 2,
    }),
    # ABS Pharmacy NSF Undercounter: PH-ABT-NSF-UCFS-{code}
    (r'^PH-ABT-NSF-UCFS-(\w+)$', {
        'brand_code': 'ABS',
        'family_code': 'pharmacy_nsf_ref',
        'product_line': 'Pharmacy NSF',
        'product_type': 'refrigerator',
        'nsf_ansi_456': True,
    }),
    # ABS Blood Bank: ABT-HC-BBR-{capacity}
    (r'^ABT-HC-BBR-(\d+)$', {
        'brand_code': 'ABS',
        'family_code': 'blood_bank_ref',
        'product_line': 'Blood Bank',
        'product_type': 'refrigerator',
        'capacity_group': 1,
    }),
    # ABS Flammable: ABT-HC-FRP-{capacity}
    (r'^ABT-HC-FRP-(\d+)$', {
        'brand_code': 'ABS',
        'family_code': 'flammable_storage_ref',
        'product_line': 'Flammable Storage',
        'product_type': 'refrigerator',
        'capacity_group': 1,
    }),
    # LABRepCo Ultra Touch Manual Defrost Freezer: LHT-{cap}-FMP
    (r'^LHT-(\d+)-FMP$', {
        'brand_code': 'LABRepCo',
        'family_code': 'manual_defrost_freezer',
        'product_line': 'Ultra Touch',
        'product_type': 'freezer',
        'controller_tier': 'ultra_touch',
        'capacity_group': 1,
    }),
    # LABRepCo FUTURA Auto Defrost Freezer: LHT-{cap}-FASS
    (r'^LHT-(\d+)-FASS$', {
        'brand_code': 'LABRepCo',
        'family_code': 'auto_defrost_freezer',
        'product_line': 'Ultra Touch FUTURA',
        'product_type': 'freezer',
        'controller_tier': 'ultra_touch',
        'capacity_group': 1,
    }),
    # LABRepCo FUTURA Manual Defrost Freezer: LHT-{cap}-FM
    (r'^LHT-(\d+)-FM$', {
        'brand_code': 'LABRepCo',
        'family_code': 'manual_defrost_freezer',
        'product_line': 'FUTURA',
        'product_type': 'freezer',
        'controller_tier': 'ultra_touch',
        'capacity_group': 1,
    }),
    # LABRepCo Ultra Touch Flammable Refrigerator: LHT-{cap}-RFP
    (r'^LHT-(\d+)-RFP$', {
        'brand_code': 'LABRepCo',
        'family_code': 'flammable_storage_ref',
        'product_line': 'Ultra Touch',
        'product_type': 'refrigerator',
        'controller_tier': 'ultra_touch',
        'capacity_group': 1,
    }),
    # LABRepCo Precision Freezer: LPVT-{cap}-FA
    (r'^LPVT-(\d+)-FA$', {
        'brand_code': 'LABRepCo',
        'family_code': 'precision_freezer',
        'product_line': 'Precision',
        'product_type': 'freezer',
        'controller_tier': 'precision',
        'capacity_group': 1,
    }),
    # LABRepCo Refrigerator: LHT-{cap}-RFG / RFGS
    (r'^LHT-(\d+)-RFG(S?)$', {
        'brand_code': 'LABRepCo',
        'family_code': 'premier_lab_ref',
        'product_line': 'Ultra Touch',
        'product_type': 'refrigerator',
        'controller_tier': 'ultra_touch',
        'capacity_group': 1,
    }),
    # Corepoint: NSBR492WSxCR/0
    (r'^NSBR(\d+)(\w+)/(\d)$', {
        'brand_code': 'Corepoint',
        'family_code': 'premier_lab_ref',
        'product_line': 'Corepoint',
        'product_type': 'refrigerator',
    }),
    # Corepoint new format: CP-{type}-{cap}-{door}-HC
    (r'^CP-(\w+)-(\d+)-(\w)-HC$', {
        'brand_code': 'Corepoint',
        'family_code': 'premier_lab_ref',
        'product_line': 'Corepoint',
        'product_type': 'refrigerator',
        'capacity_group': 2,
        'door_map': {'S': 'solid', 'G': 'glass'},
        'door_group': 3,
    }),
    # Celsius: CEL-HC-BB-{cap}
    (r'^CEL-HC-BB-(\d+)$', {
        'brand_code': 'Celsius',
        'family_code': 'blood_bank_ref',
        'product_line': 'Celsius',
        'product_type': 'refrigerator',
        'capacity_group': 1,
    }),
    # Cryogenic dewars: V-{cap}
    (r'^V-(\d+)$', {
        'brand_code': 'CBS',
        'family_code': 'cryo_dewar',
        'product_line': 'CryoSafe',
        'product_type': 'cryogenic',
    }),
]


@dataclass
class ModelResolution:
    """Result of resolving a model number to product metadata."""
    model_number: str
    brand_code: str
    family_code: str
    product_line: Optional[str] = None
    product_type: str = 'refrigerator'
    controller_tier: Optional[str] = None
    inferred_capacity: Optional[float] = None
    inferred_door_type: Optional[str] = None
    nsf_ansi_456: bool = False
    matched_pattern: Optional[str] = None


def resolve_model_number(model: str) -> Optional[ModelResolution]:
    """Match a model number against known patterns to infer product metadata."""
    model = model.strip()
    for pattern, meta in MODEL_FAMILY_PATTERNS:
        m = re.match(pattern, model)
        if m:
            res = ModelResolution(
                model_number=model,
                brand_code=meta['brand_code'],
                family_code=meta['family_code'],
                product_line=meta.get('product_line'),
                product_type=meta.get('product_type', 'refrigerator'),
                controller_tier=meta.get('controller_tier'),
                nsf_ansi_456=meta.get('nsf_ansi_456', False),
                matched_pattern=pattern,
            )
            # Extract capacity from regex group
            cap_grp = meta.get('capacity_group')
            if cap_grp and cap_grp <= len(m.groups()):
                try:
                    res.inferred_capacity = float(m.group(cap_grp))
                except (ValueError, TypeError):
                    pass
            # Extract door type from regex group
            door_grp = meta.get('door_group')
            door_map = meta.get('door_map', {})
            if door_grp and door_grp <= len(m.groups()):
                code = m.group(door_grp)
                res.inferred_door_type = door_map.get(code, code.lower())
            return res
    return None


# ============================================================
# Spec Conflict Detection
# ============================================================

def normalize_spec_value(val: Any) -> str:
    """Normalize a spec value for comparison."""
    if val is None:
        return ''
    s = str(val).strip().lower()
    # Remove extra whitespace
    s = re.sub(r'\s+', ' ', s)
    # Normalize common abbreviations
    s = s.replace('non-applicable', 'n/a')
    s = s.replace('non applicable', 'n/a')
    s = s.replace('not applicable', 'n/a')
    return s


def detect_conflict(
    spec_name: str,
    existing_val: Any,
    new_val: Any,
    config: IngestionConfig = DEFAULT_CONFIG,
) -> Optional[tuple[ConflictSeverity, str]]:
    """
    Compare existing vs new spec value. Returns (severity, reason) if conflict,
    or None if values are equivalent.
    """
    if existing_val is None or new_val is None:
        return None  # Missing = no conflict, just fill

    e_norm = normalize_spec_value(existing_val)
    n_norm = normalize_spec_value(new_val)

    # Exact match after normalization
    if e_norm == n_norm:
        return None

    # For normalized-before-compare specs, be lenient
    if spec_name in config.normalize_before_compare:
        # Strip underscores, hyphens, extra words
        e_clean = re.sub(r'[\s_\-]+', '', e_norm)
        n_clean = re.sub(r'[\s_\-]+', '', n_norm)
        if e_clean == n_clean:
            return None

    # Numeric comparison with tolerance
    try:
        e_num = float(existing_val)
        n_num = float(new_val)
        if e_num == 0 and n_num == 0:
            return None
        denom = max(abs(e_num), abs(n_num), 1e-9)
        delta_pct = abs(e_num - n_num) / denom

        if delta_pct <= config.numeric_conflict_threshold:
            return None  # Within tolerance

        if spec_name in config.critical_specs:
            return (ConflictSeverity.CRITICAL,
                    f'{spec_name}: {existing_val} → {new_val} (Δ{delta_pct:.1%}, critical spec)')

        if delta_pct >= config.numeric_critical_threshold:
            return (ConflictSeverity.HIGH,
                    f'{spec_name}: {existing_val} → {new_val} (Δ{delta_pct:.1%})')

        return (ConflictSeverity.MEDIUM,
                f'{spec_name}: {existing_val} → {new_val} (Δ{delta_pct:.1%})')
    except (ValueError, TypeError):
        pass

    # Non-numeric mismatch
    if spec_name in config.critical_specs:
        return (ConflictSeverity.CRITICAL,
                f'{spec_name}: "{existing_val}" → "{new_val}" (critical spec)')

    return (ConflictSeverity.MEDIUM,
            f'{spec_name}: "{existing_val}" → "{new_val}"')


# ============================================================
# Document Revision Comparison
# ============================================================

REVISION_PATTERN = re.compile(
    r'Rev[_.\s]*(\d{2})[./](\d{2})[./](\d{2,4})', re.IGNORECASE
)

def parse_revision_date(rev: Optional[str]) -> Optional[date]:
    """Parse revision strings like 'Rev_03.18.25' or 'Rev_07232025' into dates."""
    if not rev:
        return None
    m = REVISION_PATTERN.search(rev)
    if m:
        mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yy < 100:
            yy += 2000
        try:
            return date(yy, mm, dd)
        except ValueError:
            return None
    # Try MMDDYYYY format: Rev_07232025
    m2 = re.search(r'Rev[_.\s]*(\d{2})(\d{2})(\d{4})', rev, re.IGNORECASE)
    if m2:
        try:
            return date(int(m2.group(3)), int(m2.group(1)), int(m2.group(2)))
        except ValueError:
            return None
    return None


def is_newer_revision(new_rev: Optional[str], existing_rev: Optional[str]) -> bool:
    """Returns True if new_rev is strictly newer than existing_rev."""
    new_d = parse_revision_date(new_rev)
    old_d = parse_revision_date(existing_rev)
    if new_d and old_d:
        return new_d > old_d
    if new_d and not old_d:
        return True  # New has a date, old doesn't — assume newer
    return False


# ============================================================
# Text Chunking for RAG
# ============================================================

# Section headers that mark natural chunk boundaries
SECTION_HEADERS = [
    'GENERAL DESCRIPTION', 'PRODUCT DESCRIPTION',
    'REFRIGERATION SYSTEM', 'REFRIGERATION',
    'CONTROLLER', 'CONTROLLER TECHNOLOGY', 'CONTROLLER & MONITORING',
    'DIMENSIONS', 'EXTERIOR DIMENSIONS', 'INTERIOR DIMENSIONS',
    'ELECTRICAL', 'FACILITY ELECTRICAL',
    'CERTIFICATIONS', 'AGENCY LISTING',
    'PERFORMANCE', 'TEMPERATURE PERFORMANCE',
    'WARRANTY', 'ALARMS', 'ALARM MANAGEMENT',
    'CONSTRUCTION', 'SHELVING', 'DOOR',
    'ACCESSORIES', 'OPTIONS',
    'INSTALLATION', 'OPERATIONAL ENVIRONMENT',
    'FEATURES', 'STANDARD FEATURES',
    'PHARMACY', 'VACCINE',
]


def chunk_document(
    text: str,
    doc_type: DocType,
    max_tokens: int = 512,
    overlap: int = 64,
) -> list[dict[str, Any]]:
    """
    Split document text into retrieval-ready chunks.
    Uses section headers as natural boundaries when possible.
    """
    if not text or not text.strip():
        return []

    chunks = []

    # Try section-based chunking first
    sections = _split_by_sections(text)

    if len(sections) > 1:
        for sec_title, sec_text in sections:
            # If section too large, sub-chunk it
            if _estimate_tokens(sec_text) > max_tokens:
                sub_chunks = _split_by_size(sec_text, max_tokens, overlap)
                for i, sc in enumerate(sub_chunks):
                    chunks.append({
                        'content': sc,
                        'section_title': sec_title,
                        'chunk_type': _classify_chunk(sec_title, sc, doc_type),
                        'token_count': _estimate_tokens(sc),
                    })
            else:
                chunks.append({
                    'content': sec_text,
                    'section_title': sec_title,
                    'chunk_type': _classify_chunk(sec_title, sec_text, doc_type),
                    'token_count': _estimate_tokens(sec_text),
                })
    else:
        # No clear sections — chunk by size
        raw_chunks = _split_by_size(text, max_tokens, overlap)
        for rc in raw_chunks:
            chunks.append({
                'content': rc,
                'section_title': None,
                'chunk_type': _classify_chunk(None, rc, doc_type),
                'token_count': _estimate_tokens(rc),
            })

    # Assign indexes
    for i, c in enumerate(chunks):
        c['chunk_index'] = i

    return chunks


def _split_by_sections(text: str) -> list[tuple[Optional[str], str]]:
    """Split text into (section_title, section_body) tuples."""
    pattern = '|'.join(re.escape(h) for h in SECTION_HEADERS)
    header_re = re.compile(rf'^[\s]*({pattern})[\s:]*$', re.IGNORECASE | re.MULTILINE)

    matches = list(header_re.finditer(text))
    if not matches:
        return [(None, text)]

    sections = []
    # Content before first header
    if matches[0].start() > 50:
        sections.append(('Preamble', text[:matches[0].start()].strip()))

    for i, m in enumerate(matches):
        title = m.group(1).strip().title()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((title, body))

    return sections


def _split_by_size(text: str, max_tokens: int, overlap: int) -> list[str]:
    """Split text into size-limited chunks with overlap."""
    # Rough: 1 token ≈ 4 chars
    max_chars = max_tokens * 4
    overlap_chars = overlap * 4

    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        # Try to break at paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind('\n\n', start + max_chars // 2, end)
            if para_break > start:
                end = para_break
            else:
                # Look for sentence break
                sent_break = text.rfind('. ', start + max_chars // 2, end)
                if sent_break > start:
                    end = sent_break + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap_chars

    return chunks


def _classify_chunk(
    section: Optional[str], content: str, doc_type: DocType
) -> str:
    """Classify a chunk by its content type for retrieval filtering."""
    if section:
        s = section.upper()
        if 'DIMENSION' in s:
            return 'dimensional'
        if 'PERFORMANCE' in s or 'TEMPERATURE' in s:
            return 'performance_data'
        if 'DESCRIPTION' in s:
            return 'description'
        if any(x in s for x in ['CERTIFICATION', 'AGENCY', 'LISTING']):
            return 'spec_block'

    c = content.upper()
    if re.search(r'\d+[\s"]\s*[xX×]\s*\d+', c):
        return 'dimensional'
    if any(x in c for x in ['UNIFORMITY', 'STABILITY', 'PROBE']):
        return 'performance_data'
    if re.search(r'(Cu\.?\s*Ft|Defrost|Amps|R\d{3})', c):
        return 'spec_block'

    return 'text'


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate (1 token ≈ 4 chars)."""
    return max(1, len(text) // 4)


# ============================================================
# Spec-to-Column Mapping (canonical_name → Product field)
# ============================================================

# Fixed columns on the products table (fast queries, indexed)
PRODUCT_FIXED_COLUMNS: dict[str, str] = {
    'storage_capacity_cuft': 'storage_capacity_cuft',
    'temp_range_min_c': 'temp_range_min_c',
    'temp_range_max_c': 'temp_range_max_c',
    'door_count': 'door_count',
    'door_type': 'door_type',
    'shelf_count': 'shelf_count',
    'refrigerant': 'refrigerant',
    'voltage_v': 'voltage_v',
    'amperage': 'amperage',
    'product_weight_lbs': 'product_weight_lbs',
    'ext_width_in': 'ext_width_in',
    'ext_depth_in': 'ext_depth_in',
    'ext_height_in': 'ext_height_in',
}

# Everything else goes into specs JSONB
# No explicit mapping needed — canonical_name becomes the key


# ============================================================
# Database Abstraction Layer (Repository Pattern)
# ============================================================

class ProductRepository:
    """
    Abstract DB access. In production, backed by asyncpg or SQLAlchemy.
    Here we define the interface; implementations are swappable.
    """

    async def get_document_by_checksum(self, checksum: str) -> Optional[Document]:
        raise NotImplementedError

    async def create_document(self, doc: Document) -> Document:
        raise NotImplementedError

    async def update_document_status(self, doc_id: UUID, status: DocStatus,
                                      log_entry: Optional[dict] = None) -> None:
        raise NotImplementedError

    async def get_product_by_model(self, model_number: str) -> Optional[Product]:
        raise NotImplementedError

    async def create_product(self, product: Product) -> Product:
        raise NotImplementedError

    async def update_product(self, product: Product) -> Product:
        raise NotImplementedError

    async def get_brand_by_code(self, code: str) -> Optional[Brand]:
        raise NotImplementedError

    async def get_family_by_code(self, code: str) -> Optional[ProductFamily]:
        raise NotImplementedError

    async def create_spec_conflict(self, conflict: SpecConflict) -> SpecConflict:
        raise NotImplementedError

    async def link_document_product(self, doc_id: UUID, product_id: UUID,
                                     relevance: str, extracted_specs: dict) -> None:
        raise NotImplementedError

    async def create_chunks(self, chunks: list[DocumentChunk]) -> None:
        raise NotImplementedError

    async def register_spec(self, entry: SpecRegistryEntry) -> SpecRegistryEntry:
        raise NotImplementedError

    async def get_spec_registry(self) -> dict[str, SpecRegistryEntry]:
        raise NotImplementedError

    async def create_ingestion_job(self, job: dict) -> UUID:
        raise NotImplementedError

    async def update_ingestion_job(self, job_id: UUID, updates: dict) -> None:
        raise NotImplementedError


# ============================================================
# In-Memory Repository (for testing / local dev)
# ============================================================

class InMemoryRepository(ProductRepository):
    """In-memory implementation for testing without a database."""

    def __init__(self):
        self.documents: dict[UUID, Document] = {}
        self.products: dict[UUID, Product] = {}
        self.brands: dict[str, Brand] = {}
        self.families: dict[str, ProductFamily] = {}
        self.conflicts: list[SpecConflict] = []
        self.doc_product_links: list[dict] = []
        self.chunks: list[DocumentChunk] = []
        self.spec_registry: dict[str, SpecRegistryEntry] = {}
        self.jobs: dict[UUID, dict] = {}
        self._checksum_index: dict[str, UUID] = {}
        self._model_index: dict[str, UUID] = {}

    async def get_document_by_checksum(self, checksum: str) -> Optional[Document]:
        doc_id = self._checksum_index.get(checksum)
        return self.documents.get(doc_id) if doc_id else None

    async def create_document(self, doc: Document) -> Document:
        self.documents[doc.id] = doc
        self._checksum_index[doc.checksum_sha256] = doc.id
        return doc

    async def update_document_status(self, doc_id: UUID, status: DocStatus,
                                      log_entry: Optional[dict] = None) -> None:
        if doc_id in self.documents:
            self.documents[doc_id].status = status
            if log_entry:
                self.documents[doc_id].processing_log.append(log_entry)

    async def get_product_by_model(self, model_number: str) -> Optional[Product]:
        pid = self._model_index.get(model_number)
        return self.products.get(pid) if pid else None

    async def create_product(self, product: Product) -> Product:
        self.products[product.id] = product
        self._model_index[product.model_number] = product.id
        return product

    async def update_product(self, product: Product) -> Product:
        self.products[product.id] = product
        return product

    async def get_brand_by_code(self, code: str) -> Optional[Brand]:
        return self.brands.get(code)

    async def get_family_by_code(self, code: str) -> Optional[ProductFamily]:
        return self.families.get(code)

    async def create_spec_conflict(self, conflict: SpecConflict) -> SpecConflict:
        self.conflicts.append(conflict)
        return conflict

    async def link_document_product(self, doc_id: UUID, product_id: UUID,
                                     relevance: str, extracted_specs: dict) -> None:
        self.doc_product_links.append({
            'document_id': doc_id,
            'product_id': product_id,
            'relevance': relevance,
            'extracted_specs': extracted_specs,
        })

    async def create_chunks(self, chunks: list[DocumentChunk]) -> None:
        self.chunks.extend(chunks)

    async def register_spec(self, entry: SpecRegistryEntry) -> SpecRegistryEntry:
        self.spec_registry[entry.canonical_name] = entry
        return entry

    async def get_spec_registry(self) -> dict[str, SpecRegistryEntry]:
        return dict(self.spec_registry)

    async def create_ingestion_job(self, job: dict) -> UUID:
        jid = uuid4()
        self.jobs[jid] = {**job, 'id': jid}
        return jid

    async def update_ingestion_job(self, job_id: UUID, updates: dict) -> None:
        if job_id in self.jobs:
            self.jobs[job_id].update(updates)


# ============================================================
# Main Ingestion Orchestrator
# ============================================================

@dataclass
class IngestionStats:
    """Tracks stats for a single ingestion job."""
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    new_products: int = 0
    updated_products: int = 0
    new_specs_discovered: int = 0
    conflicts_found: int = 0
    chunks_created: int = 0
    skipped_duplicate: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class IngestionOrchestrator:
    """
    Main orchestrator that drives the full ingestion pipeline:
      file bytes → extraction → conflict check → DB write → chunking
    """

    def __init__(
        self,
        repo: ProductRepository,
        config: IngestionConfig = DEFAULT_CONFIG,
        extractor: Optional[DocumentExtractor] = None,
    ):
        self.repo = repo
        self.config = config
        self.extractor = extractor or DocumentExtractor()

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    async def ingest_batch(
        self,
        files: list[dict[str, Any]],
        submitted_by: str = 'system',
        metadata: Optional[dict] = None,
    ) -> tuple[UUID, IngestionStats]:
        """
        Ingest a batch of files.

        Args:
            files: list of dicts with keys:
                   'filename': str, 'content': bytes | str,
                   'mime_type': str (optional)
            submitted_by: user ID
            metadata: optional job metadata

        Returns:
            (job_id, stats)
        """
        stats = IngestionStats(total_files=len(files))

        job_id = await self.repo.create_ingestion_job({
            'status': 'processing',
            'total_files': len(files),
            'submitted_by': submitted_by,
            'metadata': metadata or {},
            'started_at': datetime.now(timezone.utc).isoformat(),
        })

        for file_info in files:
            try:
                await self._ingest_single_file(file_info, stats)
                stats.processed_files += 1
            except Exception as e:
                stats.failed_files += 1
                err = f"Failed to ingest {file_info.get('filename', '?')}: {e}"
                stats.errors.append(err)
                logger.exception(err)

        # Finalize job
        final_status = 'completed' if stats.failed_files == 0 else (
            'failed' if stats.processed_files == 0 else 'completed'
        )
        await self.repo.update_ingestion_job(job_id, {
            'status': final_status,
            'processed_files': stats.processed_files,
            'failed_files': stats.failed_files,
            'new_products': stats.new_products,
            'updated_products': stats.updated_products,
            'new_specs_discovered': stats.new_specs_discovered,
            'conflicts_found': stats.conflicts_found,
            'completed_at': datetime.now(timezone.utc).isoformat(),
        })

        return job_id, stats

    async def ingest_single(
        self,
        filename: str,
        content: bytes | str,
        mime_type: str = 'application/pdf',
    ) -> tuple[ExtractionResult, IngestionStats]:
        """Convenience: ingest one file directly."""
        stats = IngestionStats(total_files=1)
        file_info = {
            'filename': filename,
            'content': content,
            'mime_type': mime_type,
        }
        await self._ingest_single_file(file_info, stats)
        stats.processed_files = 1
        # Return the extraction result for inspection
        text = content if isinstance(content, str) else content.decode('utf-8', errors='replace')
        result = self.extractor.extract(text, filename)
        return result, stats

    # ----------------------------------------------------------
    # Internal Pipeline
    # ----------------------------------------------------------

    async def _ingest_single_file(
        self, file_info: dict, stats: IngestionStats
    ) -> None:
        filename = file_info.get('filename', 'unknown')
        content = file_info['content']
        mime_type = file_info.get('mime_type', 'application/octet-stream')

        # --- Step 1: Compute checksum & dedup ---
        raw_bytes = content if isinstance(content, bytes) else content.encode('utf-8')
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        existing_doc = await self.repo.get_document_by_checksum(checksum)
        if existing_doc:
            stats.skipped_duplicate += 1
            stats.warnings.append(f"Duplicate skipped: {filename} (matches {existing_doc.filename})")
            logger.info(f"Skipping duplicate: {filename}")
            return

        # --- Step 2: Extract text (in production: PDF→text via PyMuPDF) ---
        text = content if isinstance(content, str) else content.decode('utf-8', errors='replace')

        # --- Step 3: Run extraction pipeline ---
        extraction = self.extractor.extract(text, filename, raw_bytes)

        # --- Step 4: Create document record ---
        doc = Document(
            filename=filename,
            doc_type=extraction.doc_type,
            mime_type=mime_type,
            source_uri=f'ingestion://{filename}',
            checksum_sha256=checksum,
            file_size_bytes=len(raw_bytes),
            extracted_text=text[:50000],  # Cap stored text
            status=DocStatus.PROCESSING,
            metadata={'extraction_time_ms': extraction.extraction_time_ms},
        )
        doc = await self.repo.create_document(doc)

        # --- Step 5: Resolve model numbers → products ---
        if not extraction.model_numbers:
            stats.warnings.append(f"No model numbers found in {filename}")
            await self.repo.update_document_status(
                doc.id, DocStatus.PROCESSED,
                {'stage': 'model_resolution', 'status': 'no_models', 'timestamp': _now()})
            # Still chunk for RAG even without product linkage
            await self._create_chunks(doc, text, extraction)
            stats.chunks_created += 1
            return

        for model_num in extraction.model_numbers:
            await self._process_model(
                model_num, extraction, doc, stats
            )

        # --- Step 6: Chunk document for RAG ---
        await self._create_chunks(doc, text, extraction)

        # --- Step 7: Handle newly discovered specs ---
        for spec_name in self.extractor.newly_discovered_specs:
            await self._register_new_spec(spec_name, stats)
        self.extractor.newly_discovered_specs.clear()

        # --- Step 8: Mark document as processed ---
        await self.repo.update_document_status(
            doc.id, DocStatus.PROCESSED,
            {'stage': 'complete', 'status': 'ok',
             'models': extraction.model_numbers,
             'specs_count': len(extraction.specs),
             'timestamp': _now()})

    async def _process_model(
        self,
        model_num: str,
        extraction: ExtractionResult,
        doc: Document,
        stats: IngestionStats,
    ) -> None:
        """Resolve a single model number and update/create product."""

        # --- Resolve model metadata ---
        resolution = resolve_model_number(model_num)

        # --- Find or create product ---
        product = await self.repo.get_product_by_model(model_num)

        if product is None:
            if not self.config.auto_create_products:
                stats.warnings.append(f"Unknown model {model_num}, auto-create disabled")
                return

            product = await self._create_product(
                model_num, resolution, extraction, doc, stats
            )
            stats.new_products += 1
        else:
            await self._update_product(
                product, extraction, doc, stats
            )
            stats.updated_products += 1

        # --- Link document ↔ product ---
        extracted_specs_dict = {
            s.canonical_name: {
                'raw': s.raw_value,
                'parsed': s.parsed_value,
                'confidence': s.confidence,
            }
            for s in extraction.specs if s.canonical_name
        }
        await self.repo.link_document_product(
            doc.id, product.id, 'primary', extracted_specs_dict
        )

    async def _create_product(
        self,
        model_num: str,
        resolution: Optional[ModelResolution],
        extraction: ExtractionResult,
        doc: Document,
        stats: IngestionStats,
    ) -> Product:
        """Create a new product from extraction results."""

        # Resolve brand and family IDs
        brand_code = resolution.brand_code if resolution else (extraction.brand_code or 'ABS')
        family_code = resolution.family_code if resolution else 'premier_lab_ref'

        brand = await self.repo.get_brand_by_code(brand_code)
        family = await self.repo.get_family_by_code(family_code)

        # Build product from extracted specs
        product = Product(
            model_number=model_num,
            brand_id=brand.id if brand else uuid4(),
            family_id=family.id if family else uuid4(),
            product_line=resolution.product_line if resolution else None,
            controller_tier=resolution.controller_tier if resolution else None,
            status=ProductStatus.ACTIVE,
            certifications=extraction.certifications,
            revision=self._find_revision(extraction),
        )

        # Apply fixed columns and dynamic specs
        self._apply_specs_to_product(product, extraction.specs)

        # Apply inferred values from model number pattern
        if resolution:
            if resolution.inferred_capacity and not product.storage_capacity_cuft:
                product.storage_capacity_cuft = resolution.inferred_capacity
            if resolution.inferred_door_type and not product.door_type:
                product.door_type = resolution.inferred_door_type

        product = await self.repo.create_product(product)
        logger.info(f"Created product: {model_num} (family={family_code})")
        return product

    async def _update_product(
        self,
        product: Product,
        extraction: ExtractionResult,
        doc: Document,
        stats: IngestionStats,
    ) -> None:
        """Update existing product with new extraction, detecting conflicts."""

        new_revision = self._find_revision(extraction)
        is_newer = is_newer_revision(new_revision, product.revision)

        changes_made = False
        specs_to_apply = extraction.specs

        for spec in specs_to_apply:
            if not spec.canonical_name or spec.canonical_name.startswith('_unknown_'):
                continue
            if spec.confidence < self.config.min_confidence:
                continue

            new_val = spec.parsed_value
            existing_val = self._get_product_spec_value(product, spec.canonical_name)

            # If product doesn't have this spec yet, just apply it
            if existing_val is None:
                self._set_product_spec_value(product, spec.canonical_name, new_val)
                changes_made = True
                continue

            # Check for conflict
            conflict = detect_conflict(
                spec.canonical_name, existing_val, new_val, self.config
            )

            if conflict is None:
                continue  # Values match, nothing to do

            severity, reason = conflict
            stats.conflicts_found += 1

            # Auto-accept if newer revision and config allows
            if is_newer and self.config.auto_accept_newer_revision:
                self._set_product_spec_value(product, spec.canonical_name, new_val)
                changes_made = True
                # Still log the conflict for audit trail
                await self.repo.create_spec_conflict(SpecConflict(
                    product_id=product.id,
                    spec_name=spec.canonical_name,
                    existing_value=str(existing_val),
                    new_value=str(new_val),
                    source_doc_id=doc.id,
                    severity=severity,
                    resolution=ConflictResolution.ACCEPT_NEW,
                ))
                logger.info(f"Auto-accepted (newer rev): {reason}")
            elif severity in (ConflictSeverity.CRITICAL, ConflictSeverity.HIGH):
                # Flag for human review, don't auto-apply
                await self.repo.create_spec_conflict(SpecConflict(
                    product_id=product.id,
                    spec_name=spec.canonical_name,
                    existing_value=str(existing_val),
                    new_value=str(new_val),
                    source_doc_id=doc.id,
                    severity=severity,
                    resolution=ConflictResolution.PENDING,
                ))
                stats.warnings.append(f"Conflict flagged: {reason}")
                logger.warning(f"Conflict flagged: {reason}")
            else:
                # Medium/Low — auto-accept from newer, otherwise flag
                await self.repo.create_spec_conflict(SpecConflict(
                    product_id=product.id,
                    spec_name=spec.canonical_name,
                    existing_value=str(existing_val),
                    new_value=str(new_val),
                    source_doc_id=doc.id,
                    severity=severity,
                    resolution=ConflictResolution.PENDING,
                ))

        # Update certifications (union)
        if extraction.certifications:
            merged = sorted(set(product.certifications + extraction.certifications))
            if merged != product.certifications:
                product.certifications = merged
                changes_made = True

        # Update revision if newer
        if is_newer and new_revision:
            product.revision = new_revision
            changes_made = True

        if changes_made:
            product.version += 1
            product = await self.repo.update_product(product)
            logger.info(f"Updated product: {product.model_number} v{product.version}")

    # ----------------------------------------------------------
    # Spec Value Helpers
    # ----------------------------------------------------------

    def _get_product_spec_value(self, product: Product, spec_name: str) -> Any:
        """Get a spec value from fixed columns or dynamic specs."""
        if spec_name in PRODUCT_FIXED_COLUMNS:
            return getattr(product, PRODUCT_FIXED_COLUMNS[spec_name], None)
        return product.specs.get(spec_name)

    def _set_product_spec_value(self, product: Product, spec_name: str, value: Any) -> None:
        """Set a spec value to fixed column or dynamic specs."""
        if spec_name in PRODUCT_FIXED_COLUMNS:
            col = PRODUCT_FIXED_COLUMNS[spec_name]
            setattr(product, col, value)
        else:
            product.specs[spec_name] = value

    def _apply_specs_to_product(self, product: Product, specs: list[ExtractedSpec]) -> None:
        """Apply all extracted specs to a product."""
        for spec in specs:
            if not spec.canonical_name:
                continue
            if spec.canonical_name.startswith('_unknown_'):
                # Store unknowns in specs for later review
                product.specs[spec.canonical_name] = spec.parsed_value
                continue
            if spec.confidence < self.config.min_confidence:
                continue
            self._set_product_spec_value(product, spec.canonical_name, spec.parsed_value)

    def _find_revision(self, extraction: ExtractionResult) -> Optional[str]:
        """Find revision string from extracted specs."""
        for s in extraction.specs:
            if s.canonical_name in ('revision', '_unknown_revision'):
                return str(s.parsed_value)
        # Also check raw text for revision pattern
        if extraction.raw_text:
            m = REVISION_PATTERN.search(extraction.raw_text)
            if m:
                return m.group(0)
        return None

    # ----------------------------------------------------------
    # RAG Chunking
    # ----------------------------------------------------------

    async def _create_chunks(
        self,
        doc: Document,
        text: str,
        extraction: ExtractionResult,
    ) -> None:
        """Create document chunks for RAG retrieval."""
        raw_chunks = chunk_document(
            text, extraction.doc_type,
            max_tokens=self.config.chunk_max_tokens,
            overlap=self.config.chunk_overlap_tokens,
        )

        # Resolve product IDs for chunk tagging
        product_ids = []
        for model in extraction.model_numbers:
            p = await self.repo.get_product_by_model(model)
            if p:
                product_ids.append(p.id)

        # Detect which specs are mentioned in each chunk
        spec_names_set = {s.canonical_name for s in extraction.specs if s.canonical_name}

        chunks = []
        for rc in raw_chunks:
            # Find spec names mentioned in this chunk
            chunk_specs = []
            for sn in spec_names_set:
                # Check if the display-friendly version appears
                readable = sn.replace('_', ' ')
                if readable in rc['content'].lower() or sn in rc['content'].lower():
                    chunk_specs.append(sn)

            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=rc['chunk_index'],
                content=rc['content'],
                chunk_type=rc['chunk_type'],
                section_title=rc.get('section_title'),
                product_ids=product_ids,
                spec_names=chunk_specs,
                metadata={
                    'doc_type': extraction.doc_type.value,
                    'brand': extraction.brand_code,
                },
                token_count=rc.get('token_count'),
            )
            chunks.append(chunk)

        if chunks:
            await self.repo.create_chunks(chunks)

    # ----------------------------------------------------------
    # Spec Registry Discovery
    # ----------------------------------------------------------

    async def _register_new_spec(self, spec_name: str, stats: IngestionStats) -> None:
        """Register a newly discovered spec in the registry."""
        if spec_name.startswith('_unknown_'):
            display = spec_name.replace('_unknown_', '').replace('_', ' ').title()
        else:
            display = spec_name.replace('_', ' ').title()

        entry = SpecRegistryEntry(
            canonical_name=spec_name,
            display_name=display,
            data_type=SpecDataType.TEXT,  # Default; human reviews later
            auto_discovered=True,
            approved=False,
        )
        await self.repo.register_spec(entry)
        stats.new_specs_discovered += 1
        logger.info(f"New spec discovered: {spec_name}")


# ============================================================
# Helpers
# ============================================================

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# CLI / Script Entry Point
# ============================================================

async def ingest_directory(
    directory: str,
    repo: Optional[ProductRepository] = None,
    config: Optional[IngestionConfig] = None,
) -> IngestionStats:
    """
    Ingest all supported files from a directory.
    Convenience function for batch processing.
    """
    if repo is None:
        repo = InMemoryRepository()
    if config is None:
        config = DEFAULT_CONFIG

    orchestrator = IngestionOrchestrator(repo, config)
    dir_path = Path(directory)

    supported = {'.pdf', '.txt', '.md', '.html', '.json'}
    mime_map = {
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.html': 'text/html',
        '.json': 'application/json',
    }

    files = []
    for f in sorted(dir_path.iterdir()):
        if f.suffix.lower() in supported and f.is_file():
            content = f.read_bytes()
            files.append({
                'filename': f.name,
                'content': content,
                'mime_type': mime_map.get(f.suffix.lower(), 'application/octet-stream'),
            })

    if not files:
        logger.warning(f"No supported files found in {directory}")
        return IngestionStats()

    logger.info(f"Ingesting {len(files)} files from {directory}")
    job_id, stats = await orchestrator.ingest_batch(files)

    logger.info(
        f"Ingestion complete: {stats.processed_files}/{stats.total_files} processed, "
        f"{stats.new_products} new products, {stats.updated_products} updated, "
        f"{stats.conflicts_found} conflicts, {stats.new_specs_discovered} new specs"
    )
    return stats


# ============================================================
# Example / Test Usage
# ============================================================

async def _example():
    """Demonstrate the ingestion pipeline with sample data."""
    repo = InMemoryRepository()

    # Seed brands and families
    repo.brands['ABS'] = Brand(code='ABS', name='American BioTech Supply')
    repo.brands['LABRepCo'] = Brand(code='LABRepCo', name='LABRepCo')
    repo.brands['Corepoint'] = Brand(code='Corepoint', name='Corepoint Scientific')
    repo.brands['Celsius'] = Brand(code='Celsius', name='Celsius Scientific')
    repo.brands['CBS'] = Brand(code='CBS', name='CBS / CryoSafe')

    from models import SuperCategory
    families = [
        ('premier_lab_ref', 'Premier Lab Refrigerator', SuperCategory.REFRIGERATOR),
        ('standard_lab_ref', 'Standard Lab Refrigerator', SuperCategory.REFRIGERATOR),
        ('chromatography_ref', 'Chromatography Refrigerator', SuperCategory.REFRIGERATOR),
        ('pharmacy_vaccine_ref', 'Pharmacy Vaccine Refrigerator', SuperCategory.REFRIGERATOR),
        ('pharmacy_nsf_ref', 'Pharmacy NSF Refrigerator', SuperCategory.REFRIGERATOR),
        ('blood_bank_ref', 'Blood Bank Refrigerator', SuperCategory.REFRIGERATOR),
        ('flammable_storage_ref', 'Flammable Storage Refrigerator', SuperCategory.REFRIGERATOR),
        ('manual_defrost_freezer', 'Manual Defrost Freezer', SuperCategory.FREEZER),
        ('auto_defrost_freezer', 'Auto Defrost Freezer', SuperCategory.FREEZER),
        ('precision_freezer', 'Precision Freezer', SuperCategory.FREEZER),
        ('cryo_dewar', 'Cryogenic Dewar', SuperCategory.CRYOGENIC),
    ]
    for code, name, cat in families:
        repo.families[code] = ProductFamily(code=code, name=name, super_category=cat)

    # Simulate ingesting a product data sheet
    sample_text = """
    Product Data Sheet
    ABT-HC-26S Premier Laboratory Refrigerator

    General Description
    American BioTech Supply Premier 26 cu. ft. laboratory refrigerator
    with solid door, designed for general laboratory storage.

    Storage capacity (cu. ft)    26
    Adjustable Temperature Range    1°C to 10°C
    Door    One swing solid door, self-closing, right hinged
    Shelves    Four adjustable shelves (adjustable in ½" increments)
    Refrigerant    Hydrocarbon, natural refrigerant (R290)
    Compressor    Hermetic
    Defrost    Cycle
    Rated Amperage    3
    Controller technology    Microprocessor
    Display technology    LED, 0.1°C resolution
    Digital Communication    RS-485 MODBUS

    Dimensions
    Exterior    28 3/8    36 3/4    81 3/4
    Interior    23 3/4    28    52 1/4

    Product Weight (lbs)    235
    Shipping Weight (lbs)    275

    Agency Listing and Certification    ETL, C-ETL listed and certified to UL471 standard, Energy Star Certified

    General Warranty    Two (2) year parts and labor
    Compressor Warranty    Five (5) year compressor parts

    Rev_03.18.25
    """

    orchestrator = IngestionOrchestrator(repo)
    result, stats = await orchestrator.ingest_single(
        'ABT-HC-26S_DataSheet.pdf', sample_text
    )

    print(f"\n--- Ingestion Results ---")
    print(f"New products: {stats.new_products}")
    print(f"Conflicts: {stats.conflicts_found}")
    print(f"New specs discovered: {stats.new_specs_discovered}")

    # Verify product was created correctly
    product = await repo.get_product_by_model('ABT-HC-26S')
    if product:
        print(f"\nProduct: {product.model_number}")
        print(f"  Capacity: {product.storage_capacity_cuft} cu.ft.")
        print(f"  Temp: {product.temp_range_min_c}°C to {product.temp_range_max_c}°C")
        print(f"  Door: {product.door_type} x{product.door_count}")
        print(f"  Shelves: {product.shelf_count}")
        print(f"  Refrigerant: {product.refrigerant}")
        print(f"  Voltage: {product.voltage_v}V, {product.amperage}A")
        print(f"  Weight: {product.product_weight_lbs} lbs")
        print(f"  Dims: {product.ext_width_in} x {product.ext_depth_in} x {product.ext_height_in}")
        print(f"  Certs: {product.certifications}")
        print(f"  Revision: {product.revision}")
        print(f"  Dynamic specs: {list(product.specs.keys())}")

    # Simulate ingesting an update with a conflict
    updated_text = sample_text.replace(
        'Rated Amperage    3', 'Rated Amperage    3.5'
    ).replace('Rev_03.18.25', 'Rev_07.01.25')

    print(f"\n--- Ingesting update (amperage changed, newer revision) ---")
    result2, stats2 = await orchestrator.ingest_single(
        'ABT-HC-26S_DataSheet_v2.pdf', updated_text
    )
    print(f"Updated products: {stats2.updated_products}")
    print(f"Conflicts: {stats2.conflicts_found}")

    product2 = await repo.get_product_by_model('ABT-HC-26S')
    if product2:
        print(f"  Amperage now: {product2.amperage}A (was 3.0)")
        print(f"  Version: {product2.version}")
        print(f"  Revision: {product2.revision}")

    print(f"\n--- Chunks created: {len(repo.chunks)} ---")
    for c in repo.chunks[:3]:
        print(f"  [{c.chunk_type}] {c.section_title or 'No section'}: "
              f"{c.content[:80]}...")

    print(f"\n--- Conflicts logged: {len(repo.conflicts)} ---")
    for cf in repo.conflicts:
        print(f"  {cf.spec_name}: {cf.existing_value} → {cf.new_value} "
              f"[{cf.severity.value}] → {cf.resolution.value}")


if __name__ == '__main__':
    import asyncio
    asyncio.run(_example())
