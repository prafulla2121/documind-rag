"""
Application configuration via Pydantic BaseSettings.
All settings can be overridden via .env file or environment variables.
"""
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional, Any
import logging
import os
import secrets

# Resolve .env path relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # --- LLM (Ollama) ---
    OLLAMA_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3"
    LLM_TEMPERATURE: float = 0.1  # Low for RAG — factual, not creative

    # --- Embeddings ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_BATCH_SIZE: int = 32
    # "local" (sentence-transformers), "gemini" (API, no torch) or "hash" (keyless stub for tests).
    # Empty = "local", or in DEMO_MODE "gemini" when GEMINI_API_KEY is set, else "hash".
    EMBEDDING_PROVIDER: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_EMBEDDING_DIM: int = 768
    RERANKER_ENABLED: Optional[bool] = None  # None = on, except in DEMO_MODE (cross-encoder needs torch)

    # --- Qdrant (local file mode) ---
    QDRANT_PATH: str = str(PROJECT_ROOT / "data" / "qdrant_storage")
    QDRANT_COLLECTION: str = "company_docs"

    # --- Retrieval ---
    TOP_K_DENSE: int = 20
    TOP_K_SPARSE: int = 20
    TOP_K_FINAL: int = 5

    # --- Chunking ---
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50

    # --- Auth ---
    SECRET_KEY: str = "change-in-production"
    ENCRYPTION_KEY: str = "your-symmetric-encryption-key-here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # --- Paths ---
    DATA_DIR: str = str(PROJECT_ROOT / "data")
    UPLOAD_DIR: str = str(PROJECT_ROOT / "data" / "uploads")
    BM25_INDEX_PATH: str = str(PROJECT_ROOT / "data" / "bm25_index.pkl")
    SQLITE_DB_PATH: str = str(PROJECT_ROOT / "data" / "metadata.db")
    DATABASE_URL: str = "postgresql+asyncpg://postgres:1234@localhost:5432/RagSystem"

    # --- Server ---
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173
    REDIS_URL: Optional[str] = None

    # --- Platform (multi-tenant API, queue, pgvector) ---
    VECTOR_BACKEND: str = "qdrant"  # "qdrant" (local file, single process) or "pgvector"
    PGVECTOR_URL: str = ""  # psycopg conninfo; empty = DATABASE_URL without the +asyncpg driver
    TENANT_API_KEYS: str = ""  # "tenant_a:key1,tenant_b:key2"
    RATE_LIMIT_PER_MINUTE: int = 120  # per tenant, fixed one-minute window
    MAX_UPLOAD_MB: int = 20
    PLATFORM_LLM_PROVIDER: str = "ollama"  # "stub" = no model, echoes context (tests, load tests)
    PLATFORM_LLM_MODEL: str = "llama3.2:3b"
    PLATFORM_LLM_API_KEY: str = ""
    PLATFORM_LLM_BASE_URL: str = ""
    LOG_FORMAT: str = "text"  # "json" for structured logs

    # --- Public demo (Render backend + Vercel frontend) ---
    DEMO_MODE: bool = False  # SQLite, sample doc preloaded, no server-side URL fetching, query rate limit
    CORS_ORIGINS: str = ""  # extra allowed origins, comma-separated (e.g. the Vercel URL)
    DEMO_QUERIES_PER_HOUR: int = 20  # per visitor IP (questions and uploads)
    DEMO_QUERIES_PER_DAY: int = 300  # all visitors together; protects the free Gemini key

    @property
    def pgvector_dsn(self) -> str:
        return self.PGVECTOR_URL or self.DATABASE_URL.replace("+asyncpg", "", 1)

    @property
    def async_db_url(self) -> str:
        """Return the database URL with the asyncpg driver, stripping unsupported params."""
        url = self.DATABASE_URL
        
        # Handle SQLite relative paths
        if url.startswith("sqlite"):
            if "///./" in url:
                # Resolve ./ relative to PROJECT_ROOT
                url = url.replace("///./", f"///{PROJECT_ROOT}/", 1)
            elif "///../" in url:
                # Resolve ../ relative to PROJECT_ROOT
                url = url.replace("///../", f"///{PROJECT_ROOT.parent}/", 1)
            return url

        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Strip ?schema=... if present, as asyncpg might not support it as a query param
        if "?" in url:
            base_url, query = url.split("?", 1)
            params = query.split("&")
            filtered_params = [p for p in params if not p.startswith("schema=")]
            if filtered_params:
                url = f"{base_url}?{'&'.join(filtered_params)}"
            else:
                url = base_url
        return url

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def _resolve_project_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str(PROJECT_ROOT / path)


def _prefer_existing_qdrant_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)

    project_path = PROJECT_ROOT / path
    legacy_backend_path = PROJECT_ROOT / "backend" / path
    collection_name = settings.QDRANT_COLLECTION

    project_has_collection = (project_path / "collection" / collection_name).exists()
    legacy_has_collection = (legacy_backend_path / "collection" / collection_name).exists()
    if legacy_has_collection and not project_has_collection:
        return str(legacy_backend_path)
    return str(project_path)


settings.DATA_DIR = _resolve_project_path(settings.DATA_DIR)
settings.UPLOAD_DIR = _resolve_project_path(settings.UPLOAD_DIR)
settings.BM25_INDEX_PATH = _resolve_project_path(settings.BM25_INDEX_PATH)
settings.SQLITE_DB_PATH = _resolve_project_path(settings.SQLITE_DB_PATH)
settings.QDRANT_PATH = _prefer_existing_qdrant_path(settings.QDRANT_PATH)

_PLACEHOLDER_SECRETS = {"change-in-production", "your-symmetric-encryption-key-here",
                        "change-this-in-production-use-a-long-random-string"}
for _name in ("SECRET_KEY", "ENCRYPTION_KEY"):
    if getattr(settings, _name) in _PLACEHOLDER_SECRETS or not getattr(settings, _name):
        if settings.DEMO_MODE:
            # Demo data is wiped on restart anyway, so a per-boot random key is safe and never public.
            setattr(settings, _name, secrets.token_urlsafe(48))
            logging.getLogger(__name__).warning("%s not set: generated a random one for this run", _name)
        else:
            logging.getLogger(__name__).warning("%s is a placeholder value: set it before exposing this server", _name)

if settings.DEMO_MODE and "DATABASE_URL" not in settings.model_fields_set:
    settings.DATABASE_URL = f"sqlite+aiosqlite:///{settings.SQLITE_DB_PATH}"
if settings.DEMO_MODE and "MAX_UPLOAD_MB" not in settings.model_fields_set:
    settings.MAX_UPLOAD_MB = 5

# One Gemini key serves both answers and embeddings.
if settings.PLATFORM_LLM_PROVIDER == "gemini" and not settings.PLATFORM_LLM_API_KEY:
    settings.PLATFORM_LLM_API_KEY = settings.GEMINI_API_KEY
if not settings.EMBEDDING_PROVIDER:
    settings.EMBEDDING_PROVIDER = ("gemini" if settings.GEMINI_API_KEY else "hash") if settings.DEMO_MODE else "local"
if settings.EMBEDDING_PROVIDER == "gemini" and not settings.GEMINI_API_KEY:
    logging.getLogger(__name__).warning("GEMINI_API_KEY is empty: using the keyword-hash stub embedder")
    settings.EMBEDDING_PROVIDER = "hash"
if settings.RERANKER_ENABLED is None:
    settings.RERANKER_ENABLED = not settings.DEMO_MODE

# Ensure data directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.QDRANT_PATH, exist_ok=True)
