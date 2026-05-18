"""
API Dependencies — shared dependency injection for FastAPI routes.
Initializes and provides singleton instances of all RAG components.
"""
import logging
from app.core.config import settings
from app.ingestion.embedder import Embedder
from app.storage.vector_store import VectorStore
from app.storage.cache import CacheManager
from app.storage.metadata_db import MetadataDB
from app.rag.query_processor import QueryProcessor
from app.rag.bm25_index import BM25Index
from app.rag.retriever import HybridRetriever
from app.rag.reranker import Reranker
from app.rag.context_builder import ContextBuilder
from app.rag.observability import RAGTracer
from app.rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)

# ── Singleton Instances ────────────────────────────────

_pipeline: RAGPipeline | None = None
_metadata_db: MetadataDB | None = None
_vector_store: VectorStore | None = None
_embedder: Embedder | None = None
_bm25: BM25Index | None = None
_cache: CacheManager | None = None
_tracer: RAGTracer | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder(model_name=settings.EMBEDDING_MODEL)
    return _embedder


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(
            path=settings.QDRANT_PATH,
            collection_name=settings.QDRANT_COLLECTION,
        )
    return _vector_store


def get_bm25() -> BM25Index:
    global _bm25
    if _bm25 is None:
        _bm25 = BM25Index(index_path=settings.BM25_INDEX_PATH)
    return _bm25


def get_metadata_db() -> MetadataDB:
    global _metadata_db
    if _metadata_db is None:
        _metadata_db = MetadataDB(db_path=settings.SQLITE_DB_PATH)
    return _metadata_db


def get_cache() -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache


def get_tracer() -> RAGTracer:
    global _tracer
    if _tracer is None:
        from pathlib import Path
        _tracer = RAGTracer(log_dir=str(Path(settings.DATA_DIR) / "logs"))
    return _tracer


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        embedder = get_embedder()
        vector_store = get_vector_store()
        bm25 = get_bm25()

        _pipeline = RAGPipeline(
            query_processor=QueryProcessor(),
            retriever=HybridRetriever(vector_store, bm25, embedder),
            reranker=Reranker(top_k=settings.TOP_K_FINAL),
            context_builder=ContextBuilder(),
            cache=get_cache(),
            tracer=get_tracer()
        )
    return _pipeline


async def initialize_services():
    """Called on startup — initializes DB, loads indexes."""
    logger.info("🚀 Initializing services...")

    # Initialize database
    db = get_metadata_db()
    await db.init_db()
    await db.seed_oauth_settings(
        google_client_id=settings.GOOGLE_CLIENT_ID,
        google_client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    # Heavy RAG components are initialized lazily when documents are ingested or
    # queried, so auth and admin routes can start without downloading models.
    # Try to load BM25 index
    bm25 = get_bm25()
    try:
        rebuilt = bm25.rebuild_from_vector_store()
        if rebuilt:
            logger.info(f"BM25 index rebuilt from vector store: {rebuilt} docs")
            await get_cache().invalidate_responses()
            logger.info("âœ… All services initialized")
            return
        bm25._load()
        if bm25.index:
            logger.info(f"BM25 index loaded: {len(bm25.doc_store)} docs")
        else:
            logger.info("No existing BM25 index found — will build on first ingestion")
    except Exception:
        logger.info("No existing BM25 index — will build on first ingestion")

    logger.info("✅ All services initialized")
