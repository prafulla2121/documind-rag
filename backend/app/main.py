"""
FastAPI Application Entry Point — RAG Company Assistant API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import logging

from app.api.routes import query, ingest, admin, auth, models, v1
from app.api.dependencies import initialize_services
from app.core.config import settings
from app.providers.registry import PROVIDER_CATALOG
from app.core.telemetry import RequestContextMiddleware, metrics_response, setup_logging

# ── Logging ────────────────────────────────────────────
setup_logging(settings.LOG_FORMAT)
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting RAG Company Assistant...")
    await initialize_services()
    logger.info("✅ RAG Company Assistant is ready!")
    yield
    logger.info("🛑 Shutting down...")


# ── App ────────────────────────────────────────────────
app = FastAPI(
    title="RAG Company Assistant API",
    description="Production-grade RAG system for company knowledge base",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        *[o.strip().rstrip("/") for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestContextMiddleware)

# ── Routes ─────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(models.router, prefix="/api")
app.include_router(v1.router, prefix="/v1", tags=["platform"])


@app.get("/metrics", include_in_schema=False)
async def metrics():
    from app.api.dependencies import get_queue
    queue = None
    if settings.REDIS_URL:
        try:
            queue = await get_queue()
        except Exception as e:
            logger.warning(f"queue depth unavailable: {e}")
    return await metrics_response(queue)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/api/demo")
async def demo_info():
    """What the UI needs to know about the public demo: mode, upload cap, example questions."""
    examples = []
    if settings.DEMO_MODE:
        from app.api.dependencies import SAMPLE_DOC
        golden = SAMPLE_DOC.with_name("golden.jsonl")
        if golden.exists():
            lines = [line for line in golden.read_text(encoding="utf-8").splitlines() if line.strip()]
            examples = [json.loads(line)["question"] for line in lines[:3]]
    return {
        "demo_mode": settings.DEMO_MODE,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "examples": examples,
        # False = no key on the server: answers come from the stub (echoed sources), the UI says so.
        "llm_ready": settings.PLATFORM_LLM_PROVIDER != "stub" and (
            bool(settings.PLATFORM_LLM_API_KEY)
            or not PROVIDER_CATALOG.get(settings.PLATFORM_LLM_PROVIDER, {}).get("key_required")),
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "reranker": bool(settings.RERANKER_ENABLED),
    }


@app.get("/")
async def root():
    return {
        "name": "RAG Company Assistant",
        "version": "1.0.0",
        "docs": "/api/docs",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
