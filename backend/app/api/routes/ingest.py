"""
Ingest API Routes — handles document upload and ingestion.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from typing import List
import os
import uuid
import logging
import time

from app.models.schemas import IngestResponse, URLIngestRequest
from app.core.config import settings
from app.core.security import get_current_user
from app.api.dependencies import get_metadata_db, get_bm25, get_cache

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".txt", ".md", ".csv"}
INGEST_TASKS = {}


async def _process_url_background(url: str, doc_id: str, task_id: str, user_id: str):
    """Background task to fetch and process a URL."""
    try:
        INGEST_TASKS[task_id] = {"task_id": task_id, "status": "running", "progress": 10, "doc_id": doc_id, "started_at": int(time.time())}
        import httpx
        from app.ingestion.pipeline import IngestionPipeline
        
        # Fetch URL content
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            html_content = response.text
            
        # Parse and Ingest directly
        pipeline = IngestionPipeline()
        parsed = pipeline.html_parser.parse(html_content, url=url)
        
        if not parsed.get("text"):
            raise ValueError("No text content could be extracted from the URL")
            
        result = pipeline.ingest_text(parsed["text"], title=parsed["title"] or url, source_type="web", user_id=user_id)
        INGEST_TASKS[task_id]["progress"] = 70
        
        # Update metadata DB
        db = get_metadata_db()
        await db.update_document(
            doc_id=doc_id,
            num_chunks=result.get("num_chunks", 0),
            status=result.get("status", "completed"),
        )

        # Rebuild BM25 index
        bm25 = get_bm25()
        bm25.rebuild_from_vector_store()
        await get_cache().invalidate_responses()
        INGEST_TASKS[task_id].update({"status": "completed", "progress": 100, "num_chunks": result.get("num_chunks", 0), "finished_at": int(time.time())})

        logger.info(f"✅ Background URL ingestion complete: {url} → {result.get('num_chunks', 0)} chunks")
    except Exception as e:
        logger.error(f"❌ Background URL ingestion failed for {url}: {e}")
        db = get_metadata_db()
        await db.update_document(doc_id=doc_id, num_chunks=0, status="failed")
        INGEST_TASKS[task_id].update({"status": "failed", "progress": 100, "error": str(e), "finished_at": int(time.time())})

async def _process_file_background(filepath: str, filename: str, doc_id: str, task_id: str, user_id: str):
    """Background task to process a file through the ingestion pipeline."""
    try:
        INGEST_TASKS[task_id] = {"task_id": task_id, "status": "running", "progress": 10, "doc_id": doc_id, "started_at": int(time.time())}
        from app.ingestion.pipeline import IngestionPipeline
        pipeline = IngestionPipeline()
        result = pipeline.ingest_file(filepath, original_filename=filename, user_id=user_id)
        INGEST_TASKS[task_id]["progress"] = 70

        # Update metadata DB
        db = get_metadata_db()
        await db.update_document(
            doc_id=doc_id,
            num_chunks=result.get("num_chunks", 0),
            status=result.get("status", "completed"),
        )

        # Rebuild BM25 index
        bm25 = get_bm25()
        bm25.rebuild_from_vector_store()
        await get_cache().invalidate_responses()
        INGEST_TASKS[task_id].update({"status": "completed", "progress": 100, "num_chunks": result.get("num_chunks", 0), "finished_at": int(time.time())})

        logger.info(f"✅ Background ingestion complete: {filename} → {result.get('num_chunks', 0)} chunks")
    except Exception as e:
        logger.error(f"❌ Background ingestion failed for {filename}: {e}")
        db = get_metadata_db()
        await db.update_document(doc_id=doc_id, num_chunks=0, status="failed")
        INGEST_TASKS[task_id].update({"status": "failed", "progress": 100, "error": str(e), "finished_at": int(time.time())})
    finally:
        # Cleanup temp file
        try:
            os.remove(filepath)
        except Exception:
            pass


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """Upload a single file for ingestion. Processing happens in background."""
    # Validate file extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Save to temp location
    doc_id = str(uuid.uuid4())
    temp_filename = f"{doc_id}{ext}"
    temp_path = os.path.join(settings.UPLOAD_DIR, temp_filename)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {str(e)}")

    # Record in metadata DB
    db = get_metadata_db()
    await db.add_document(
        doc_id=doc_id,
        filename=file.filename or "unknown",
        source_type=ext.replace(".", ""),
        title=os.path.splitext(file.filename or "")[0],
        user_id=current_user["id"],
    )

    # Queue background processing
    task_id = str(uuid.uuid4())
    INGEST_TASKS[task_id] = {"task_id": task_id, "status": "queued", "progress": 0, "doc_id": doc_id, "filename": file.filename}
    background_tasks.add_task(
        _process_file_background, temp_path, file.filename or "unknown", doc_id, task_id, current_user["id"]
    )

    return {
        "message": f"File '{file.filename}' queued for processing",
        "doc_id": doc_id,
        "status": "processing",
        "task_id": task_id,
    }


@router.post("/upload-multiple")
async def upload_multiple(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user=Depends(get_current_user),
):
    """Upload multiple files at once."""
    results = []
    for file in files:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            results.append({"filename": file.filename, "status": "skipped", "reason": f"Unsupported: {ext}"})
            continue

        doc_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        temp_filename = f"{doc_id}{ext}"
        temp_path = os.path.join(settings.UPLOAD_DIR, temp_filename)

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        db = get_metadata_db()
        await db.add_document(
            doc_id=doc_id,
            filename=file.filename or "unknown",
            source_type=ext.replace(".", ""),
            title=os.path.splitext(file.filename or "")[0],
            user_id=current_user["id"],
        )

        background_tasks.add_task(
            _process_file_background, temp_path, file.filename or "unknown", doc_id, task_id, current_user["id"]
        )
        INGEST_TASKS[task_id] = {"task_id": task_id, "status": "queued", "progress": 0, "doc_id": doc_id, "filename": file.filename}

        results.append({"filename": file.filename, "doc_id": doc_id, "task_id": task_id, "status": "processing"})

    return {"message": f"Queued {len(results)} files", "results": results}


@router.post("/url", response_model=IngestResponse)
async def ingest_url(
    request: URLIngestRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    """Ingest a web page from a URL."""
    doc_id = str(uuid.uuid4())
    
    # Record in metadata DB
    db = get_metadata_db()
    await db.add_document(
        doc_id=doc_id,
        filename=request.url,
        source_type="web",
        title=request.url,
        user_id=current_user["id"],
    )

    # Queue background processing
    task_id = str(uuid.uuid4())
    INGEST_TASKS[task_id] = {"task_id": task_id, "status": "queued", "progress": 0, "doc_id": doc_id, "filename": request.url}
    background_tasks.add_task(
        _process_url_background, request.url, doc_id, task_id, current_user["id"]
    )

    return {
        "message": f"URL '{request.url}' queued for processing",
        "doc_id": doc_id,
        "status": "processing",
        "task_id": task_id,
    }


@router.get("/documents")
async def list_documents(current_user=Depends(get_current_user)):
    """List all ingested documents."""
    db = get_metadata_db()
    docs = await db.get_all_documents(user_id=current_user["id"])
    return {"documents": docs}


@router.get("/tasks/{task_id}")
async def get_ingest_task(task_id: str, current_user=Depends(get_current_user)):
    task = INGEST_TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task
