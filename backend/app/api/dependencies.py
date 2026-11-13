"""
API Dependencies — shared dependency injection for FastAPI routes.
Initializes and provides singleton instances of all RAG components.
"""
import logging
from pathlib import Path
from app.core.config import settings
from app.ingestion.embedder import make_embedder
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
_vector_store = None
_embedder = None
_bm25 = None
_cache: CacheManager | None = None
_tracer: RAGTracer | None = None
_queue = None  # arq pool (Redis); also used for rate limits


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = make_embedder()
    return _embedder


def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(
            path=settings.QDRANT_PATH,
            collection_name=settings.QDRANT_COLLECTION,
        )
    return _vector_store


def get_bm25():
    """Sparse index: BM25 pickle for Qdrant, Postgres full-text search for pgvector."""
    global _bm25
    if _bm25 is None:
        if settings.VECTOR_BACKEND == "pgvector":
            from app.storage.pgvector_store import PgKeywordIndex
            _bm25 = PgKeywordIndex()
        else:
            _bm25 = BM25Index(index_path=settings.BM25_INDEX_PATH)
    return _bm25


async def get_queue():
    global _queue
    if _queue is None:
        from arq import create_pool
        from arq.connections import RedisSettings
        if not settings.REDIS_URL:
            raise RuntimeError("REDIS_URL is required for the /v1 platform API")
        _queue = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _queue


def get_platform_llm():
    from app.providers.base import ModelConfig
    from app.providers.registry import PROVIDER_CATALOG, get_llm_provider
    provider = settings.PLATFORM_LLM_PROVIDER
    if PROVIDER_CATALOG.get(provider, {}).get("key_required") and not settings.PLATFORM_LLM_API_KEY:
        # No key yet (e.g. a fresh Space): answer with the stub instead of failing every query.
        logger.warning("PLATFORM_LLM_API_KEY is empty for provider %s: using the stub LLM", provider)
        provider = "stub"
    return get_llm_provider(ModelConfig(
        provider=provider,
        model_name=settings.PLATFORM_LLM_MODEL,
        api_key=settings.PLATFORM_LLM_API_KEY,
        api_base_url=settings.PLATFORM_LLM_BASE_URL,
    ))


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


SAMPLE_DOC = Path(__file__).resolve().parents[3] / "evals" / "harbor_lamp_guide.md"


async def _preload_sample_doc(db: MetadataDB):
    """Demo mode: load the eval sample doc for anonymous visitors so they can ask right away."""
    if not SAMPLE_DOC.exists():
        logger.warning(f"Sample doc missing, nothing preloaded: {SAMPLE_DOC}")
        return
    if await db.find_document_by_filename(SAMPLE_DOC.name, "md", "anonymous"):
        return
    from app.ingestion.pipeline import IngestionPipeline
    result = IngestionPipeline().ingest_file(str(SAMPLE_DOC), user_id="anonymous")
    await db.add_document(doc_id=result["doc_id"], filename=SAMPLE_DOC.name, source_type="md",
                          title="Harbor HL-7 lantern guide", user_id="anonymous")
    await db.update_document(doc_id=result["doc_id"], num_chunks=result.get("num_chunks", 0),
                             status=result.get("status", "completed"))
    logger.info(f"Demo sample doc preloaded: {result.get('num_chunks', 0)} chunks")


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

    if settings.DEMO_MODE:
        await _preload_sample_doc(db)

    # Heavy RAG components are initialized lazily when documents are ingested or
    # queried, so auth and admin routes can start without downloading models.
    if settings.VECTOR_BACKEND == "pgvector":
        get_vector_store().create_collection(vector_dim=get_embedder().dimension)
        logger.info("pgvector backend: schema ready; keyword search runs in Postgres, no BM25 warm-up")
        return

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
