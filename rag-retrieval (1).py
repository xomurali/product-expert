"""
Product Expert System — RAG Retrieval Layer
006_rag_retrieval.py

Responsibilities:
  1. Hybrid retrieval: vector similarity + keyword/BM25 + metadata filters
  2. Query understanding & expansion (spec synonyms, model numbers)
  3. Re-ranking with cross-encoder or heuristic scoring
  4. Citation assembly with page/section references
  5. Context window management for LLM prompts
  6. Grounded response generation with hallucination guards
"""
from __future__ import annotations
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Callable
from uuid import UUID, uuid4

from models import (
    DocumentChunk, Document, Product, Citation,
    DocType, SpecRegistryEntry, SpecDataType,
    ExtractionResult,
)

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

@dataclass
class RAGConfig:
    """Tunable parameters for retrieval."""
    # Retrieval
    vector_top_k: int = 30           # candidates from vector search
    keyword_top_k: int = 20          # candidates from keyword search
    final_top_k: int = 8             # after re-ranking & fusion
    min_relevance_score: float = 0.3 # discard below this

    # Hybrid fusion
    vector_weight: float = 0.6       # RRF weight for vector results
    keyword_weight: float = 0.3      # RRF weight for keyword results
    metadata_weight: float = 0.1     # boost for metadata match

    # Context window
    max_context_tokens: int = 6000   # total tokens for LLM context
    max_chunks_in_context: int = 10  # hard cap on chunks
    chunk_header_tokens: int = 30    # overhead per chunk in prompt

    # Embedding
    embedding_model: str = 'e5-large-v2'
    embedding_dim: int = 1024

    # Re-ranking
    use_cross_encoder: bool = False  # if True, uses cross-encoder reranker
    cross_encoder_model: str = 'cross-encoder/ms-marco-MiniLM-L-12-v2'


DEFAULT_RAG_CONFIG = RAGConfig()


# ============================================================
# Query Understanding
# ============================================================

@dataclass
class ParsedQuery:
    """Structured representation of a user query."""
    original: str
    cleaned: str
    model_numbers: list[str] = field(default_factory=list)
    spec_mentions: list[str] = field(default_factory=list)
    brand_mentions: list[str] = field(default_factory=list)
    cert_mentions: list[str] = field(default_factory=list)
    family_hints: list[str] = field(default_factory=list)
    intent: str = 'general'  # general, spec_lookup, compare, troubleshoot
    expanded_terms: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)


# Model number patterns (same as extraction pipeline)
_MODEL_PATTERNS = [
    r'(ABT-HC-(?:CS-)?\d+[A-Z]?)',
    r'(PH-ABT-(?:HC|NSF)-[\w-]+)',
    r'(LHT-\d+-[A-Z]+)',
    r'(LPVT-\d+-[A-Z]+)',
    r'(NSBR\d+\w+/\d)',
    r'(CEL-[\w-]+)',
    r'(CP-[\w-]+)',
]

# Spec synonym map for query expansion
_SPEC_SYNONYMS: dict[str, list[str]] = {
    'storage_capacity_cuft': [
        'capacity', 'volume', 'cubic feet', 'cu ft', 'cu. ft', 'size',
        'how big', 'how much space', 'storage space',
    ],
    'temp_range_min_c': [
        'minimum temperature', 'lowest temp', 'coldest', 'min temp',
        'how cold', 'temperature range',
    ],
    'temp_range_max_c': [
        'maximum temperature', 'highest temp', 'warmest', 'max temp',
    ],
    'uniformity_c': [
        'uniformity', 'temperature uniformity', 'temp uniformity',
        'even temperature', 'consistent temp',
    ],
    'stability_c': [
        'stability', 'temperature stability', 'temp stability',
        'temperature fluctuation',
    ],
    'energy_kwh_day': [
        'energy', 'power consumption', 'energy consumption',
        'electricity', 'kwh', 'energy efficient', 'running cost',
    ],
    'noise_dba': [
        'noise', 'sound', 'decibel', 'dba', 'how loud', 'quiet',
    ],
    'refrigerant': [
        'refrigerant', 'r290', 'r600a', 'r134a', 'hydrocarbon',
        'natural refrigerant', 'gas type',
    ],
    'certifications': [
        'certification', 'certified', 'listed', 'etl', 'ul',
        'energy star', 'nsf', 'fda', 'aabb', 'nfpa',
    ],
    'door_type': [
        'door', 'solid door', 'glass door', 'sliding door',
    ],
    'defrost_type': [
        'defrost', 'manual defrost', 'auto defrost', 'cycle defrost',
        'frost free',
    ],
    'ext_width_in': ['width', 'wide', 'how wide'],
    'ext_depth_in': ['depth', 'deep', 'how deep'],
    'ext_height_in': ['height', 'tall', 'how tall'],
    'product_weight_lbs': ['weight', 'heavy', 'how heavy', 'lbs'],
    'amperage': ['amps', 'amperage', 'current draw', 'electrical'],
    'voltage_v': ['voltage', 'volts', '115v', '220v'],
    'shelf_count': ['shelves', 'shelf', 'how many shelves'],
    'pulldown_time_min': ['pulldown', 'pull down', 'cool down time'],
    'warranty_general_years': ['warranty', 'guarantee'],
}

# Brand patterns
_BRAND_PATTERNS = {
    'ABS': [r'\bABS\b', r'American\s*Bio\s*Tech'],
    'LABRepCo': [r'LABRepCo', r'Lab\s*Rep\s*Co'],
    'Corepoint': [r'Corepoint'],
    'Celsius': [r'Celsius\s*Scientific', r'°celsius'],
    'CBS': [r'\bCBS\b', r'CryoSafe'],
}

# Intent classification keywords
_INTENT_KEYWORDS = {
    'spec_lookup': [
        'what is', 'what are', 'tell me', 'specs', 'specifications',
        'data sheet', 'spec sheet', 'features',
    ],
    'compare': [
        'compare', 'versus', 'vs', 'difference', 'better',
        'which one', 'or',
    ],
    'troubleshoot': [
        'alarm', 'error', 'problem', 'issue', 'not working',
        'temperature too', 'won\'t cool', 'beeping',
    ],
    'recommend': [
        'recommend', 'suggest', 'need', 'looking for', 'best',
        'which', 'what should', 'help me choose',
    ],
    'compliance': [
        'comply', 'compliance', 'regulation', 'cdc', 'fda',
        'nsf', 'nfpa', 'aabb', 'requirements',
    ],
}


def parse_query(
    query: str,
    spec_registry: Optional[dict[str, SpecRegistryEntry]] = None,
) -> ParsedQuery:
    """Parse a user query into structured components."""
    pq = ParsedQuery(original=query, cleaned=query.strip())
    q = query.lower()

    # Extract model numbers
    for pat in _MODEL_PATTERNS:
        for m in re.finditer(pat, query, re.IGNORECASE):
            pq.model_numbers.append(m.group(1))

    # Detect brands
    for brand, patterns in _BRAND_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, query, re.IGNORECASE):
                pq.brand_mentions.append(brand)
                break

    # Detect spec mentions via synonyms
    for canon, syns in _SPEC_SYNONYMS.items():
        for syn in syns:
            if syn in q:
                if canon not in pq.spec_mentions:
                    pq.spec_mentions.append(canon)
                break

    # Also check registry synonyms
    if spec_registry:
        for name, entry in spec_registry.items():
            for syn in entry.synonyms:
                if syn.lower() in q:
                    if name not in pq.spec_mentions:
                        pq.spec_mentions.append(name)
                    break

    # Detect certifications
    cert_pats = {
        'NSF_ANSI_456': [r'nsf\s*/?ansi\s*456', r'nsf\s*456'],
        'Energy_Star': [r'energy\s*star'],
        'ETL': [r'\betl\b'],
        'FDA': [r'\bfda\b'],
        'AABB': [r'\baabb\b'],
        'NFPA_45': [r'nfpa\s*45'],
        'EPA_SNAP': [r'epa\s*snap'],
    }
    for cert, pats in cert_pats.items():
        for pat in pats:
            if re.search(pat, q):
                pq.cert_mentions.append(cert)
                break

    # Detect family hints
    family_kw = {
        'premier_lab_ref': ['premier', 'lab refrigerator'],
        'pharmacy_vaccine_ref': ['pharmacy', 'vaccine'],
        'pharmacy_nsf_ref': ['nsf', 'vaccine storage'],
        'chromatography_ref': ['chromatography', 'hplc', 'column'],
        'blood_bank_ref': ['blood bank', 'blood product'],
        'flammable_storage_ref': ['flammable', 'solvent'],
        'manual_defrost_freezer': ['manual defrost', 'freezer'],
        'auto_defrost_freezer': ['auto defrost', 'frost free'],
        'cryo_dewar': ['dewar', 'cryogenic', 'liquid nitrogen'],
    }
    for fam, kws in family_kw.items():
        for kw in kws:
            if kw in q:
                if fam not in pq.family_hints:
                    pq.family_hints.append(fam)
                break

    # Classify intent
    intent_scores: dict[str, int] = {}
    for intent, kws in _INTENT_KEYWORDS.items():
        for kw in kws:
            if kw in q:
                intent_scores[intent] = intent_scores.get(intent, 0) + 1
    if intent_scores:
        pq.intent = max(intent_scores, key=intent_scores.get)
    elif pq.model_numbers:
        pq.intent = 'spec_lookup'

    # Query expansion — add synonyms for detected specs
    expanded = set()
    for spec in pq.spec_mentions:
        syns = _SPEC_SYNONYMS.get(spec, [])
        expanded.update(syns[:3])  # top 3 synonyms
    pq.expanded_terms = sorted(expanded)

    # Build filters
    if pq.model_numbers:
        pq.filters['model_numbers'] = pq.model_numbers
    if pq.brand_mentions:
        pq.filters['brands'] = pq.brand_mentions
    if pq.family_hints:
        pq.filters['families'] = pq.family_hints

    return pq


# ============================================================
# Embedding Interface
# ============================================================

class EmbeddingProvider:
    """
    Abstract embedding provider. In production, wraps an API call
    to an embedding model service.
    """

    def __init__(self, model: str = 'e5-large-v2', dim: int = 1024):
        self.model = model
        self.dim = dim

    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query. Adds 'query: ' prefix for e5 models."""
        # In production: call embedding API
        # For now, return a mock vector
        return self._mock_embed(f"query: {text}")

    async def embed_document(self, text: str) -> list[float]:
        """Embed a document chunk. Adds 'passage: ' prefix for e5 models."""
        return self._mock_embed(f"passage: {text}")

    async def embed_batch(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        """Embed multiple texts."""
        prefix = "query: " if is_query else "passage: "
        return [self._mock_embed(f"{prefix}{t}") for t in texts]

    def _mock_embed(self, text: str) -> list[float]:
        """Deterministic mock embedding based on text hash."""
        import hashlib
        h = hashlib.sha256(text.encode()).hexdigest()
        # Generate dim-length vector from hash (repeating as needed)
        vals = []
        for i in range(self.dim):
            byte_idx = (i * 2) % len(h)
            vals.append((int(h[byte_idx:byte_idx+2], 16) - 128) / 128.0)
        # Normalize
        norm = sum(v*v for v in vals) ** 0.5
        return [v / norm for v in vals] if norm > 0 else vals


# ============================================================
# Vector Store Interface
# ============================================================

class VectorStore:
    """
    Abstract vector store. In production, backed by pgvector.
    Supports filtered similarity search.
    """

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Search for similar chunks.
        Returns list of (chunk, similarity_score) sorted by score desc.
        """
        raise NotImplementedError

    async def upsert(self, chunk_id: UUID, vector: list[float]) -> None:
        """Store or update a chunk embedding."""
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    """In-memory vector store for testing."""

    def __init__(self):
        self.vectors: dict[UUID, list[float]] = {}
        self.chunks: dict[UUID, DocumentChunk] = {}

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        results = []
        for cid, vec in self.vectors.items():
            chunk = self.chunks.get(cid)
            if not chunk:
                continue

            # Apply filters
            if filters:
                if 'product_ids' in filters:
                    req_ids = set(str(x) for x in filters['product_ids'])
                    chunk_ids = set(str(x) for x in chunk.product_ids)
                    if not req_ids & chunk_ids:
                        continue
                if 'chunk_types' in filters:
                    if chunk.chunk_type not in filters['chunk_types']:
                        continue
                if 'doc_types' in filters:
                    doc_type = chunk.metadata.get('doc_type')
                    if doc_type and doc_type not in filters['doc_types']:
                        continue
                if 'brands' in filters:
                    brand = chunk.metadata.get('brand')
                    if brand and brand not in filters['brands']:
                        continue

            sim = self._cosine_sim(query_vector, vec)
            results.append((chunk, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    async def upsert(self, chunk_id: UUID, vector: list[float]) -> None:
        self.vectors[chunk_id] = vector

    def register_chunk(self, chunk: DocumentChunk) -> None:
        self.chunks[chunk.id] = chunk

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x*y for x, y in zip(a, b))
        na = sum(x*x for x in a) ** 0.5
        nb = sum(x*x for x in b) ** 0.5
        return dot / (na * nb) if na > 0 and nb > 0 else 0.0


# ============================================================
# Keyword Search (BM25-style)
# ============================================================

class KeywordSearcher:
    """
    Simple keyword search over chunk content.
    In production, backed by PostgreSQL full-text search (tsvector).
    """

    def __init__(self):
        self.chunks: dict[UUID, DocumentChunk] = {}

    def index_chunk(self, chunk: DocumentChunk) -> None:
        self.chunks[chunk.id] = chunk

    def search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """BM25-style keyword search."""
        terms = self._tokenize(query)
        if not terms:
            return []

        results = []
        for chunk in self.chunks.values():
            # Apply filters
            if filters:
                if 'brands' in filters:
                    brand = chunk.metadata.get('brand')
                    if brand and brand not in filters['brands']:
                        continue
                if 'chunk_types' in filters:
                    if chunk.chunk_type not in filters['chunk_types']:
                        continue

            content_lower = chunk.content.lower()
            content_terms = self._tokenize(chunk.content)

            # Simple TF scoring
            score = 0.0
            for term in terms:
                tf = content_lower.count(term)
                if tf > 0:
                    # Log-normalized TF
                    score += 1.0 + (tf - 1) * 0.3

                # Boost for exact spec name matches
                if term in [s.lower().replace('_', ' ') for s in (chunk.spec_names or [])]:
                    score += 2.0

                # Boost for section title match
                if chunk.section_title and term in chunk.section_title.lower():
                    score += 1.5

            # Boost for model number match
            for model in (chunk.product_ids or []):
                if str(model).lower() in query.lower():
                    score += 3.0

            if score > 0:
                # Normalize by doc length (simple BM25-like)
                doc_len = len(content_terms) or 1
                avg_len = 100  # assumed average
                norm = score / (score + 0.5 * (1 - 0.75 + 0.75 * doc_len / avg_len))
                results.append((chunk, norm))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple whitespace tokenizer with stopword removal."""
        stop = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may',
            'might', 'shall', 'can', 'of', 'in', 'to', 'for',
            'with', 'on', 'at', 'by', 'from', 'it', 'its',
            'this', 'that', 'and', 'or', 'but', 'not', 'no',
            'what', 'which', 'who', 'how', 'when', 'where',
        }
        words = re.findall(r'\b\w+\b', text.lower())
        return [w for w in words if w not in stop and len(w) > 1]


# ============================================================
# Re-Ranking
# ============================================================

@dataclass
class ScoredChunk:
    """A chunk with its final relevance score and source info."""
    chunk: DocumentChunk
    score: float
    source: str  # 'vector', 'keyword', 'both'
    vector_rank: Optional[int] = None
    keyword_rank: Optional[int] = None


def reciprocal_rank_fusion(
    vector_results: list[tuple[DocumentChunk, float]],
    keyword_results: list[tuple[DocumentChunk, float]],
    vector_weight: float = 0.6,
    keyword_weight: float = 0.3,
    k: int = 60,
) -> list[ScoredChunk]:
    """
    Fuse vector and keyword search results using Reciprocal Rank Fusion.
    """
    chunk_scores: dict[UUID, ScoredChunk] = {}

    # Process vector results
    for rank, (chunk, sim) in enumerate(vector_results):
        rrf = vector_weight / (k + rank + 1)
        if chunk.id not in chunk_scores:
            chunk_scores[chunk.id] = ScoredChunk(
                chunk=chunk, score=0.0, source='vector',
                vector_rank=rank,
            )
        chunk_scores[chunk.id].score += rrf
        chunk_scores[chunk.id].vector_rank = rank

    # Process keyword results
    for rank, (chunk, score) in enumerate(keyword_results):
        rrf = keyword_weight / (k + rank + 1)
        if chunk.id not in chunk_scores:
            chunk_scores[chunk.id] = ScoredChunk(
                chunk=chunk, score=0.0, source='keyword',
                keyword_rank=rank,
            )
        else:
            chunk_scores[chunk.id].source = 'both'
        chunk_scores[chunk.id].score += rrf
        chunk_scores[chunk.id].keyword_rank = rank

    results = list(chunk_scores.values())
    results.sort(key=lambda x: x.score, reverse=True)
    return results


def heuristic_rerank(
    chunks: list[ScoredChunk],
    parsed_query: ParsedQuery,
    config: RAGConfig = DEFAULT_RAG_CONFIG,
) -> list[ScoredChunk]:
    """
    Apply heuristic re-ranking boosts based on query understanding.
    Used when cross-encoder is disabled.
    """
    for sc in chunks:
        chunk = sc.chunk
        boost = 0.0

        # Boost if chunk mentions queried model numbers
        for model in parsed_query.model_numbers:
            if model.lower() in chunk.content.lower():
                boost += 0.15

        # Boost spec_block chunks when query is about specs
        if parsed_query.intent == 'spec_lookup' and chunk.chunk_type == 'spec_block':
            boost += 0.10

        # Boost performance_data chunks for performance queries
        perf_specs = {'uniformity_c', 'stability_c', 'energy_kwh_day', 'noise_dba'}
        if perf_specs & set(parsed_query.spec_mentions):
            if chunk.chunk_type == 'performance_data':
                boost += 0.12

        # Boost dimensional chunks for dimension queries
        dim_specs = {'ext_width_in', 'ext_depth_in', 'ext_height_in'}
        if dim_specs & set(parsed_query.spec_mentions):
            if chunk.chunk_type == 'dimensional':
                boost += 0.10

        # Boost chunks from product_data_sheet docs (more authoritative)
        if chunk.metadata.get('doc_type') == 'product_data_sheet':
            boost += 0.05
        elif chunk.metadata.get('doc_type') == 'performance_data_sheet':
            if perf_specs & set(parsed_query.spec_mentions):
                boost += 0.08

        # Boost chunks that appear in both vector and keyword results
        if sc.source == 'both':
            boost += 0.08

        # Penalize very short chunks (likely headers or noise)
        if chunk.token_count and chunk.token_count < 30:
            boost -= 0.10

        sc.score += boost

    chunks.sort(key=lambda x: x.score, reverse=True)
    return chunks


# ============================================================
# Context Builder
# ============================================================

@dataclass
class RetrievalContext:
    """Assembled context for LLM prompt construction."""
    chunks: list[ScoredChunk]
    citations: list[Citation]
    total_tokens: int
    context_text: str
    product_context: Optional[str] = None
    system_notes: list[str] = field(default_factory=list)


def build_context(
    ranked_chunks: list[ScoredChunk],
    parsed_query: ParsedQuery,
    products: Optional[list[Product]] = None,
    config: RAGConfig = DEFAULT_RAG_CONFIG,
) -> RetrievalContext:
    """
    Build the retrieval context for LLM prompt injection.
    Manages token budget, deduplication, and citation assembly.
    """
    selected: list[ScoredChunk] = []
    citations: list[Citation] = []
    seen_content: set[str] = set()
    token_budget = config.max_context_tokens
    tokens_used = 0

    for sc in ranked_chunks:
        if sc.score < config.min_relevance_score:
            break
        if len(selected) >= config.max_chunks_in_context:
            break

        # Dedup: skip near-duplicate content
        content_sig = _content_signature(sc.chunk.content)
        if content_sig in seen_content:
            continue
        seen_content.add(content_sig)

        # Check token budget
        chunk_tokens = (sc.chunk.token_count or _est_tokens(sc.chunk.content))
        chunk_tokens += config.chunk_header_tokens
        if tokens_used + chunk_tokens > token_budget:
            # Try to fit a truncated version
            remaining = token_budget - tokens_used - config.chunk_header_tokens
            if remaining > 100:
                sc.chunk.content = sc.chunk.content[:remaining * 4]
                chunk_tokens = remaining + config.chunk_header_tokens
            else:
                break

        selected.append(sc)
        tokens_used += chunk_tokens

        # Build citation
        citations.append(Citation(
            doc_id=str(sc.chunk.document_id),
            filename='',  # resolved from doc store in production
            page=None,
            section=sc.chunk.section_title,
            snippet=sc.chunk.content[:200],
        ))

    # Build context text
    context_parts = []
    for i, sc in enumerate(selected):
        header = _format_chunk_header(sc, i + 1)
        context_parts.append(f"{header}\n{sc.chunk.content}")

    context_text = "\n\n---\n\n".join(context_parts)

    # Build product context (structured spec summary)
    product_context = None
    if products:
        product_context = _format_product_context(products)
        product_tokens = _est_tokens(product_context)
        tokens_used += product_tokens

    # System notes for the LLM
    notes = []
    if parsed_query.model_numbers:
        notes.append(
            f"User is asking about model(s): {', '.join(parsed_query.model_numbers)}")
    if parsed_query.spec_mentions:
        notes.append(
            f"Query relates to specs: {', '.join(parsed_query.spec_mentions)}")
    if parsed_query.intent:
        notes.append(f"Query intent: {parsed_query.intent}")

    return RetrievalContext(
        chunks=selected,
        citations=citations,
        total_tokens=tokens_used,
        context_text=context_text,
        product_context=product_context,
        system_notes=notes,
    )


def _format_chunk_header(sc: ScoredChunk, idx: int) -> str:
    """Format a chunk header for context injection."""
    parts = [f"[Source {idx}]"]
    if sc.chunk.section_title:
        parts.append(f"Section: {sc.chunk.section_title}")
    if sc.chunk.chunk_type != 'text':
        parts.append(f"Type: {sc.chunk.chunk_type}")
    brand = sc.chunk.metadata.get('brand')
    if brand:
        parts.append(f"Brand: {brand}")
    parts.append(f"Relevance: {sc.score:.2f}")
    return " | ".join(parts)


def _format_product_context(products: list[Product]) -> str:
    """Format product specs as structured context for the LLM."""
    parts = ["## Product Specifications\n"]

    for p in products:
        parts.append(f"### {p.model_number}")
        if p.product_line:
            parts.append(f"Product Line: {p.product_line}")
        if p.storage_capacity_cuft:
            parts.append(f"Capacity: {p.storage_capacity_cuft} cu.ft.")
        if p.temp_range_min_c is not None and p.temp_range_max_c is not None:
            parts.append(
                f"Temperature Range: {p.temp_range_min_c}°C to {p.temp_range_max_c}°C")
        if p.door_type:
            parts.append(f"Door: {p.door_count or 1}x {p.door_type}")
        if p.refrigerant:
            parts.append(f"Refrigerant: {p.refrigerant}")
        if p.voltage_v:
            parts.append(f"Electrical: {p.voltage_v}V, {p.amperage}A")
        if p.ext_width_in:
            parts.append(
                f"Dimensions: {p.ext_width_in}\" W × "
                f"{p.ext_depth_in}\" D × {p.ext_height_in}\" H")
        if p.certifications:
            parts.append(f"Certifications: {', '.join(p.certifications)}")

        # Dynamic specs
        for k, v in sorted(p.specs.items()):
            if not k.startswith('_unknown_') and k != 'product_type':
                display = k.replace('_', ' ').title()
                parts.append(f"{display}: {v}")
        parts.append("")

    return "\n".join(parts)


def _content_signature(text: str) -> str:
    """Generate a signature for dedup. Uses first 100 chars normalized."""
    sig = re.sub(r'\s+', ' ', text[:200].lower().strip())
    return sig[:100]


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ============================================================
# Prompt Builder
# ============================================================

SYSTEM_PROMPT = """You are a Product Expert for laboratory, pharmacy, and vaccine storage refrigerators and freezers. You help users find the right product, compare options, and answer technical questions.

IMPORTANT RULES:
1. Only state facts that are supported by the provided source documents and product data.
2. When citing specifications, reference the source document section.
3. If information is not available in the provided context, say so clearly.
4. Never fabricate or guess specifications — accuracy is critical for compliance.
5. For vaccine storage, always verify NSF/ANSI 456 certification status.
6. For blood bank applications, verify FDA and AABB compliance.
7. Temperature ranges are in °C unless the user requests °F.
8. When comparing products, highlight both similarities and differences.
9. For electrical specs, always confirm voltage compatibility."""


def build_prompt(
    query: str,
    context: RetrievalContext,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> list[dict[str, str]]:
    """
    Build a complete prompt for the LLM with retrieval context.

    Returns messages in OpenAI/Anthropic format:
    [{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    messages = []

    # System prompt
    system_parts = [SYSTEM_PROMPT]

    if context.system_notes:
        system_parts.append("\n## Query Analysis")
        for note in context.system_notes:
            system_parts.append(f"- {note}")

    messages.append({
        "role": "system",
        "content": "\n".join(system_parts),
    })

    # Conversation history (if multi-turn)
    if conversation_history:
        # Only include last few turns to stay within budget
        for turn in conversation_history[-4:]:
            messages.append(turn)

    # User message with context
    user_parts = []

    if context.product_context:
        user_parts.append(
            "<product_data>\n"
            f"{context.product_context}\n"
            "</product_data>\n"
        )

    if context.context_text:
        user_parts.append(
            "<source_documents>\n"
            f"{context.context_text}\n"
            "</source_documents>\n"
        )

    user_parts.append(
        f"<user_question>\n{query}\n</user_question>\n\n"
        "Answer based on the provided product data and source documents. "
        "Cite specific sources when referencing specifications."
    )

    messages.append({
        "role": "user",
        "content": "\n".join(user_parts),
    })

    return messages


# ============================================================
# Main Retrieval Pipeline
# ============================================================

class RAGPipeline:
    """
    End-to-end retrieval-augmented generation pipeline.
    Orchestrates: query → parse → retrieve → rerank → context → prompt
    """

    def __init__(
        self,
        vector_store: VectorStore,
        keyword_searcher: KeywordSearcher,
        embedder: EmbeddingProvider,
        product_repo: Any,
        spec_registry: Optional[dict[str, SpecRegistryEntry]] = None,
        config: RAGConfig = DEFAULT_RAG_CONFIG,
    ):
        self.vector_store = vector_store
        self.keyword_searcher = keyword_searcher
        self.embedder = embedder
        self.product_repo = product_repo
        self.spec_registry = spec_registry or {}
        self.config = config

    async def retrieve(
        self,
        query: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> tuple[RetrievalContext, list[dict[str, str]]]:
        """
        Full retrieval pipeline. Returns (context, prompt_messages).
        """
        start = time.monotonic()

        # Step 1: Parse query
        pq = parse_query(query, self.spec_registry)
        logger.info(
            f"Parsed query: intent={pq.intent}, "
            f"models={pq.model_numbers}, specs={pq.spec_mentions}")

        # Step 2: Embed query
        # Expand query with synonyms for better recall
        expanded_query = query
        if pq.expanded_terms:
            expanded_query = f"{query} {' '.join(pq.expanded_terms[:5])}"
        query_vec = await self.embedder.embed_query(expanded_query)

        # Step 3: Vector search
        vector_filters = {}
        if pq.brand_mentions:
            vector_filters['brands'] = pq.brand_mentions

        # Chunk type filter based on intent
        if pq.intent == 'spec_lookup':
            vector_filters['chunk_types'] = [
                'spec_block', 'performance_data', 'dimensional', 'text']
        elif pq.intent == 'compare':
            vector_filters['chunk_types'] = [
                'spec_block', 'performance_data', 'description']

        vector_results = await self.vector_store.search(
            query_vec, top_k=self.config.vector_top_k,
            filters=vector_filters if vector_filters else None,
        )

        # Step 4: Keyword search
        keyword_results = self.keyword_searcher.search(
            query, top_k=self.config.keyword_top_k,
            filters=vector_filters if vector_filters else None,
        )

        # Step 5: Hybrid fusion
        fused = reciprocal_rank_fusion(
            vector_results, keyword_results,
            vector_weight=self.config.vector_weight,
            keyword_weight=self.config.keyword_weight,
        )

        # Step 6: Re-rank
        if self.config.use_cross_encoder:
            # In production: call cross-encoder model
            reranked = fused[:self.config.final_top_k]
        else:
            reranked = heuristic_rerank(fused, pq, self.config)
            reranked = reranked[:self.config.final_top_k]

        # Step 7: Fetch referenced products
        products = []
        if pq.model_numbers:
            for model in pq.model_numbers:
                p = await self._get_product(model)
                if p:
                    products.append(p)

        # Also fetch products referenced by top chunks
        seen_pids: set[str] = {str(p.id) for p in products}
        for sc in reranked[:5]:
            for pid in (sc.chunk.product_ids or []):
                if str(pid) not in seen_pids:
                    p = await self._get_product_by_id(pid)
                    if p:
                        products.append(p)
                        seen_pids.add(str(pid))

        # Step 8: Build context
        context = build_context(
            reranked, pq, products, self.config)

        # Step 9: Build prompt
        messages = build_prompt(query, context, conversation_history)

        elapsed = int((time.monotonic() - start) * 1000)
        logger.info(
            f"RAG retrieval: {len(reranked)} chunks, "
            f"{context.total_tokens} tokens, {elapsed}ms")

        return context, messages

    async def index_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Index chunks into both vector and keyword stores."""
        count = 0
        for chunk in chunks:
            # Embed and store in vector store
            vec = await self.embedder.embed_document(chunk.content)
            await self.vector_store.upsert(chunk.id, vec)

            # Index in keyword store
            if isinstance(self.vector_store, InMemoryVectorStore):
                self.vector_store.register_chunk(chunk)
            self.keyword_searcher.index_chunk(chunk)
            count += 1

        return count

    async def _get_product(self, model: str) -> Optional[Product]:
        if hasattr(self.product_repo, 'get_product_by_model'):
            return await self.product_repo.get_product_by_model(model)
        return None

    async def _get_product_by_id(self, pid: UUID) -> Optional[Product]:
        if hasattr(self.product_repo, 'products'):
            return self.product_repo.products.get(pid)
        return None


# ============================================================
# Grounding Validator
# ============================================================

class GroundingValidator:
    """
    Post-generation validation to check that LLM responses
    are grounded in the retrieved context.
    """

    @staticmethod
    def validate_response(
        response_text: str,
        context: RetrievalContext,
        products: list[Product],
    ) -> dict[str, Any]:
        """
        Check response for potential hallucinations.
        Returns validation report.
        """
        report = {
            'grounded': True,
            'warnings': [],
            'spec_claims': [],
            'ungrounded_claims': [],
        }

        # Extract numeric claims from response
        num_claims = re.findall(
            r'(\d+\.?\d*)\s*(cu\.?\s*ft|°[CF]|kWh|dBA|lbs|kg|inches?|in\b|amps?|V\b|Hz|watts?|W\b)',
            response_text, re.IGNORECASE
        )

        context_text = context.context_text.lower()
        product_text = (context.product_context or '').lower()
        all_context = f"{context_text} {product_text}"

        for val, unit in num_claims:
            claim = f"{val} {unit}"
            # Check if this value appears in context
            if val in all_context:
                report['spec_claims'].append({
                    'claim': claim, 'grounded': True})
            else:
                # Check against product specs
                found = False
                for p in products:
                    for attr in ['storage_capacity_cuft', 'temp_range_min_c',
                                 'temp_range_max_c', 'amperage', 'voltage_v',
                                 'product_weight_lbs', 'ext_width_in',
                                 'ext_depth_in', 'ext_height_in']:
                        pval = getattr(p, attr, None)
                        if pval is not None and str(pval) == val:
                            found = True
                            break
                    if not found:
                        for sv in p.specs.values():
                            if str(sv) == val:
                                found = True
                                break
                    if found:
                        break

                if found:
                    report['spec_claims'].append({
                        'claim': claim, 'grounded': True})
                else:
                    report['grounded'] = False
                    report['ungrounded_claims'].append(claim)
                    report['warnings'].append(
                        f"Claim '{claim}' not found in retrieved context")

        # Check for model numbers not in context
        for pat in _MODEL_PATTERNS:
            for m in re.finditer(pat, response_text):
                model = m.group(1)
                if model.lower() not in all_context:
                    report['grounded'] = False
                    report['warnings'].append(
                        f"Model '{model}' mentioned but not in context")

        return report


# ============================================================
# Example / Integration Test
# ============================================================

async def _example():
    """Demonstrate the RAG pipeline."""
    from ingestion_orchestrator import InMemoryRepository
    from models import SuperCategory

    # Setup
    repo = InMemoryRepository()
    repo.brands['ABS'] = Brand(code='ABS', name='American BioTech Supply')
    repo.families['premier_lab_ref'] = ProductFamily(
        code='premier_lab_ref', name='Premier Lab',
        super_category=SuperCategory.REFRIGERATOR)

    # Create a product
    product = Product(
        model_number='ABT-HC-26S',
        brand_id=repo.brands['ABS'].id,
        family_id=repo.families['premier_lab_ref'].id,
        product_line='Premier',
        storage_capacity_cuft=26.0,
        temp_range_min_c=1.0, temp_range_max_c=10.0,
        door_count=1, door_type='solid', shelf_count=4,
        refrigerant='R290', voltage_v=115, amperage=3.0,
        product_weight_lbs=235.0,
        ext_width_in=28.375, ext_depth_in=36.75, ext_height_in=81.75,
        certifications=['ETL', 'C-ETL', 'UL471', 'Energy_Star'],
        specs={
            'uniformity_c': 1.4, 'stability_c': 1.3,
            'energy_kwh_day': 1.15, 'noise_dba': 41,
            'product_type': 'refrigerator',
            'defrost_type': 'cycle',
        },
    )
    repo.products[product.id] = product
    repo._model_index['ABT-HC-26S'] = product.id

    # Create document chunks
    chunks = [
        DocumentChunk(
            document_id=uuid4(), chunk_index=0,
            content="The ABT-HC-26S Premier Laboratory Refrigerator provides "
                    "26 cu.ft. of storage capacity with a temperature range of "
                    "1°C to 10°C. Features include a solid door with self-closing "
                    "mechanism and four adjustable shelves.",
            chunk_type='description',
            section_title='General Description',
            product_ids=[product.id],
            spec_names=['storage_capacity_cuft', 'temp_range_min_c', 'door_type'],
            metadata={'doc_type': 'product_data_sheet', 'brand': 'ABS'},
            token_count=60,
        ),
        DocumentChunk(
            document_id=uuid4(), chunk_index=1,
            content="Refrigeration System: Hermetic compressor, R290 hydrocarbon "
                    "natural refrigerant (EPA SNAP compliant). Static exterior wall "
                    "condenser, fin and tube evaporator. Cycle defrost.",
            chunk_type='spec_block',
            section_title='Refrigeration System',
            product_ids=[product.id],
            spec_names=['refrigerant', 'compressor_type', 'defrost_type'],
            metadata={'doc_type': 'product_data_sheet', 'brand': 'ABS'},
            token_count=45,
        ),
        DocumentChunk(
            document_id=uuid4(), chunk_index=2,
            content="Temperature Performance: Cabinet air uniformity ±1.4°C, "
                    "stability ±1.3°C. Energy consumption 1.15 kWh/day. "
                    "Noise pressure level 41 dBA or less. Pull down time to "
                    "nominal operating temp: 35 minutes.",
            chunk_type='performance_data',
            section_title='Performance',
            product_ids=[product.id],
            spec_names=['uniformity_c', 'stability_c', 'energy_kwh_day', 'noise_dba'],
            metadata={'doc_type': 'product_data_sheet', 'brand': 'ABS'},
            token_count=50,
        ),
        DocumentChunk(
            document_id=uuid4(), chunk_index=3,
            content="Exterior Dimensions: 28 3/8\" W × 36 3/4\" D × 81 3/4\" H. "
                    "Interior: 23 3/4\" W × 28\" D × 52 1/4\" H. "
                    "Door swing: 26 3/8\". Total open depth: 63 1/8\". "
                    "Product weight: 235 lbs. Shipping weight: 275 lbs.",
            chunk_type='dimensional',
            section_title='Dimensions',
            product_ids=[product.id],
            spec_names=['ext_width_in', 'ext_depth_in', 'ext_height_in'],
            metadata={'doc_type': 'product_data_sheet', 'brand': 'ABS'},
            token_count=55,
        ),
        DocumentChunk(
            document_id=uuid4(), chunk_index=4,
            content="Controller: Microprocessor with LED display, 0.1°C resolution. "
                    "RS-485 MODBUS digital communication. Alarms include high/low "
                    "temperature, power failure, door ajar, sensor error. "
                    "USB data transfer for CSV/PDF export.",
            chunk_type='spec_block',
            section_title='Controller',
            product_ids=[product.id],
            spec_names=['controller_type', 'display_type', 'digital_comm'],
            metadata={'doc_type': 'product_data_sheet', 'brand': 'ABS'},
            token_count=50,
        ),
    ]

    # Initialize pipeline components
    vec_store = InMemoryVectorStore()
    kw_searcher = KeywordSearcher()
    embedder = EmbeddingProvider()

    pipeline = RAGPipeline(
        vector_store=vec_store,
        keyword_searcher=kw_searcher,
        embedder=embedder,
        product_repo=repo,
    )

    # Index chunks
    indexed = await pipeline.index_chunks(chunks)
    print(f"Indexed {indexed} chunks\n")

    # --- Test 1: Spec lookup ---
    print("=" * 60)
    print("TEST 1: What is the energy consumption of the ABT-HC-26S?")
    print("=" * 60)

    ctx, messages = await pipeline.retrieve(
        "What is the energy consumption of the ABT-HC-26S?"
    )

    print(f"Retrieved {len(ctx.chunks)} chunks, {ctx.total_tokens} tokens")
    print(f"\nSystem notes:")
    for n in ctx.system_notes:
        print(f"  - {n}")
    print(f"\nTop chunks:")
    for sc in ctx.chunks[:3]:
        print(f"  [{sc.chunk.chunk_type}] {sc.chunk.section_title}: "
              f"score={sc.score:.3f}, source={sc.source}")
        print(f"    {sc.chunk.content[:100]}...")
    print(f"\nCitations: {len(ctx.citations)}")
    for c in ctx.citations[:3]:
        print(f"  Section: {c.section}, Snippet: {c.snippet[:80]}...")

    print(f"\nPrompt messages: {len(messages)}")
    for m in messages:
        role = m['role']
        content = m['content'][:200]
        print(f"  [{role}] {content}...")

    # --- Test 2: Dimension query ---
    print("\n" + "=" * 60)
    print("TEST 2: How tall is the ABT-HC-26S?")
    print("=" * 60)

    ctx2, msgs2 = await pipeline.retrieve(
        "How tall is the ABT-HC-26S? Will it fit under a 7-foot ceiling?"
    )
    print(f"Retrieved {len(ctx2.chunks)} chunks")
    print(f"Top chunk type: {ctx2.chunks[0].chunk.chunk_type if ctx2.chunks else 'none'}")

    # --- Test 3: General query without model ---
    print("\n" + "=" * 60)
    print("TEST 3: What refrigerant options are available?")
    print("=" * 60)

    ctx3, msgs3 = await pipeline.retrieve(
        "What refrigerant options do you have for lab refrigerators?"
    )
    print(f"Retrieved {len(ctx3.chunks)} chunks")
    print(f"Spec mentions detected: {parse_query('What refrigerant options do you have?').spec_mentions}")

    # --- Test 4: Grounding validation ---
    print("\n" + "=" * 60)
    print("TEST 4: Grounding Validation")
    print("=" * 60)

    # Good response (grounded)
    good_resp = ("The ABT-HC-26S has an energy consumption of 1.15 kWh/day "
                 "and a noise level of 41 dBA.")
    report = GroundingValidator.validate_response(good_resp, ctx, [product])
    print(f"Good response grounded: {report['grounded']}")
    print(f"  Claims: {report['spec_claims']}")

    # Bad response (hallucinated)
    bad_resp = ("The ABT-HC-26S consumes only 0.8 kWh/day, making it the most "
                "efficient model. The ABT-HC-99X is also available.")
    report2 = GroundingValidator.validate_response(bad_resp, ctx, [product])
    print(f"\nBad response grounded: {report2['grounded']}")
    print(f"  Warnings: {report2['warnings']}")
    print(f"  Ungrounded: {report2['ungrounded_claims']}")

    # --- Test 5: Query parsing ---
    print("\n" + "=" * 60)
    print("TEST 5: Query Parsing Examples")
    print("=" * 60)

    queries = [
        "I need a vaccine storage refrigerator with NSF 456 certification",
        "Compare ABT-HC-26S vs ABT-HC-26G",
        "What is the uniformity and stability of the PH-ABT-NSF-UCFS-0504?",
        "Do you have an energy star certified flammable storage fridge under 36 inches?",
        "The alarm keeps going off on my LABRepCo freezer",
    ]
    for q in queries:
        pq = parse_query(q)
        print(f"\n  Q: {q}")
        print(f"    Intent: {pq.intent}")
        print(f"    Models: {pq.model_numbers}")
        print(f"    Specs: {pq.spec_mentions}")
        print(f"    Brands: {pq.brand_mentions}")
        print(f"    Certs: {pq.cert_mentions}")
        print(f"    Families: {pq.family_hints}")
        print(f"    Filters: {pq.filters}")


if __name__ == '__main__':
    import asyncio
    asyncio.run(_example())
