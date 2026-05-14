"""
Application configuration via Pydantic BaseSettings.
All settings can be overridden via .env file or environment variables.
"""
from pydantic_settings import BaseSettings
from pathlib import Path
import os

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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    GOOGLE_CLIENT_ID: str = ""

    # --- Paths ---
    DATA_DIR: str = str(PROJECT_ROOT / "data")
    UPLOAD_DIR: str = str(PROJECT_ROOT / "data" / "uploads")
    BM25_INDEX_PATH: str = str(PROJECT_ROOT / "data" / "bm25_index.pkl")
    SQLITE_DB_PATH: str = str(PROJECT_ROOT / "data" / "metadata.db")
    DATABASE_URL: str = "postgresql+asyncpg://postgres:1234@localhost:5432/RagSytem"

    # --- Server ---
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173

    @property
    def async_db_url(self) -> str:
        """Return the database URL with the asyncpg driver, stripping unsupported params."""
        url = self.DATABASE_URL
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


settings = Settings()

# Ensure data directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.QDRANT_PATH, exist_ok=True)
