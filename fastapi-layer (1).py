"""
Product Expert System — FastAPI Application Layer
007_api_layer.py

Endpoints:
  1. POST /recommend        — Product recommendation
  2. POST /compare          — Side-by-side comparison
  3. POST /ask              — RAG-powered Q&A
  4. POST /ingest           — Document ingestion
  5. GET  /products/{model} — Product lookup
  6. GET  /products         — Product search/list
  7. GET  /conflicts        — Spec conflict queue
  8. PUT  /conflicts/{id}   — Resolve a conflict
  9. GET  /health           — Health check
  10. GET /stats            — System statistics

Auth: API key header + role-based access control
"""
from __future__ import annotations
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import (
    FastAPI, HTTPException, Depends, Header, Query,
    UploadFile, File, BackgroundTasks, Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from models import (
    Product, Document, SpecConflict,
    RecommendRequest, RecommendResponse,
    CompareRequest, CompareResponse,
    IngestRequest, IngestResponse,
    HealthResponse, ProductStatus,
    ConflictResolution, ConflictSeverity,
    UserRole, Brand, ProductFamily,
    Citation, DecisionTrace, ProductRecommendation,
)
from ingestion_orchestrator import (
    IngestionOrchestrator, IngestionConfig, InMemoryRepository,
    ProductRepository, IngestionStats,
)
from recommendation_engine import (
    RecommendationEngine, USE_CASE_PROFILES,
)
from rag_retrieval import (
    RAGPipeline, RAGConfig, InMemoryVectorStore,
    KeywordSearcher, EmbeddingProvider, GroundingValidator,
    parse_query,
)

logger = logging.getLogger(__name__)

# ============================================================
# App Configuration
# ============================================================

class AppConfig(BaseModel):
    app_name: str = "Product Expert System"
    version: str = "1.0.0"
    environment: str = "development"
    api_key_header: str = "X-API-Key"
    cors_origins: list[str] = ["*"]
    max_upload_size_mb: int = 50
    max_batch_files: int = 100
    log_level: str = "INFO"


def load_config() -> AppConfig:
    return AppConfig(
        environment=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


# ============================================================
# Application State (shared singletons)
# ============================================================

class AppState:
    """Holds all shared service instances."""
    config: AppConfig
    repo: ProductRepository
    ingestion: IngestionOrchestrator
    recommender: RecommendationEngine
    rag: RAGPipeline
    start_time: float
    request_count: int = 0

    def __init__(self):
        self.start_time = time.monotonic()
        self.request_count = 0


_state = AppState()


# ============================================================
# Lifespan: Startup / Shutdown
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    logger.info("Starting Product Expert System...")

    cfg = load_config()
    _state.config = cfg

    # --- Repository ---
    # In production: asyncpg pool, SQLAlchemy async session
    repo = InMemoryRepository()
    _seed_reference_data(repo)
    _state.repo = repo

    # --- Ingestion ---
    _state.ingestion = IngestionOrchestrator(repo, IngestionConfig())

    # --- Recommendation ---
    _state.recommender = RecommendationEngine(repo)

    # --- RAG ---
    vec_store = InMemoryVectorStore()
    kw_searcher = KeywordSearcher()
    embedder = EmbeddingProvider()
    _state.rag = RAGPipeline(
        vector_store=vec_store,
        keyword_searcher=kw_searcher,
        embedder=embedder,
        product_repo=repo,
    )

    logger.info(f"System ready. Environment: {cfg.environment}")
    yield

    # Shutdown
    logger.info("Shutting down Product Expert System...")


def _seed_reference_data(repo: InMemoryRepository):
    """Seed brands and families into the in-memory repo."""
    from models import SuperCategory
    brands = [
        ('ABS', 'American BioTech Supply', 'Horizon Scientific'),
        ('LABRepCo', 'LABRepCo', 'Horizon Scientific'),
        ('Corepoint', 'Corepoint Scientific', 'Horizon Scientific'),
        ('Celsius', '°celsius Scientific', 'Horizon Scientific'),
        ('CBS', 'CBS / CryoSafe', 'Horizon Scientific'),
    ]
    for code, name, parent in brands:
        repo.brands[code] = Brand(code=code, name=name, parent_org=parent)

    families = [
        ('premier_lab_ref', 'Premier Laboratory Refrigerator', 'refrigerator'),
        ('standard_lab_ref', 'Standard Laboratory Refrigerator', 'refrigerator'),
        ('chromatography_ref', 'Chromatography Refrigerator', 'refrigerator'),
        ('pharmacy_vaccine_ref', 'Pharmacy/Vaccine Refrigerator', 'refrigerator'),
        ('pharmacy_nsf_ref', 'Pharmacy/Vaccine NSF Certified', 'refrigerator'),
        ('flammable_storage_ref', 'Flammable Material Storage', 'refrigerator'),
        ('blood_bank_ref', 'Blood Bank Refrigerator', 'refrigerator'),
        ('manual_defrost_freezer', 'Manual Defrost Freezer', 'freezer'),
        ('auto_defrost_freezer', 'Auto Defrost Freezer', 'freezer'),
        ('precision_freezer', 'Precision Series Freezer', 'freezer'),
        ('ultra_low_freezer', 'Ultra-Low Freezer', 'freezer'),
        ('plasma_freezer', 'Plasma Storage Freezer', 'freezer'),
        ('cryo_dewar', 'Cryogenic Dewar', 'cryogenic'),
        ('vapor_shipper', 'Vapor Shipper', 'cryogenic'),
        ('cryo_freezer', 'CryoMizer Freezer', 'cryogenic'),
        ('accessory', 'Accessory', 'accessory'),
    ]
    for code, name, cat in families:
        repo.families[code] = ProductFamily(
            code=code, name=name,
            super_category=SuperCategory(cat) if cat != 'accessory'
            else SuperCategory.ACCESSORY,
        )


# ============================================================
# Auth & Dependencies
# ============================================================

# Simple API key → user role mapping (in production: JWT/OAuth2)
_API_KEYS: dict[str, dict[str, Any]] = {
    "dev-key-001": {"user_id": "dev@test.com", "role": UserRole.ADMIN, "name": "Dev User"},
    "sales-key-001": {"user_id": "sales@corp.com", "role": UserRole.SALES_ENGINEER, "name": "Sales Eng"},
    "customer-key-001": {"user_id": "cust@lab.com", "role": UserRole.CUSTOMER, "name": "Lab Manager"},
}


class AuthContext(BaseModel):
    user_id: str
    role: UserRole
    name: str
    api_key: str


async def get_auth(
    x_api_key: str = Header(None, alias="X-API-Key"),
) -> AuthContext:
    """Validate API key and return auth context."""
    if not x_api_key:
        # Development mode: allow unauthenticated
        if _state.config.environment == "development":
            return AuthContext(
                user_id="dev@anon", role=UserRole.ADMIN,
                name="Anonymous Dev", api_key="none",
            )
        raise HTTPException(401, "Missing X-API-Key header")

    user = _API_KEYS.get(x_api_key)
    if not user:
        raise HTTPException(403, "Invalid API key")

    return AuthContext(
        user_id=user["user_id"], role=user["role"],
        name=user["name"], api_key=x_api_key,
    )


def require_role(*roles: UserRole):
    """Dependency factory for role-based access control."""
    async def check(auth: AuthContext = Depends(get_auth)):
        if auth.role not in roles:
            raise HTTPException(
                403, f"Requires role: {[r.value for r in roles]}")
        return auth
    return check


# ============================================================
# Request/Response Models (API-specific)
# ============================================================

class AskRequest(BaseModel):
    question: str
    model_numbers: list[str] = Field(default_factory=list)
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    include_citations: bool = True
    max_context_chunks: int = 8


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    grounding_report: Optional[dict[str, Any]] = None
    products_referenced: list[str] = Field(default_factory=list)
    query_analysis: dict[str, Any] = Field(default_factory=dict)
    response_time_ms: int = 0


class ProductResponse(BaseModel):
    model_number: str
    brand: str
    family: str
    product_line: Optional[str] = None
    status: str
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
    certifications: list[str] = Field(default_factory=list)
    specs: dict[str, Any] = Field(default_factory=dict)
    revision: Optional[str] = None
    version: int = 1


class ProductListResponse(BaseModel):
    products: list[ProductResponse]
    total: int
    page: int = 1
    page_size: int = 25


class ConflictResponse(BaseModel):
    id: str
    product_model: str
    spec_name: str
    existing_value: Optional[str]
    new_value: Optional[str]
    severity: str
    resolution: str
    source_doc: Optional[str] = None
    created_at: Optional[str] = None


class ConflictResolveRequest(BaseModel):
    resolution: str  # keep_existing, accept_new, manual_override
    override_value: Optional[str] = None
    notes: Optional[str] = None


class StatsResponse(BaseModel):
    total_products: int
    total_documents: int
    total_chunks: int
    pending_conflicts: int
    brands: dict[str, int]
    families: dict[str, int]
    uptime_seconds: int
    request_count: int


class UseCaseListResponse(BaseModel):
    use_cases: list[dict[str, Any]]


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="Product Expert System API",
    description="AI-powered product recommendation, comparison, and Q&A for "
                "laboratory, pharmacy, and vaccine storage equipment.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Middleware: Request Counting & Timing
# ============================================================

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.monotonic()
    _state.request_count += 1
    response = await call_next(request)
    elapsed = int((time.monotonic() - start) * 1000)
    response.headers["X-Response-Time-Ms"] = str(elapsed)
    return response


# ============================================================
# 1. POST /recommend — Product Recommendation
# ============================================================

@app.post("/recommend", response_model=RecommendResponse, tags=["Recommendations"])
async def recommend_products(
    request: RecommendRequest,
    auth: AuthContext = Depends(get_auth),
):
    """
    Get product recommendations based on use case, specs, and constraints.

    Supports:
    - use_case: predefined profile (e.g., 'vaccine_storage', 'chromatography')
    - free_text: natural language description
    - structured_specs: explicit spec requirements
    - constraints: hard must-match criteria
    - preferences: weighted soft preferences
    """
    try:
        response = await _state.recommender.recommend(request)

        # Audit log (production: write to audit_log table)
        logger.info(
            f"[recommend] user={auth.user_id} use_case={request.use_case} "
            f"results={len(response.products)} time={response.response_time_ms}ms")

        return response
    except Exception as e:
        logger.exception("Recommendation failed")
        raise HTTPException(500, f"Recommendation error: {str(e)}")


# ============================================================
# 2. POST /compare — Side-by-Side Comparison
# ============================================================

@app.post("/compare", response_model=CompareResponse, tags=["Recommendations"])
async def compare_products(
    request: CompareRequest,
    auth: AuthContext = Depends(get_auth),
):
    """
    Compare 2+ products side by side.
    Optionally provide user_constraints to score suitability.
    """
    if len(request.product_ids) < 2:
        raise HTTPException(400, "At least 2 product IDs required")
    if len(request.product_ids) > 10:
        raise HTTPException(400, "Maximum 10 products for comparison")

    try:
        response = await _state.recommender.compare(request)
        return response
    except Exception as e:
        logger.exception("Comparison failed")
        raise HTTPException(500, f"Comparison error: {str(e)}")


# ============================================================
# 3. POST /ask — RAG-Powered Q&A
# ============================================================

@app.post("/ask", response_model=AskResponse, tags=["Q&A"])
async def ask_question(
    request: AskRequest,
    auth: AuthContext = Depends(get_auth),
):
    """
    Ask a question about products, specs, or applications.
    Uses RAG to ground answers in source documents.

    Returns answer with citations and grounding validation report.
    """
    start = time.monotonic()

    if not request.question.strip():
        raise HTTPException(400, "Question cannot be empty")
    if len(request.question) > 2000:
        raise HTTPException(400, "Question too long (max 2000 chars)")

    try:
        # Parse query for analysis
        pq = parse_query(request.question)

        # Retrieve context
        ctx, messages = await _state.rag.retrieve(
            request.question,
            conversation_history=request.conversation_history or None,
        )

        # In production: call LLM with messages
        # For now, build a mock response from context
        answer = _build_mock_answer(request.question, ctx, pq)

        # Collect referenced products
        products_ref = []
        for sc in ctx.chunks:
            for pid in sc.chunk.product_ids:
                p = _state.repo.products.get(pid)
                if p and p.model_number not in products_ref:
                    products_ref.append(p.model_number)

        # Grounding validation
        products_for_validation = [
            _state.repo.products[pid]
            for sc in ctx.chunks
            for pid in sc.chunk.product_ids
            if pid in _state.repo.products
        ]
        grounding = GroundingValidator.validate_response(
            answer, ctx, products_for_validation)

        elapsed = int((time.monotonic() - start) * 1000)

        return AskResponse(
            answer=answer,
            citations=ctx.citations if request.include_citations else [],
            grounding_report=grounding,
            products_referenced=products_ref,
            query_analysis={
                'intent': pq.intent,
                'model_numbers': pq.model_numbers,
                'spec_mentions': pq.spec_mentions,
                'brand_mentions': pq.brand_mentions,
                'expanded_terms': pq.expanded_terms[:5],
            },
            response_time_ms=elapsed,
        )
    except Exception as e:
        logger.exception("Q&A failed")
        raise HTTPException(500, f"Q&A error: {str(e)}")


def _build_mock_answer(question: str, ctx, pq) -> str:
    """
    Mock answer builder for development.
    In production, replaced by LLM call with ctx.context_text.
    """
    if not ctx.chunks:
        return ("I don't have enough information in my sources to answer "
                "that question. Could you provide more details or specify "
                "a model number?")

    # Build answer from top chunks
    parts = []
    if pq.model_numbers:
        parts.append(f"Regarding the {', '.join(pq.model_numbers)}:")

    for sc in ctx.chunks[:3]:
        content = sc.chunk.content
        if len(content) > 300:
            content = content[:300] + "..."
        parts.append(content)

    if ctx.citations:
        parts.append(f"\n(Based on {len(ctx.citations)} source document(s))")

    return "\n\n".join(parts)


# ============================================================
# 4. POST /ingest — Document Ingestion
# ============================================================

@app.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def ingest_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    auth: AuthContext = Depends(
        require_role(UserRole.PRODUCT_MANAGER, UserRole.ADMIN)),
):
    """
    Upload and ingest product documents (PDF, TXT, MD).
    Processing happens in background. Returns job ID for polling.

    Requires: product_manager or admin role.
    """
    if len(files) > _state.config.max_batch_files:
        raise HTTPException(
            400, f"Max {_state.config.max_batch_files} files per batch")

    max_bytes = _state.config.max_upload_size_mb * 1024 * 1024
    file_infos = []
    validation_issues = []

    for f in files:
        content = await f.read()
        if len(content) > max_bytes:
            validation_issues.append(
                f"{f.filename}: exceeds {_state.config.max_upload_size_mb}MB limit")
            continue
        if not f.filename:
            validation_issues.append("File missing filename")
            continue

        allowed = {'.pdf', '.txt', '.md', '.html', '.json'}
        ext = '.' + f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
        if ext not in allowed:
            validation_issues.append(
                f"{f.filename}: unsupported format (allowed: {allowed})")
            continue

        file_infos.append({
            'filename': f.filename,
            'content': content,
            'mime_type': f.content_type or 'application/octet-stream',
        })

    if not file_infos:
        raise HTTPException(400, "No valid files to ingest")

    job_id = str(uuid4())

    # Background processing
    background_tasks.add_task(
        _run_ingestion, job_id, file_infos, auth.user_id)

    return IngestResponse(
        job_id=job_id,
        status="queued",
        files_accepted=len(file_infos),
        validation_issues=validation_issues,
        estimated_completion_minutes=max(1, len(file_infos) // 10),
    )


async def _run_ingestion(
    job_id: str, files: list[dict], user_id: str
):
    """Background task for document ingestion."""
    try:
        job_uuid, stats = await _state.ingestion.ingest_batch(
            files, submitted_by=user_id)

        # Index new chunks in RAG
        if hasattr(_state.repo, 'chunks'):
            indexed = await _state.rag.index_chunks(_state.repo.chunks)
            logger.info(f"Indexed {indexed} chunks for RAG")

        logger.info(
            f"[ingest] job={job_id} processed={stats.processed_files} "
            f"new={stats.new_products} updated={stats.updated_products} "
            f"conflicts={stats.conflicts_found}")
    except Exception as e:
        logger.exception(f"Ingestion job {job_id} failed: {e}")


# ============================================================
# 5. GET /products/{model} — Product Lookup
# ============================================================

@app.get("/products/{model_number}", response_model=ProductResponse,
         tags=["Products"])
async def get_product(
    model_number: str,
    auth: AuthContext = Depends(get_auth),
):
    """Look up a product by model number."""
    product = await _state.repo.get_product_by_model(model_number)
    if not product:
        raise HTTPException(404, f"Product not found: {model_number}")
    return _product_to_response(product)


# ============================================================
# 6. GET /products — Product Search / List
# ============================================================

@app.get("/products", response_model=ProductListResponse, tags=["Products"])
async def list_products(
    brand: Optional[str] = Query(None, description="Filter by brand code"),
    family: Optional[str] = Query(None, description="Filter by family code"),
    product_type: Optional[str] = Query(None, description="refrigerator|freezer|cryogenic"),
    min_capacity: Optional[float] = Query(None, description="Min capacity cu.ft."),
    max_capacity: Optional[float] = Query(None, description="Max capacity cu.ft."),
    door_type: Optional[str] = Query(None, description="solid|glass|glass_sliding"),
    refrigerant: Optional[str] = Query(None, description="R290|R600a|R134a"),
    certification: Optional[str] = Query(None, description="Filter by certification"),
    search: Optional[str] = Query(None, description="Full-text search"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    auth: AuthContext = Depends(get_auth),
):
    """
    Search and filter products.
    Supports filtering by brand, family, specs, certifications, and free text.
    """
    # In production: SQL query with WHERE + pagination
    all_products = list(_state.repo.products.values())
    filtered = []

    for p in all_products:
        if p.status in (ProductStatus.DEPRECATED.value, 'deprecated'):
            continue

        if brand:
            b = _state.repo.brands.get(brand)
            if b and p.brand_id != b.id:
                continue

        if family:
            f = _state.repo.families.get(family)
            if f and p.family_id != f.id:
                continue

        if product_type:
            pt = p.specs.get('product_type')
            if pt and pt != product_type:
                continue

        if min_capacity and p.storage_capacity_cuft:
            if p.storage_capacity_cuft < min_capacity:
                continue

        if max_capacity and p.storage_capacity_cuft:
            if p.storage_capacity_cuft > max_capacity:
                continue

        if door_type and p.door_type:
            if p.door_type != door_type:
                continue

        if refrigerant and p.refrigerant:
            if p.refrigerant.upper() != refrigerant.upper():
                continue

        if certification:
            if certification not in p.certifications:
                continue

        if search:
            haystack = f"{p.model_number} {p.product_line or ''} {p.description or ''}".lower()
            if search.lower() not in haystack:
                continue

        filtered.append(p)

    # Pagination
    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start:start + page_size]

    return ProductListResponse(
        products=[_product_to_response(p) for p in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================
# 7. GET /conflicts — Spec Conflict Queue
# ============================================================

@app.get("/conflicts", response_model=list[ConflictResponse],
         tags=["Conflicts"])
async def list_conflicts(
    severity: Optional[str] = Query(None, description="low|medium|high|critical"),
    status: Optional[str] = Query("pending", description="pending|keep_existing|accept_new"),
    limit: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(
        require_role(UserRole.PRODUCT_MANAGER, UserRole.ADMIN)),
):
    """List pending spec conflicts for review."""
    conflicts = getattr(_state.repo, 'conflicts', [])
    filtered = []

    for c in conflicts:
        if status and c.resolution.value != status:
            continue
        if severity and c.severity.value != severity:
            continue
        filtered.append(c)

    results = []
    for c in filtered[:limit]:
        # Resolve product model number
        product_model = "unknown"
        for p in _state.repo.products.values():
            if p.id == c.product_id:
                product_model = p.model_number
                break

        results.append(ConflictResponse(
            id=str(c.id),
            product_model=product_model,
            spec_name=c.spec_name,
            existing_value=c.existing_value,
            new_value=c.new_value,
            severity=c.severity.value,
            resolution=c.resolution.value,
            source_doc=str(c.source_doc_id) if c.source_doc_id else None,
        ))

    return results


# ============================================================
# 8. PUT /conflicts/{id} — Resolve a Conflict
# ============================================================

@app.put("/conflicts/{conflict_id}", tags=["Conflicts"])
async def resolve_conflict(
    conflict_id: str,
    request: ConflictResolveRequest,
    auth: AuthContext = Depends(
        require_role(UserRole.PRODUCT_MANAGER, UserRole.ADMIN)),
):
    """
    Resolve a spec conflict.
    Options: keep_existing, accept_new, manual_override (with override_value).
    """
    valid = {'keep_existing', 'accept_new', 'manual_override', 'dismissed'}
    if request.resolution not in valid:
        raise HTTPException(400, f"Invalid resolution. Must be one of: {valid}")

    if request.resolution == 'manual_override' and not request.override_value:
        raise HTTPException(400, "manual_override requires override_value")

    # Find conflict
    conflict = None
    for c in getattr(_state.repo, 'conflicts', []):
        if str(c.id) == conflict_id:
            conflict = c
            break

    if not conflict:
        raise HTTPException(404, f"Conflict not found: {conflict_id}")

    # Apply resolution
    resolution_map = {
        'keep_existing': ConflictResolution.KEEP_EXISTING,
        'accept_new': ConflictResolution.ACCEPT_NEW,
        'manual_override': ConflictResolution.MANUAL,
        'dismissed': ConflictResolution.DISMISSED,
    }
    conflict.resolution = resolution_map[request.resolution]

    # If accepting new or manual override, update the product
    if request.resolution in ('accept_new', 'manual_override'):
        product = _state.repo.products.get(conflict.product_id)
        if product:
            new_val = (request.override_value
                       if request.resolution == 'manual_override'
                       else conflict.new_value)
            _apply_spec_to_product(product, conflict.spec_name, new_val)
            product.version += 1
            await _state.repo.update_product(product)

    logger.info(
        f"[conflict] resolved={conflict_id} resolution={request.resolution} "
        f"by={auth.user_id}")

    return {"status": "resolved", "conflict_id": conflict_id,
            "resolution": request.resolution}


def _apply_spec_to_product(product: Product, spec_name: str, value: Any):
    """Apply a spec value to a product (fixed column or dynamic)."""
    from ingestion_orchestrator import PRODUCT_FIXED_COLUMNS
    if spec_name in PRODUCT_FIXED_COLUMNS:
        col = PRODUCT_FIXED_COLUMNS[spec_name]
        # Type coercion
        try:
            if col in ('door_count', 'shelf_count', 'voltage_v'):
                value = int(value)
            elif col in ('storage_capacity_cuft', 'amperage', 'product_weight_lbs',
                         'temp_range_min_c', 'temp_range_max_c',
                         'ext_width_in', 'ext_depth_in', 'ext_height_in'):
                value = float(value)
        except (ValueError, TypeError):
            pass
        setattr(product, col, value)
    else:
        product.specs[spec_name] = value


# ============================================================
# 9. GET /health — Health Check
# ============================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """System health check."""
    uptime = int(time.monotonic() - _state.start_time)

    components = {
        "repository": {
            "status": "healthy",
            "products": len(getattr(_state.repo, 'products', {})),
            "documents": len(getattr(_state.repo, 'documents', {})),
        },
        "recommendation_engine": {"status": "healthy"},
        "rag_pipeline": {
            "status": "healthy",
            "indexed_chunks": len(getattr(_state.rag.keyword_searcher, 'chunks', {})),
        },
        "ingestion": {"status": "healthy"},
    }

    return HealthResponse(
        status="healthy",
        components=components,
        version=_state.config.version,
        uptime_seconds=uptime,
    )


# ============================================================
# 10. GET /stats — System Statistics
# ============================================================

@app.get("/stats", response_model=StatsResponse, tags=["System"])
async def system_stats(
    auth: AuthContext = Depends(
        require_role(UserRole.SALES_ENGINEER, UserRole.PRODUCT_MANAGER, UserRole.ADMIN)),
):
    """System statistics. Requires sales_engineer+ role."""
    products = list(_state.repo.products.values())

    # Brand distribution
    brand_counts: dict[str, int] = {}
    for p in products:
        for code, b in _state.repo.brands.items():
            if p.brand_id == b.id:
                brand_counts[code] = brand_counts.get(code, 0) + 1
                break

    # Family distribution
    family_counts: dict[str, int] = {}
    for p in products:
        for code, f in _state.repo.families.items():
            if p.family_id == f.id:
                family_counts[code] = family_counts.get(code, 0) + 1
                break

    pending = sum(
        1 for c in getattr(_state.repo, 'conflicts', [])
        if c.resolution == ConflictResolution.PENDING
    )

    return StatsResponse(
        total_products=len(products),
        total_documents=len(getattr(_state.repo, 'documents', {})),
        total_chunks=len(getattr(_state.repo, 'chunks', [])),
        pending_conflicts=pending,
        brands=brand_counts,
        families=family_counts,
        uptime_seconds=int(time.monotonic() - _state.start_time),
        request_count=_state.request_count,
    )


# ============================================================
# Bonus: GET /use-cases — List Available Use Cases
# ============================================================

@app.get("/use-cases", response_model=UseCaseListResponse, tags=["Recommendations"])
async def list_use_cases():
    """List all predefined use-case profiles for recommendation."""
    cases = []
    for key, profile in USE_CASE_PROFILES.items():
        cases.append({
            'key': key,
            'name': profile.name,
            'description': profile.description,
            'required_certifications': profile.required_certifications,
            'notes': profile.notes,
        })
    return UseCaseListResponse(use_cases=cases)


# ============================================================
# Bonus: GET /equivalents/{model} — Find Equivalent Products
# ============================================================

@app.get("/equivalents/{model_number}", tags=["Recommendations"])
async def find_equivalents(
    model_number: str,
    auth: AuthContext = Depends(get_auth),
):
    """Find products equivalent to the given model (cross-brand substitution)."""
    product = await _state.repo.get_product_by_model(model_number)
    if not product:
        raise HTTPException(404, f"Product not found: {model_number}")

    equivs = await _state.recommender.find_equivalents(product)

    return {
        "reference": model_number,
        "equivalents": [
            {
                "model_number": eq.model_number,
                "similarity": round(sim, 3),
                "capacity": eq.storage_capacity_cuft,
                "door_type": eq.door_type,
                "refrigerant": eq.refrigerant,
            }
            for eq, sim in equivs[:10]
        ],
    }


# ============================================================
# Helpers
# ============================================================

def _product_to_response(p: Product) -> ProductResponse:
    """Convert Product model to API response."""
    # Resolve brand and family names
    brand_name = ""
    for code, b in _state.repo.brands.items():
        if b.id == p.brand_id:
            brand_name = code
            break
    family_name = ""
    for code, f in _state.repo.families.items():
        if f.id == p.family_id:
            family_name = f.name
            break

    return ProductResponse(
        model_number=p.model_number,
        brand=brand_name,
        family=family_name,
        product_line=p.product_line,
        status=p.status.value if isinstance(p.status, ProductStatus) else str(p.status),
        storage_capacity_cuft=p.storage_capacity_cuft,
        temp_range_min_c=p.temp_range_min_c,
        temp_range_max_c=p.temp_range_max_c,
        door_count=p.door_count,
        door_type=p.door_type,
        shelf_count=p.shelf_count,
        refrigerant=p.refrigerant,
        voltage_v=p.voltage_v,
        amperage=p.amperage,
        product_weight_lbs=p.product_weight_lbs,
        ext_width_in=p.ext_width_in,
        ext_depth_in=p.ext_depth_in,
        ext_height_in=p.ext_height_in,
        certifications=p.certifications,
        specs={k: v for k, v in p.specs.items() if not k.startswith('_unknown_')},
        revision=p.revision,
        version=p.version,
    )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
