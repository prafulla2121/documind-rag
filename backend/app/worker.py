"""
Ingestion worker (arq). Runs as its own process, separate from the API:

    cd backend && arq app.worker.WorkerSettings

The API only saves the upload and enqueues; parse -> clean -> chunk -> embed -> store
happens here, so a slow PDF or a burst of uploads never blocks query latency.
"""
import asyncio
import logging
import os

from arq.connections import RedisSettings

from app.core.config import settings
from app.core.telemetry import setup_logging

logger = logging.getLogger(__name__)


async def startup(ctx):
    setup_logging(settings.LOG_FORMAT)
    if settings.VECTOR_BACKEND != "pgvector":
        # Qdrant local mode locks its folder to one process; the API already holds it.
        raise RuntimeError("The worker needs VECTOR_BACKEND=pgvector")
    from app.api.dependencies import get_cache
    from app.ingestion.pipeline import IngestionPipeline

    ctx["pipeline"] = IngestionPipeline()  # loads the embedding model once per worker
    ctx["cache"] = get_cache()


def _remove(path: str):
    try:
        os.remove(path)
    except OSError:
        pass


async def ingest_file_job(ctx, path: str, filename: str, tenant_id: str) -> dict:
    try:
        # The pipeline is sync and CPU-bound (embedding); a thread keeps the worker loop responsive.
        result = await asyncio.to_thread(ctx["pipeline"].ingest_file, path, filename, "api", tenant_id)
    except Exception:
        _remove(path)  # a real failure is final; a cancel (worker shutdown) keeps the file for arq's retry
        raise
    _remove(path)
    if result.get("num_chunks"):
        await ctx["cache"].invalidate_responses()  # shared Redis version -> API cache misses
    logger.info(f"ingested {filename} for tenant {tenant_id}: {result.get('num_chunks')} chunks")
    return {k: result.get(k) for k in ("doc_id", "title", "num_chunks", "status")}


class WorkerSettings:
    functions = [ingest_file_job]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL or "redis://localhost:6379/0")
    max_jobs = int(os.getenv("WORKER_MAX_JOBS", "2"))
    job_timeout = 600
    max_tries = 3
    keep_result = 24 * 3600
    health_check_interval = 30  # `arq --check` (compose healthcheck) reads this key
