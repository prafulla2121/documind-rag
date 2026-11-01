"""
Platform API (/v1): multi-tenant, API-key auth, async ingestion through a Redis queue.

POST /v1/documents      upload a file -> 202 + job_id (a worker parses, chunks, embeds)
GET  /v1/jobs/{job_id}  job status for the caller's tenant only
POST /v1/query          answer from the caller's tenant's documents only
"""
import logging
import os
import time
import uuid

from arq.jobs import Job, JobStatus
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.dependencies import get_pipeline, get_platform_llm, get_queue
from app.api.routes.ingest import ALLOWED_EXTENSIONS
from app.core.config import settings
from app.core.telemetry import langfuse_client
from app.core.tenancy import rate_limited_tenant

logger = logging.getLogger(__name__)
router = APIRouter()
API_USER = "api"  # user namespace for /v1 traffic; isolation is by tenant_id


class V1QueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)


@router.post("/documents", status_code=202)
async def enqueue_document(file: UploadFile = File(...), tenant: str = Depends(rate_limited_tenant)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    content = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File larger than {settings.MAX_UPLOAD_MB} MB")

    job_id = uuid.uuid4().hex
    # The worker reads this path, so UPLOAD_DIR must be a volume both containers share.
    path = os.path.join(settings.UPLOAD_DIR, f"{job_id}{ext}")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)

    try:
        queue = await get_queue()
        job = await queue.enqueue_job(
            "ingest_file_job", path=path, filename=file.filename or "upload", tenant_id=tenant, _job_id=job_id,
        )
    except Exception:
        logger.exception("enqueue failed")
        job = None
    if job is None:
        os.remove(path)  # no job will ever read it; don't leak files on the shared volume
        raise HTTPException(503, "Ingestion queue unavailable, try again")
    logger.info(f"enqueued job {job_id} for tenant {tenant}: {file.filename}")
    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}")
async def job_status(job_id: str, tenant: str = Depends(rate_limited_tenant)):
    job = Job(job_id, await get_queue())
    # info() reads the result key, then the job key; a job that finishes between the two
    # reads is in neither. Re-reading the result closes that gap (seen under load as a 404).
    info = await job.info() or await job.result_info()
    # Another tenant's job looks exactly like a missing job.
    if info is None or info.kwargs.get("tenant_id") != tenant:
        raise HTTPException(404, "Job not found")
    status = await job.status()
    out = {"job_id": job_id, "status": status.value}
    if status == JobStatus.complete:
        result = await job.result_info()
        out["success"] = result.success
        out["result"] = result.result if result.success else None
        out["error"] = None if result.success else str(result.result)
        out["finished_at"] = result.finish_time.isoformat()
    return out


@router.post("/query")
async def query(request: V1QueryRequest, tenant: str = Depends(rate_limited_tenant)):
    started = time.perf_counter()
    try:
        result = await get_pipeline().query(
            request.query, get_platform_llm(), user_id=API_USER, tenant_id=tenant,
            rag_config={"top_k": request.top_k},
        )
    except Exception as e:
        logger.exception("query failed")
        raise HTTPException(502, f"LLM or retrieval error: {type(e).__name__}")

    lf = langfuse_client()
    if lf:
        try:
            span = lf.start_span(name="v1-query", input={"query": request.query, "tenant": tenant})
            span.update(output=result["answer"], metadata={
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "stage_timings": result.get("stage_timings"), "from_cache": result.get("from_cache"),
            })
            span.end()
        except Exception as e:
            logger.warning(f"Langfuse trace failed: {e}")

    return {
        "answer": result["answer"],
        "sources": [
            {"title": s.get("title"), "excerpt": s.get("excerpt"), "score": s.get("score")}
            for s in result.get("sources", [])
        ],
        "intent": result.get("intent"),
        "from_cache": result.get("from_cache", False),
        "latency_ms": result.get("latency_ms"),
    }
