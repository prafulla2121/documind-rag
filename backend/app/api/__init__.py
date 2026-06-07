# API module

from fastapi import APIRouter
from app.api.routes import ingest, query, admin, auth

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingestion"])
api_router.include_router(query.router, prefix="/query", tags=["query"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
