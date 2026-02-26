"""
asyncpg_repository.py — Production PostgreSQL repository implementation.

Implements the ProductRepository interface using asyncpg connection pool,
pgvector for similarity search, and PostgreSQL full-text search for BM25-style retrieval.
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import numpy as np

logger = logging.getLogger(__name__)

# ── Connection Pool Manager ──────────────────────────────────────────────────

class DatabasePool:
    """Manages asyncpg connection pool lifecycle."""

    def __init__(self, dsn: str, min_size: int = 5, max_size: int = 20):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """Create connection pool and install pgvector codec."""
        self._pool = await asyncpg.create_pool(
            self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
            command_timeout=30,
            init=self._init_connection,
        )
        logger.info(
            "Database pool initialized (min=%d, max=%d)", self.min_size, self.max_size
        )

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Per-connection setup: register pgvector type codec."""
        await conn.set_type_codec(
            "vector",
            encoder=self._encode_vector,
            decoder=self._decode_vector,
            schema="public",
            format="text",
        )

    @staticmethod
    def _encode_vector(v: list[float]) -> str:
        return "[" + ",".join(str(x) for x in v) + "]"

    @staticmethod
    def _decode_vector(v: str) -> list[float]:
        return [float(x) for x in v.strip("[]").split(",")]

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool not initialized. Call initialize() first.")
        return self._pool

    @asynccontextmanager
    async def acquire(self):
        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("Database pool closed")


# ── Product Repository ───────────────────────────────────────────────────────

class AsyncPGProductRepository:
    """
    Production repository implementing the ProductRepository interface.
    
    Methods match the interface defined in ingestion_orchestrator.py:
    - find_product_by_model(model_number) -> Optional[dict]
    - create_product(product_data) -> str
    - update_product(product_id, updates) -> None
    - search_products(filters) -> list[dict]
    - find_or_create_brand(name) -> str
    - find_or_create_family(name, brand_id) -> str
    - add_document(doc_data) -> str
    - get_document_by_hash(sha256) -> Optional[dict]
    - update_document_status(doc_id, status) -> None
    - add_chunks(chunks) -> list[str]
    - add_conflict(conflict_data) -> str
    - get_pending_conflicts(product_id?) -> list[dict]
    - resolve_conflict(conflict_id, resolution, resolved_by, override_value?) -> None
    - link_document_product(doc_id, product_id) -> None
    - get_spec_registry() -> list[dict]
    - upsert_spec_registry(entries) -> None
    """

    def __init__(self, db: DatabasePool):
        self.db = db

    # ── Products ─────────────────────────────────────────────────────────

    async def find_product_by_model(self, model_number: str) -> Optional[dict]:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT p.*, b.name AS brand_name, f.name AS family_name
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                LEFT JOIN product_families f ON p.family_id = f.id
                WHERE p.model_number = $1
                """,
                model_number,
            )
            return dict(row) if row else None

    async def create_product(self, data: dict) -> str:
        product_id = str(uuid.uuid4())
        specs = data.pop("specs", {})
        cols = ["id"] + list(data.keys()) + ["specs", "created_at", "updated_at"]
        vals = [product_id] + list(data.values()) + [
            json.dumps(specs),
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        ]
        placeholders = ", ".join(f"${i+1}" for i in range(len(vals)))
        col_names = ", ".join(cols)

        async with self.db.transaction() as conn:
            await conn.execute(
                f"INSERT INTO products ({col_names}) VALUES ({placeholders})",
                *vals,
            )
            logger.info("Created product %s (%s)", data.get("model_number"), product_id)
        return product_id

    async def update_product(self, product_id: str, updates: dict) -> None:
        if not updates:
            return
        specs = updates.pop("specs", None)
        sets, vals, idx = [], [], 1

        for k, v in updates.items():
            sets.append(f"{k} = ${idx}")
            vals.append(v)
            idx += 1

        if specs:
            sets.append(f"specs = specs || ${idx}::jsonb")
            vals.append(json.dumps(specs))
            idx += 1

        sets.append(f"updated_at = ${idx}")
        vals.append(datetime.now(timezone.utc))
        idx += 1
        vals.append(product_id)

        query = f"UPDATE products SET {', '.join(sets)} WHERE id = ${idx}"
        async with self.db.acquire() as conn:
            await conn.execute(query, *vals)

    async def search_products(self, filters: dict) -> list[dict]:
        conditions, vals, idx = [], [], 1

        if brand := filters.get("brand"):
            conditions.append(f"b.name ILIKE ${idx}")
            vals.append(f"%{brand}%")
            idx += 1

        if family := filters.get("family"):
            conditions.append(f"f.name ILIKE ${idx}")
            vals.append(f"%{family}%")
            idx += 1

        if min_cap := filters.get("capacity_min"):
            conditions.append(f"p.storage_capacity_cuft >= ${idx}")
            vals.append(float(min_cap))
            idx += 1

        if max_cap := filters.get("capacity_max"):
            conditions.append(f"p.storage_capacity_cuft <= ${idx}")
            vals.append(float(max_cap))
            idx += 1

        if door_type := filters.get("door_type"):
            conditions.append(f"p.door_type = ${idx}")
            vals.append(door_type)
            idx += 1

        if voltage := filters.get("voltage"):
            conditions.append(f"p.voltage_v = ${idx}")
            vals.append(int(voltage))
            idx += 1

        if certs := filters.get("certifications"):
            conditions.append(f"p.certifications @> ${idx}::text[]")
            vals.append(certs)
            idx += 1

        if text := filters.get("text"):
            conditions.append(
                f"p.search_vector @@ plainto_tsquery('english', ${idx})"
            )
            vals.append(text)
            idx += 1

        if status := filters.get("status"):
            conditions.append(f"p.status = ${idx}")
            vals.append(status)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        limit = min(int(filters.get("limit", 50)), 200)
        offset = int(filters.get("offset", 0))

        query = f"""
            SELECT p.*, b.name AS brand_name, f.name AS family_name
            FROM products p
            LEFT JOIN brands b ON p.brand_id = b.id
            LEFT JOIN product_families f ON p.family_id = f.id
            {where}
            ORDER BY p.model_number
            LIMIT {limit} OFFSET {offset}
        """
        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, *vals)
            return [dict(r) for r in rows]

    async def get_product_with_documents(self, product_id: str) -> Optional[dict]:
        async with self.db.acquire() as conn:
            product = await conn.fetchrow(
                """
                SELECT p.*, b.name AS brand_name, f.name AS family_name
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                LEFT JOIN product_families f ON p.family_id = f.id
                WHERE p.id = $1
                """,
                product_id,
            )
            if not product:
                return None

            docs = await conn.fetch(
                """
                SELECT d.* FROM documents d
                JOIN document_products dp ON d.id = dp.document_id
                WHERE dp.product_id = $1
                ORDER BY d.ingested_at DESC
                """,
                product_id,
            )
            result = dict(product)
            result["documents"] = [dict(d) for d in docs]
            return result

    # ── Brands & Families ────────────────────────────────────────────────

    async def find_or_create_brand(self, name: str) -> str:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM brands WHERE name ILIKE $1", name
            )
            if row:
                return str(row["id"])

            brand_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO brands (id, name, created_at) VALUES ($1, $2, $3)",
                brand_id,
                name,
                datetime.now(timezone.utc),
            )
            return brand_id

    async def find_or_create_family(self, name: str, brand_id: str) -> str:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM product_families WHERE name ILIKE $1 AND brand_id = $2",
                name,
                brand_id,
            )
            if row:
                return str(row["id"])

            family_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO product_families (id, name, brand_id, created_at) VALUES ($1, $2, $3, $4)",
                family_id,
                name,
                brand_id,
                datetime.now(timezone.utc),
            )
            return family_id

    # ── Documents ────────────────────────────────────────────────────────

    async def add_document(self, data: dict) -> str:
        doc_id = str(uuid.uuid4())
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO documents (id, filename, file_hash, doc_type, status, raw_text, 
                                       extracted_data, brand_detected, models_detected, ingested_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                doc_id,
                data["filename"],
                data["file_hash"],
                data.get("doc_type", "unknown"),
                data.get("status", "pending"),
                data.get("raw_text", ""),
                json.dumps(data.get("extracted_data", {})),
                data.get("brand_detected"),
                data.get("models_detected", []),
                datetime.now(timezone.utc),
            )
        return doc_id

    async def get_document_by_hash(self, sha256: str) -> Optional[dict]:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE file_hash = $1", sha256
            )
            return dict(row) if row else None

    async def update_document_status(self, doc_id: str, status: str) -> None:
        async with self.db.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status = $1, updated_at = $2 WHERE id = $3",
                status,
                datetime.now(timezone.utc),
                doc_id,
            )

    async def link_document_product(self, doc_id: str, product_id: str) -> None:
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO document_products (document_id, product_id, linked_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (document_id, product_id) DO NOTHING
                """,
                doc_id,
                product_id,
                datetime.now(timezone.utc),
            )

    # ── Chunks (RAG) ─────────────────────────────────────────────────────

    async def add_chunks(self, chunks: list[dict]) -> list[str]:
        chunk_ids = []
        async with self.db.transaction() as conn:
            stmt = await conn.prepare(
                """
                INSERT INTO document_chunks 
                    (id, document_id, product_id, chunk_index, content, section_type,
                     model_numbers, token_count, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """
            )
            for chunk in chunks:
                chunk_id = str(uuid.uuid4())
                await stmt.fetch(
                    chunk_id,
                    chunk["document_id"],
                    chunk.get("product_id"),
                    chunk.get("chunk_index", 0),
                    chunk["content"],
                    chunk.get("section_type", "general"),
                    chunk.get("model_numbers", []),
                    chunk.get("token_count", 0),
                    chunk.get("embedding"),
                )
                chunk_ids.append(chunk_id)
        logger.info("Inserted %d chunks", len(chunk_ids))
        return chunk_ids

    async def vector_search(
        self,
        embedding: list[float],
        limit: int = 20,
        product_id: Optional[str] = None,
        model_numbers: Optional[list[str]] = None,
    ) -> list[dict]:
        """pgvector cosine similarity search."""
        conditions = ["embedding IS NOT NULL"]
        vals: list[Any] = [embedding, limit]
        idx = 3

        if product_id:
            conditions.append(f"product_id = ${idx}")
            vals.append(product_id)
            idx += 1

        if model_numbers:
            conditions.append(f"model_numbers && ${idx}::text[]")
            vals.append(model_numbers)
            idx += 1

        where = " AND ".join(conditions)
        query = f"""
            SELECT id, document_id, product_id, chunk_index, content, section_type,
                   model_numbers, token_count,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM document_chunks
            WHERE {where}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """
        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, *vals)
            return [dict(r) for r in rows]

    async def keyword_search(
        self,
        query_text: str,
        limit: int = 20,
        product_id: Optional[str] = None,
        model_numbers: Optional[list[str]] = None,
    ) -> list[dict]:
        """PostgreSQL full-text search with ts_rank scoring."""
        conditions = [
            "to_tsvector('english', content) @@ plainto_tsquery('english', $1)"
        ]
        vals: list[Any] = [query_text, limit]
        idx = 3

        if product_id:
            conditions.append(f"product_id = ${idx}")
            vals.append(product_id)
            idx += 1

        if model_numbers:
            conditions.append(f"model_numbers && ${idx}::text[]")
            vals.append(model_numbers)
            idx += 1

        where = " AND ".join(conditions)
        query = f"""
            SELECT id, document_id, product_id, chunk_index, content, section_type,
                   model_numbers, token_count,
                   ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) AS rank
            FROM document_chunks
            WHERE {where}
            ORDER BY rank DESC
            LIMIT $2
        """
        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, *vals)
            return [dict(r) for r in rows]

    # ── Conflicts ────────────────────────────────────────────────────────

    async def add_conflict(self, data: dict) -> str:
        conflict_id = str(uuid.uuid4())
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO spec_conflicts 
                    (id, product_id, document_id, spec_name, existing_value, new_value,
                     severity, resolution, detected_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8)
                """,
                conflict_id,
                data["product_id"],
                data.get("document_id"),
                data["spec_name"],
                str(data["existing_value"]),
                str(data["new_value"]),
                data.get("severity", "medium"),
                datetime.now(timezone.utc),
            )
        return conflict_id

    async def get_pending_conflicts(
        self, product_id: Optional[str] = None
    ) -> list[dict]:
        conditions = ["sc.resolution = 'pending'"]
        vals = []
        if product_id:
            conditions.append("sc.product_id = $1")
            vals.append(product_id)

        where = " AND ".join(conditions)
        query = f"""
            SELECT sc.*, p.model_number AS product_model, d.filename AS source_document
            FROM spec_conflicts sc
            JOIN products p ON sc.product_id = p.id
            LEFT JOIN documents d ON sc.document_id = d.id
            WHERE {where}
            ORDER BY 
                CASE sc.severity 
                    WHEN 'critical' THEN 0 WHEN 'high' THEN 1 
                    WHEN 'medium' THEN 2 ELSE 3 
                END,
                sc.detected_at DESC
        """
        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, *vals)
            return [dict(r) for r in rows]

    async def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        resolved_by: str,
        override_value: Optional[str] = None,
    ) -> None:
        async with self.db.transaction() as conn:
            conflict = await conn.fetchrow(
                "SELECT * FROM spec_conflicts WHERE id = $1", conflict_id
            )
            if not conflict:
                raise ValueError(f"Conflict {conflict_id} not found")

            await conn.execute(
                """
                UPDATE spec_conflicts 
                SET resolution = $1, resolved_by = $2, override_value = $3, resolved_at = $4
                WHERE id = $5
                """,
                resolution,
                resolved_by,
                override_value,
                datetime.now(timezone.utc),
                conflict_id,
            )

            # Apply the resolution to the product
            if resolution == "accept_new":
                apply_value = conflict["new_value"]
            elif resolution == "manual_override" and override_value:
                apply_value = override_value
            else:
                return  # keep_existing or dismissed — no product update

            spec_name = conflict["spec_name"]
            product_id = conflict["product_id"]

            # Check if it's a fixed column or JSONB spec
            fixed_cols = {
                "storage_capacity_cuft", "temp_range_min_c", "temp_range_max_c",
                "door_count", "door_type", "shelf_count", "refrigerant",
                "voltage_v", "amperage", "product_weight_lbs",
                "ext_width_in", "ext_depth_in", "ext_height_in",
            }
            if spec_name in fixed_cols:
                await conn.execute(
                    f"UPDATE products SET {spec_name} = $1, updated_at = $2 WHERE id = $3",
                    apply_value,
                    datetime.now(timezone.utc),
                    product_id,
                )
            else:
                await conn.execute(
                    """
                    UPDATE products 
                    SET specs = jsonb_set(COALESCE(specs, '{}'::jsonb), $1::text[], to_jsonb($2::text)),
                        updated_at = $3
                    WHERE id = $4
                    """,
                    [spec_name],
                    apply_value,
                    datetime.now(timezone.utc),
                    product_id,
                )

            # Audit log
            await conn.execute(
                """
                INSERT INTO audit_log (id, action, entity_type, entity_id, user_id, details, created_at)
                VALUES ($1, 'conflict_resolved', 'product', $2, $3, $4, $5)
                """,
                str(uuid.uuid4()),
                product_id,
                resolved_by,
                json.dumps({
                    "conflict_id": conflict_id,
                    "spec": spec_name,
                    "resolution": resolution,
                    "value": apply_value,
                }),
                datetime.now(timezone.utc),
            )

    # ── Spec Registry ────────────────────────────────────────────────────

    async def get_spec_registry(self) -> list[dict]:
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM spec_registry ORDER BY category, display_name"
            )
            return [dict(r) for r in rows]

    async def upsert_spec_registry(self, entries: list[dict]) -> None:
        async with self.db.transaction() as conn:
            stmt = await conn.prepare(
                """
                INSERT INTO spec_registry (id, canonical_name, display_name, unit, data_type,
                                           category, is_critical, synonyms, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (canonical_name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    unit = EXCLUDED.unit,
                    data_type = EXCLUDED.data_type,
                    category = EXCLUDED.category,
                    is_critical = EXCLUDED.is_critical,
                    synonyms = EXCLUDED.synonyms
                """
            )
            for entry in entries:
                await stmt.fetch(
                    str(uuid.uuid4()),
                    entry["canonical_name"],
                    entry.get("display_name", entry["canonical_name"]),
                    entry.get("unit"),
                    entry.get("data_type", "text"),
                    entry.get("category", "general"),
                    entry.get("is_critical", False),
                    entry.get("synonyms", []),
                    datetime.now(timezone.utc),
                )

    # ── Equivalence ──────────────────────────────────────────────────────

    async def find_equivalents(self, model_number: str) -> list[dict]:
        """Find cross-brand equivalents via equivalence_rules table."""
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p2.model_number, b.name AS brand, p2.storage_capacity_cuft,
                       p2.temp_range_min_c, p2.temp_range_max_c, er.confidence
                FROM equivalence_rules er
                JOIN products p1 ON er.product_id_a = p1.id
                JOIN products p2 ON er.product_id_b = p2.id
                JOIN brands b ON p2.brand_id = b.id
                WHERE p1.model_number = $1
                UNION ALL
                SELECT p1.model_number, b.name AS brand, p1.storage_capacity_cuft,
                       p1.temp_range_min_c, p1.temp_range_max_c, er.confidence
                FROM equivalence_rules er
                JOIN products p1 ON er.product_id_a = p1.id
                JOIN products p2 ON er.product_id_b = p2.id
                JOIN brands b ON p1.brand_id = b.id
                WHERE p2.model_number = $1
                ORDER BY confidence DESC
                """,
                model_number,
            )
            return [dict(r) for r in rows]

    # ── Statistics ───────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        async with self.db.acquire() as conn:
            product_count = await conn.fetchval("SELECT COUNT(*) FROM products")
            doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents")
            chunk_count = await conn.fetchval("SELECT COUNT(*) FROM document_chunks")
            conflict_count = await conn.fetchval(
                "SELECT COUNT(*) FROM spec_conflicts WHERE resolution = 'pending'"
            )
            brand_counts = await conn.fetch(
                """
                SELECT b.name, COUNT(p.id) AS count
                FROM brands b LEFT JOIN products p ON b.id = p.brand_id
                GROUP BY b.name ORDER BY count DESC
                """
            )
            return {
                "products": product_count,
                "documents": doc_count,
                "chunks": chunk_count,
                "pending_conflicts": conflict_count,
                "brands": {r["name"]: r["count"] for r in brand_counts},
            }

    # ── Health Check ─────────────────────────────────────────────────────

    async def health_check(self) -> dict:
        try:
            async with self.db.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                pool = self.db.pool
                return {
                    "status": "healthy",
                    "postgres_version": version,
                    "pool_size": pool.get_size(),
                    "pool_free": pool.get_idle_size(),
                    "pool_used": pool.get_size() - pool.get_idle_size(),
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
