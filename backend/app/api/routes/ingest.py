"""
Ingest API Routes — handles document upload and ingestion.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from typing import List
import os
import uuid
import logging
import time
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from app.models.schemas import (
    ConnectorIngestRequest,
    IngestResponse,
    SitemapIngestRequest,
    URLIngestRequest,
    YouTubeIngestRequest,
    YouTubeIngestResponse,
)
from app.core.config import settings
from app.core.security import get_current_user
from app.api.dependencies import get_metadata_db, get_bm25, get_cache
from app.ingestion.parsers.youtube_parser import (
    InvalidYouTubeURLError,
    TranscriptNotAvailableError,
    YouTubeMetadataError,
    extract_video_id,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".txt", ".md", ".csv"}
INGEST_TASKS = {}


def _normalize_web_url(url: str) -> str:
    """Normalize user-entered website URLs before queueing ingestion."""
    normalized = url.strip()
    if not normalized:
        raise ValueError("URL is required.")
    if "://" not in normalized:
        normalized = f"https://{normalized}"

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid http or https URL.")
    return normalized


async def _fetch_url_content(url: str) -> str:
    import httpx

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
    }

    last_error = None
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        for attempt in range(3):
            try:
                response = await client.get(url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if content_type and not any(kind in content_type for kind in ("text/html", "text/plain", "application/xhtml")):
                    raise ValueError(f"Unsupported URL content type: {content_type}")
                return response.text
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(1 + attempt)

    raise ValueError(f"Failed to fetch URL content: {last_error}")


def _same_site_links(html_content: str, base_url: str, limit: int) -> list[str]:
    from bs4 import BeautifulSoup

    parsed_base = urlparse(base_url)
    seen = {base_url}
    links = []
    soup = BeautifulSoup(html_content, "lxml")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].split("#", 1)[0].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        try:
            absolute = _normalize_web_url(urljoin(base_url, href))
        except ValueError:
            continue
        parsed = urlparse(absolute)
        if parsed.netloc != parsed_base.netloc or absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
        if len(links) >= limit:
            break
    return links


async def _ingest_single_url(url: str, doc_id: str, user_id: str) -> dict:
    from app.ingestion.pipeline import IngestionPipeline

    html_content = await _fetch_url_content(url)
    pipeline = IngestionPipeline()
    parsed = pipeline.html_parser.parse(html_content, url=url)

    if not parsed.get("text"):
        raise ValueError("No text content could be extracted from the URL")

    return pipeline.ingest_text(
        parsed["text"],
        title=parsed["title"] or url,
        source_type="web",
        user_id=user_id,
        doc_id=doc_id,
        source_url=url,
        filename=url,
    )


async def _process_url_background(
    url: str,
    doc_id: str,
    task_id: str,
    user_id: str,
    crawl: bool = False,
    max_pages: int = 1,
):
    """Background task to fetch and process a URL."""
    try:
        INGEST_TASKS[task_id] = {"task_id": task_id, "status": "running", "progress": 10, "doc_id": doc_id, "started_at": int(time.time())}
        db = get_metadata_db()
        urls = [url]
        if crawl and max_pages > 1:
            first_html = await _fetch_url_content(url)
            urls.extend(_same_site_links(first_html, url, max_pages - 1))

        total_chunks = 0
        for index, page_url in enumerate(urls):
            page_doc_id = doc_id if index == 0 else str(uuid.uuid4())
            if index > 0:
                await db.add_document(
                    doc_id=page_doc_id,
                    filename=page_url,
                    source_type="web",
                    title=page_url,
                    user_id=user_id,
                )
            result = await _ingest_single_url(page_url, page_doc_id, user_id)
            await db.update_document(
                doc_id=page_doc_id,
                num_chunks=result.get("num_chunks", 0),
                status=result.get("status", "completed"),
            )
            total_chunks += result.get("num_chunks", 0)
            INGEST_TASKS[task_id]["progress"] = min(90, 10 + int(((index + 1) / len(urls)) * 75))

        # Rebuild BM25 index
        bm25 = get_bm25()
        bm25.rebuild_from_vector_store()
        await get_cache().invalidate_responses()
        INGEST_TASKS[task_id].update({"status": "completed", "progress": 100, "num_chunks": total_chunks, "pages": len(urls), "finished_at": int(time.time())})

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
    try:
        normalized_url = _normalize_web_url(request.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    doc_id = str(uuid.uuid4())
    
    # Record in metadata DB
    db = get_metadata_db()
    existing = await db.find_document_by_filename(normalized_url, "web", current_user["id"])
    if existing and not request.crawl:
        return {
            "message": f"URL '{normalized_url}' is already in your knowledge base",
            "doc_id": existing["id"],
            "status": "completed",
            "task_id": None,
            "chunks_created": existing.get("num_chunks", 0),
        }

    await db.add_document(
        doc_id=doc_id,
        filename=normalized_url,
        source_type="web",
        title=normalized_url,
        user_id=current_user["id"],
    )

    # Queue background processing
    task_id = str(uuid.uuid4())
    INGEST_TASKS[task_id] = {"task_id": task_id, "status": "queued", "progress": 0, "doc_id": doc_id, "filename": normalized_url}
    background_tasks.add_task(
        _process_url_background,
        normalized_url,
        doc_id,
        task_id,
        current_user["id"],
        request.crawl,
        request.max_pages,
    )

    return {
        "message": f"URL '{normalized_url}' queued for processing",
        "doc_id": doc_id,
        "status": "processing",
        "task_id": task_id,
    }


async def _process_sitemap_background(urls: list[str], task_id: str, user_id: str):
    try:
        db = get_metadata_db()
        total_chunks = 0
        INGEST_TASKS[task_id].update({"status": "running", "progress": 5})
        for index, page_url in enumerate(urls):
            existing = await db.find_document_by_filename(page_url, "web", user_id)
            if existing:
                continue
            doc_id = str(uuid.uuid4())
            await db.add_document(doc_id=doc_id, filename=page_url, source_type="web", title=page_url, user_id=user_id)
            result = await _ingest_single_url(page_url, doc_id, user_id)
            await db.update_document(doc_id=doc_id, num_chunks=result.get("num_chunks", 0), status=result.get("status", "completed"))
            total_chunks += result.get("num_chunks", 0)
            INGEST_TASKS[task_id]["progress"] = min(90, 5 + int(((index + 1) / len(urls)) * 80))

        get_bm25().rebuild_from_vector_store()
        await get_cache().invalidate_responses()
        INGEST_TASKS[task_id].update({"status": "completed", "progress": 100, "num_chunks": total_chunks, "pages": len(urls), "finished_at": int(time.time())})
    except Exception as exc:
        INGEST_TASKS[task_id].update({"status": "failed", "progress": 100, "error": str(exc), "finished_at": int(time.time())})


@router.post("/sitemap", response_model=IngestResponse)
async def ingest_sitemap(
    request: SitemapIngestRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    try:
        sitemap_url = _normalize_web_url(request.url)
        xml_text = await _fetch_url_content(sitemap_url)
        root = ElementTree.fromstring(xml_text.encode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to load sitemap: {exc}")

    urls = []
    for element in root.iter():
        if element.tag.endswith("loc") and element.text:
            try:
                urls.append(_normalize_web_url(element.text))
            except ValueError:
                continue
        if len(urls) >= request.max_pages:
            break

    if not urls:
        raise HTTPException(status_code=400, detail="No page URLs were found in this sitemap.")

    task_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    INGEST_TASKS[task_id] = {"task_id": task_id, "status": "queued", "progress": 0, "doc_id": doc_id, "filename": sitemap_url}
    background_tasks.add_task(_process_sitemap_background, urls, task_id, current_user["id"])
    return {"message": f"Sitemap queued with {len(urls)} page(s)", "doc_id": doc_id, "status": "processing", "task_id": task_id}


@router.post("/connectors", response_model=IngestResponse)
async def ingest_connector(
    request: ConnectorIngestRequest,
    current_user=Depends(get_current_user),
):
    raise HTTPException(
        status_code=501,
        detail=(
            f"{request.connector} connector setup is not configured yet. "
            "Create an OAuth/app credential flow before ingesting private workspace data."
        ),
    )


@router.post("/youtube", response_model=YouTubeIngestResponse)
async def ingest_youtube(
    request: YouTubeIngestRequest,
    current_user=Depends(get_current_user),
):
    """Ingest a YouTube transcript into the knowledge base."""
    user_id = current_user["id"]
    logger.info("YouTube ingestion requested by user %s: %s", user_id, request.url)

    try:
        video_id = extract_video_id(request.url)
    except InvalidYouTubeURLError as exc:
        logger.info("Rejected invalid YouTube URL: %s", request.url)
        raise HTTPException(status_code=422, detail=str(exc))

    db = get_metadata_db()
    existing = await db.get_youtube_source(user_id=user_id, video_id=video_id)
    if existing:
        logger.info("YouTube video %s already ingested for user %s", video_id, user_id)
        return {
            "video_id": existing["video_id"],
            "title": existing["title"],
            "channel_name": existing["channel_name"],
            "thumbnail_url": existing["thumbnail_url"],
            "chunk_count": existing["chunk_count"],
            "already_existed": True,
        }

    try:
        from app.ingestion.pipeline import IngestionPipeline

        doc_id = str(uuid.uuid4())
        logger.info("Starting YouTube pipeline for video %s", video_id)
        result = IngestionPipeline().ingest_youtube(
            request.url,
            user_id=user_id,
            chunker=request.chunker,
            doc_id=doc_id,
        )

        await db.add_document(
            doc_id=doc_id,
            filename=result["title"],
            source_type="youtube",
            title=result["title"],
            content_hash=video_id,
            user_id=user_id,
        )
        await db.update_document(
            doc_id=doc_id,
            num_chunks=result["num_chunks"],
            status=result.get("status", "completed"),
        )
        await db.add_youtube_source(
            user_id=user_id,
            video_id=result["video_id"],
            title=result["title"],
            channel_name=result["channel_name"],
            thumbnail_url=result["thumbnail_url"],
            duration_secs=result.get("duration_seconds", 0),
            chunk_count=result["num_chunks"],
        )

        bm25 = get_bm25()
        bm25.rebuild_from_vector_store()
        await get_cache().invalidate_responses()

        logger.info("YouTube video %s ingested for user %s", video_id, user_id)
        return {
            "video_id": result["video_id"],
            "title": result["title"],
            "channel_name": result["channel_name"],
            "thumbnail_url": result["thumbnail_url"],
            "chunk_count": result["num_chunks"],
            "already_existed": False,
        }
    except TranscriptNotAvailableError as exc:
        logger.info("Transcript unavailable for video %s: %s", video_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except (InvalidYouTubeURLError, YouTubeMetadataError, ValueError) as exc:
        logger.info("YouTube ingestion failed for video %s: %s", video_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/documents")
async def list_documents(current_user=Depends(get_current_user)):
    """List all ingested documents."""
    db = get_metadata_db()
    docs = await db.get_all_documents(user_id=current_user["id"])
    return {"documents": docs}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, current_user=Depends(get_current_user)):
    db = get_metadata_db()
    deleted = await db.delete_document(doc_id, current_user["id"])
    if not deleted:
        raise HTTPException(404, "Document not found")

    from app.storage.vector_store import VectorStore
    VectorStore().delete_by_doc_id(doc_id)
    get_bm25().rebuild_from_vector_store()
    await get_cache().invalidate_responses()
    return {"status": "success"}


@router.post("/documents/{doc_id}/reindex")
async def reindex_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    db = get_metadata_db()
    document = await db.get_document(doc_id, current_user["id"])
    if not document:
        raise HTTPException(404, "Document not found")
    if document["source_type"] != "web":
        raise HTTPException(400, "Re-index is currently supported for web sources.")

    from app.storage.vector_store import VectorStore
    VectorStore().delete_by_doc_id(doc_id)
    await db.update_document(doc_id, num_chunks=0, status="processing")
    task_id = str(uuid.uuid4())
    INGEST_TASKS[task_id] = {"task_id": task_id, "status": "queued", "progress": 0, "doc_id": doc_id, "filename": document["filename"]}
    background_tasks.add_task(_process_url_background, document["filename"], doc_id, task_id, current_user["id"])
    return {"status": "processing", "task_id": task_id}


@router.post("/recrawl-stale")
async def recrawl_stale_web_sources(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    db = get_metadata_db()
    documents = await db.get_all_documents(user_id=current_user["id"])
    web_docs = [doc for doc in documents if doc["source_type"] == "web"]
    queued = []
    from app.storage.vector_store import VectorStore
    for doc in web_docs:
        VectorStore().delete_by_doc_id(doc["id"])
        await db.update_document(doc["id"], num_chunks=0, status="processing")
        task_id = str(uuid.uuid4())
        INGEST_TASKS[task_id] = {"task_id": task_id, "status": "queued", "progress": 0, "doc_id": doc["id"], "filename": doc["filename"]}
        background_tasks.add_task(_process_url_background, doc["filename"], doc["id"], task_id, current_user["id"])
        queued.append({"doc_id": doc["id"], "task_id": task_id})
    return {"status": "processing", "queued": queued}


@router.get("/tasks/{task_id}")
async def get_ingest_task(task_id: str, current_user=Depends(get_current_user)):
    task = INGEST_TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task
