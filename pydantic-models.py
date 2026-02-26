"""
Product Expert System — Core Pydantic Models
002_models.py
"""
from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator
import re

# ============================================================
# Enums
# ============================================================

class ProductStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending_review"
    ACTIVE = "active"
    DISCONTINUED = "discontinued"
    DEPRECATED = "deprecated"

class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"

class SuperCategory(str, Enum):
    REFRIGERATOR = "refrigerator"
    FREEZER = "freezer"
    CRYOGENIC = "cryogenic"
    ACCESSORY = "accessory"

class DocType(str, Enum):
    PRODUCT_DATA_SHEET = "product_data_sheet"
    CUT_SHEET = "cut_sheet"
    FEATURE_LIST = "feature_list"
    PERFORMANCE_DATA = "performance_data_sheet"
    PRODUCT_IMAGE = "product_image"
    DIMENSIONAL_DRAWING = "dimensional_drawing"
    SELECTION_GUIDE = "selection_guide"
    INSTALL_MANUAL = "install_manual"
    MARKETING = "marketing"
    CATALOG = "catalog"
    OTHER = "other"

class DocStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"

class RelationType(str, Enum):
    SUPERSEDES = "supersedes"
    EQUIVALENT = "equivalent_to"
    COMPATIBLE = "compatible_with"
    ACCESSORY = "accessory_for"
    VARIANT = "variant_of"
    REBRAND = "rebrand_of"

class UserRole(str, Enum):
    CUSTOMER = "customer"
    SALES_ENGINEER = "sales_engineer"
    PRODUCT_MANAGER = "product_manager"
    ADMIN = "admin"

class ConflictSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ConflictResolution(str, Enum):
    PENDING = "pending"
    KEEP_EXISTING = "keep_existing"
    ACCEPT_NEW = "accept_new"
    MANUAL = "manual_override"
    DISMISSED = "dismissed"

class ControllerTier(str, Enum):
    STANDARD = "standard"
    ULTRA_TOUCH = "ultra_touch"
    PRECISION = "precision"
    PID_BLOOD_BANK = "pid_blood_bank"

class SpecDataType(str, Enum):
    NUMERIC = "numeric"
    TEXT = "text"
    BOOLEAN = "boolean"
    ENUM = "enum"
    RANGE = "range"
    LIST = "list"

# ============================================================
# Core Domain Models
# ============================================================

class Brand(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    code: str
    name: str
    parent_org: Optional[str] = None
    is_active: bool = True

class ProductFamily(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    code: str
    name: str
    super_category: SuperCategory
    description: Optional[str] = None
    is_active: bool = True

class SpecRegistryEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    canonical_name: str
    display_name: str
    data_type: SpecDataType
    unit: Optional[str] = ""
    unit_system: str = "imperial"
    family_scope: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    unit_conversions: dict[str, float] = Field(default_factory=dict)
    allowed_values: Optional[Any] = None
    is_filterable: bool = True
    is_comparable: bool = True
    is_searchable: bool = True
    sort_order: int = 100
    auto_discovered: bool = False
    approved: bool = True

class Product(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    model_number: str
    brand_id: UUID
    family_id: UUID
    product_line: Optional[str] = None
    controller_tier: Optional[str] = None
    status: ProductStatus = ProductStatus.ACTIVE

    # Universal specs (fixed columns for fast queries)
    storage_capacity_cuft: Optional[float] = None
    temp_range_min_c: Optional[float] = None
    temp_range_max_c: Optional[float] = None
    door_count: Optional[int] = None
    door_type: Optional[str] = None
    shelf_count: Optional[int] = None
    refrigerant: Optional[str] = None
    voltage_v: Optional[int] = None
    amperage: Optional[float] = None
    product_weight_lbs: Optional[float] = None
    ext_width_in: Optional[float] = None
    ext_depth_in: Optional[float] = None
    ext_height_in: Optional[float] = None

    # Dynamic specs
    specs: dict[str, Any] = Field(default_factory=dict)
    certifications: list[str] = Field(default_factory=list)

    # Lifecycle
    effective_from: date = Field(default_factory=date.today)
    effective_to: Optional[date] = None
    version: int = 1
    replaced_by: list[UUID] = Field(default_factory=list)
    replaces: list[UUID] = Field(default_factory=list)

    description: Optional[str] = None
    revision: Optional[str] = None
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED

class ProductRelationship(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    relationship: RelationType
    confidence: float = 1.0
    notes: Optional[str] = None
    auto_detected: bool = False

# ============================================================
# Document Models
# ============================================================

class Document(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    doc_type: DocType
    mime_type: str
    source_uri: str
    checksum_sha256: str
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    extracted_text: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    brand_id: Optional[UUID] = None
    status: DocStatus = DocStatus.PENDING
    processing_log: list[dict] = Field(default_factory=list)
    version: int = 1

class DocumentChunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int
    content: str
    chunk_type: str = "text"
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    product_ids: list[UUID] = Field(default_factory=list)
    spec_names: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    token_count: Optional[int] = None

# ============================================================
# Extraction Models (pipeline output)
# ============================================================

class ExtractedSpec(BaseModel):
    """A single spec value extracted from a document."""
    name: str                    # raw field name from document
    canonical_name: Optional[str] = None  # mapped canonical name
    raw_value: str               # original text
    parsed_value: Any = None     # normalized value
    unit: Optional[str] = None
    confidence: float = 1.0
    page: Optional[int] = None
    section: Optional[str] = None

class ExtractionResult(BaseModel):
    """Full extraction output for one document."""
    document_id: UUID
    doc_type: DocType
    brand_code: Optional[str] = None
    model_numbers: list[str] = Field(default_factory=list)
    title: Optional[str] = None
    description: Optional[str] = None
    specs: list[ExtractedSpec] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    raw_text: Optional[str] = None
    pages_processed: int = 0
    extraction_time_ms: int = 0

# ============================================================
# Conflict Models
# ============================================================

class SpecConflict(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID
    spec_name: str
    existing_value: Optional[str] = None
    new_value: Optional[str] = None
    source_doc_id: Optional[UUID] = None
    existing_doc_id: Optional[UUID] = None
    severity: ConflictSeverity = ConflictSeverity.MEDIUM
    resolution: ConflictResolution = ConflictResolution.PENDING

# ============================================================
# API Request/Response Models
# ============================================================

class RecommendRequest(BaseModel):
    query_id: Optional[str] = None
    use_case: Optional[str] = None
    free_text: Optional[str] = None
    structured_specs: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, float] = Field(default_factory=dict)
    brand_filter: Optional[list[str]] = None
    family_filter: Optional[list[str]] = None
    region: Optional[str] = None
    units_preference: str = "imperial"
    top_n: int = 5
    include_alternates: bool = True
    include_discontinued: bool = False

class SpecMatchResult(BaseModel):
    spec: str
    display_name: str
    value_required: Optional[Any] = None
    value_product: Optional[Any] = None
    unit: str = ""
    delta_pct: Optional[float] = None
    within_tolerance: bool = True
    score: float = 1.0

class ComplianceResult(BaseModel):
    rule: str
    status: str  # pass, fail, warning, not_applicable
    details: str

class Citation(BaseModel):
    doc_id: str
    filename: str
    page: Optional[int] = None
    section: Optional[str] = None
    snippet: str

class ProductRecommendation(BaseModel):
    product_id: str
    model_number: str
    brand: str
    family: str
    score: float
    hard_pass: bool
    match_breakdown: list[SpecMatchResult]
    compliance: list[ComplianceResult] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    notes: Optional[str] = None

class DecisionTrace(BaseModel):
    step: str
    detail: str
    products_remaining: int
    timestamp: str

class RecommendResponse(BaseModel):
    query_id: str
    products: list[ProductRecommendation]
    alternates: list[ProductRecommendation] = Field(default_factory=list)
    clarifications_needed: list[dict] = Field(default_factory=list)
    decision_trace: list[DecisionTrace] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    response_time_ms: int = 0
    model_version: str = "v1.0.0"

class CompareRequest(BaseModel):
    product_ids: list[str]
    user_constraints: dict[str, Any] = Field(default_factory=dict)
    highlight_differences: bool = True

class CompareResponse(BaseModel):
    products: list[str]
    specs_compared: list[dict]
    suitability_scores: list[float]
    summary: Optional[str] = None
    citations: list[Citation] = Field(default_factory=list)

class IngestRequest(BaseModel):
    file_uris: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    replace_existing: bool = False

class IngestResponse(BaseModel):
    job_id: str
    status: str
    files_accepted: int
    validation_issues: list[str] = Field(default_factory=list)
    estimated_completion_minutes: Optional[int] = None

class HealthResponse(BaseModel):
    status: str
    components: dict[str, dict]
    version: str
    uptime_seconds: int

# ============================================================
# Utility: Fraction Parser
# ============================================================

FRACTION_MAP = {
    '½': 0.5, '¼': 0.25, '¾': 0.75,
    '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875,
    '⅓': 0.333, '⅔': 0.667, '⅕': 0.2, '⅖': 0.4,
    '⅗': 0.6, '⅘': 0.8, '⅙': 0.167, '⅚': 0.833,
}

def parse_fraction(text: str) -> Optional[float]:
    """Parse dimension strings like '23 ¾', '48 5⁄8', '26 7/8' into float."""
    if text is None:
        return None
    t = text.strip().rstrip('"').rstrip("'").strip()
    if not t:
        return None

    # Direct number
    try:
        return float(t)
    except ValueError:
        pass

    # Unicode fraction: "23 ¾" or "¾"
    for uf, val in FRACTION_MAP.items():
        if uf in t:
            whole = t.replace(uf, '').strip()
            return (float(whole) if whole else 0) + val

    # Slash fraction: "23 3/4" or "26 7/8" or "7⁄8" (unicode fraction slash)
    t = t.replace('⁄', '/')  # normalize unicode fraction slash
    m = re.match(r'^(\d+)\s+(\d+)/(\d+)$', t)
    if m:
        return float(m.group(1)) + float(m.group(2)) / float(m.group(3))

    m = re.match(r'^(\d+)/(\d+)$', t)
    if m:
        return float(m.group(1)) / float(m.group(2))

    # Decimal with trailing junk
    m = re.match(r'^(\d+\.?\d*)', t)
    if m:
        return float(m.group(1))

    return None


def parse_temp_range(text: str) -> tuple[Optional[float], Optional[float]]:
    """Parse temperature range strings like '1°C to 10°C', '-35°C to -15°C', '36°F – 46°F (2°C – 8°C)'."""
    if not text:
        return None, None

    # Prefer Celsius if both present: "36°F – 46°F (2°C – 8°C)"
    c_match = re.findall(r'(-?\d+(?:\.\d+)?)\s*°?\s*C', text)
    if len(c_match) >= 2:
        vals = sorted([float(x) for x in c_match])
        return vals[0], vals[-1]

    # Fahrenheit only — convert
    f_match = re.findall(r'(-?\d+(?:\.\d+)?)\s*°?\s*F', text)
    if len(f_match) >= 2:
        vals = sorted([(float(x) - 32) * 5 / 9 for x in f_match])
        return round(vals[0], 1), round(vals[-1], 1)

    # Plain numbers with "to" / "–"
    m = re.findall(r'(-?\d+(?:\.\d+)?)', text)
    if len(m) >= 2:
        vals = sorted([float(x) for x in m])
        return vals[0], vals[-1]

    return None, None


def parse_refrigerant(text: str) -> Optional[str]:
    """Extract refrigerant code from text like 'Hydrocarbon, natural refrigerant (R290)'."""
    if not text:
        return None
    m = re.search(r'(R-?\d{2,4}[a-zA-Z]?)', text, re.IGNORECASE)
    return m.group(1).upper().replace('-', '') if m else None


def parse_electrical(text: str) -> dict[str, Any]:
    """Parse compound electrical strings like '115V, 60 Hz, 3 Amps, 1/5 HP'."""
    result: dict[str, Any] = {}
    if not text:
        return result

    # Voltage: "115V" or "110 - 120V" or "110-120V AC"
    vm = re.search(r'(\d{2,3})\s*[-–to]+\s*(\d{2,3})\s*V', text)
    if vm:
        result['voltage_min_v'] = int(vm.group(1))
        result['voltage_max_v'] = int(vm.group(2))
        result['voltage_v'] = int(vm.group(2))
    else:
        vm = re.search(r'(\d{2,3})\s*V', text)
        if vm:
            result['voltage_v'] = int(vm.group(1))

    # Frequency
    fm = re.search(r'(\d{2})\s*Hz', text)
    if fm:
        result['frequency_hz'] = int(fm.group(1))

    # Amps
    am = re.search(r'([\d.]+)\s*[Aa]mp', text)
    if am:
        result['amperage'] = float(am.group(1))

    # HP: "1/5 HP" or "1/3 HP" or "0.5 HP"
    hm = re.search(r'(\d+/\d+|\d+\.?\d*)\s*HP', text, re.IGNORECASE)
    if hm:
        result['horsepower'] = hm.group(1)

    # Phase
    pm = re.search(r'(\d)\s*PH', text, re.IGNORECASE)
    if pm:
        result['phase'] = int(pm.group(1))

    # NEMA plug
    nm = re.search(r'(NEMA[\s-]*\d+-\d+\w?)', text, re.IGNORECASE)
    if nm:
        result['plug_type'] = nm.group(1).upper().replace(' ', '-')

    # Breaker
    bm = re.search(r'(\d+)\s*A?\s*breaker', text, re.IGNORECASE)
    if bm:
        result['breaker_amps'] = int(bm.group(1))

    return result


def parse_door_config(text: str) -> dict[str, Any]:
    """Parse door strings like 'One swing solid door, self-closing, right hinged'."""
    result: dict[str, Any] = {}
    if not text:
        return result
    t = text.lower()

    # Count
    count_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'double': 2, 'single': 1, '1': 1, '2': 2}
    for word, n in count_map.items():
        if word in t:
            result['door_count'] = n
            break

    # Type
    if 'glass' in t and 'sliding' in t:
        result['door_type'] = 'glass_sliding'
    elif 'glass' in t:
        result['door_type'] = 'glass'
    elif 'solid' in t:
        result['door_type'] = 'solid'
    elif 'stainless' in t:
        result['door_type'] = 'stainless_steel'

    # Hinge
    if 'right and left' in t or 'right & left' in t:
        result['door_hinge'] = 'right_and_left'
    elif 'right' in t:
        result['door_hinge'] = 'right'
    elif 'left' in t:
        result['door_hinge'] = 'left'

    # Features
    feats = []
    if 'self-closing' in t or 'self closing' in t:
        feats.append('self_closing')
    if 'magnetic' in t:
        feats.append('magnetic_gasket')
    if 'vacuum insulated' in t:
        feats.append('vacuum_insulated')
    if 'double pane' in t:
        feats.append('double_pane')
    if 'not reversible' in t or 'non-reversible' in t:
        feats.append('non_reversible')
    if feats:
        result['door_features'] = feats

    return result


def parse_shelf_config(text: str) -> dict[str, Any]:
    """Parse shelf strings like 'Four adjustable shelves (adjustable in ½" increments)'."""
    result: dict[str, Any] = {}
    if not text:
        return result
    t = text.lower()

    count_map = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'ten': 10
    }
    for word, n in count_map.items():
        if word in t:
            result['shelf_count'] = n
            break
    if 'shelf_count' not in result:
        m = re.search(r'(\d+)\s*(total\s+)?shelv', t)
        if m:
            result['shelf_count'] = int(m.group(1))

    if 'adjustable' in t and 'fixed' in t:
        result['shelf_type'] = 'mixed'
    elif 'adjustable' in t:
        result['shelf_type'] = 'adjustable'
    elif 'fixed' in t:
        result['shelf_type'] = 'fixed'

    m = re.search(r'adjustable in ([\d½¼¾⅛⅜⅝⅞/\s"]+)\s*increment', t)
    if m:
        result['shelf_adjustment_increment'] = m.group(1).strip()

    if 'guard rail' in t:
        result['shelf_features'] = ['guard_rail']

    return result


def parse_certifications(text: str) -> list[str]:
    """Extract certification codes from text."""
    if not text:
        return []
    certs = []
    t = text.upper()

    cert_patterns = [
        (r'ETL', 'ETL'), (r'C-?ETL', 'C-ETL'), (r'UL\s*471', 'UL471'),
        (r'UL\s*60335', 'UL60335'), (r'CSA\s*C22', 'CSA_C22'),
        (r'ENERGY\s*STAR', 'Energy_Star'), (r'NSF[\s/]*ANSI\s*456', 'NSF_ANSI_456'),
        (r'FDA', 'FDA'), (r'AABB', 'AABB'), (r'CE\b', 'CE'),
        (r'EPA\s*SNAP', 'EPA_SNAP'), (r'21\s*CFR', '21CFR_820'),
        (r'NFPA\s*45', 'NFPA_45'), (r'NFPA\s*30', 'NFPA_30'),
    ]
    for pattern, code in cert_patterns:
        if re.search(pattern, t):
            certs.append(code)
    return sorted(set(certs))
