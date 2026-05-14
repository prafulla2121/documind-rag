"""
Admin API Routes — system stats, cache management, health checks.
"""
from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.api.dependencies import get_metadata_db, get_vector_store, get_bm25
from app.storage.cache import CacheManager
from app.rag.llm_client import OllamaClient
from app.core.config import settings

router = APIRouter()


@router.get("/stats")
async def system_stats(current_user=Depends(get_current_user)):
    """Get system statistics."""
    db = get_metadata_db()
    vs = get_vector_store()
    cache = CacheManager()

    db_stats = await db.get_stats()
    qdrant_info = vs.get_collection_info()
    cache_stats = cache.get_cache_stats()

    # Check Ollama status
    llm = OllamaClient(base_url=settings.OLLAMA_URL, model=settings.LLM_MODEL)
    ollama_healthy = await llm.health_check()

    return {
        "documents": db_stats.get("total_documents", 0),
        "total_queries": db_stats.get("total_queries", 0),
        "vectors": qdrant_info.get("points_count", 0),
        "qdrant_status": qdrant_info.get("status", "unknown"),
        "ollama_status": "healthy" if ollama_healthy else "unavailable",
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "cache": cache_stats,
    }


@router.post("/cache/clear")
async def clear_cache(current_user=Depends(get_current_user)):
    """Clear response cache."""
    cache = CacheManager()
    await cache.invalidate_responses()
    return {"message": "Response cache cleared"}


@router.post("/bm25/rebuild")
async def rebuild_bm25(current_user=Depends(get_current_user)):
    """Rebuild BM25 index from current vector store."""
    bm25 = get_bm25()
    count = bm25.rebuild_from_vector_store()
    return {"message": f"BM25 index rebuilt with {count} documents"}
