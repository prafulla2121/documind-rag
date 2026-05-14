"""
FastAPI Application Entry Point — RAG Company Assistant API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api.routes import query, ingest, admin, auth
from app.api.dependencies import initialize_services
from app.core.config import settings

# ── Logging ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "name": "RAG Company Assistant",
        "version": "1.0.0",
        "docs": "/api/docs",
    }
