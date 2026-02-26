"""
config.py — Environment-based configuration using Pydantic Settings.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = "postgresql://expert:expert@localhost:5432/product_expert"
    db_pool_min: int = 5
    db_pool_max: int = 20

    # ── Redis ────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600

    # ── Embedding Service ────────────────────────────────────────────────
    embedding_provider: str = "ollama"  # ollama | openai | huggingface
    embedding_api_url: str = "http://localhost:11434/api/embeddings"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    openai_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None

    # ── LLM (for RAG answers) ────────────────────────────────────────────
    llm_provider: str = "ollama"  # ollama | openai | anthropic
    llm_api_url: str = "http://localhost:11434/api/generate"
    llm_model: str = "llama3.1:8b"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.1
    openai_llm_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # ── Authentication ───────────────────────────────────────────────────
    # Format: "key1:role1,key2:role2"
    api_keys: str = "dev-key-001:admin"
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # ── Ingestion ────────────────────────────────────────────────────────
    max_upload_size_mb: int = 50
    upload_dir: str = "/app/data/uploads"
    supported_extensions: str = ".pdf,.txt,.md,.csv"
    background_workers: int = 2

    # ── RAG ──────────────────────────────────────────────────────────────
    rag_context_budget_tokens: int = 6000
    rag_max_chunks: int = 15
    rag_vector_weight: float = 0.6
    rag_keyword_weight: float = 0.4

    # ── Logging ──────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"  # json | text
    log_file: Optional[str] = None

    # ── Server ───────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False

    # ── Rate Limiting ────────────────────────────────────────────────────
    rate_limit_ask: str = "20/minute"
    rate_limit_ingest: str = "10/minute"
    rate_limit_default: str = "100/minute"

    # ── Computed Properties ──────────────────────────────────────────────

    @property
    def asyncpg_dsn(self) -> str:
        """Convert SQLAlchemy-style URL to plain asyncpg DSN."""
        url = self.database_url
        for prefix in ["postgresql+asyncpg://", "postgresql://"]:
            if url.startswith(prefix):
                return "postgresql://" + url[len(prefix):]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def api_key_map(self) -> dict[str, str]:
        """Parse 'key:role,key:role' into {key: role}."""
        result = {}
        for pair in self.api_keys.split(","):
            pair = pair.strip()
            if ":" in pair:
                key, role = pair.split(":", 1)
                result[key.strip()] = role.strip()
        return result

    @property
    def supported_extension_list(self) -> list[str]:
        return [e.strip() for e in self.supported_extensions.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return v.upper()

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, v: str) -> str:
        valid = {"ollama", "openai", "huggingface"}
        if v.lower() not in valid:
            raise ValueError(f"embedding_provider must be one of {valid}")
        return v.lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()
