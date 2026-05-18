"""
Pydantic schemas for API request/response models.
"""
from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from datetime import datetime


# ── Query ──────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    stream: bool = False
    filters: dict = {}
    session_id: Optional[str] = None


class SourceInfo(BaseModel):
    index: int
    title: str = ""
    filename: str = ""
    source_type: str = ""
    url: str = ""
    section: str = ""
    score: float = 0.0
    retrieval_methods: List[str] = []
    excerpt: str = ""
    video_id: str = ""
    video_title: str = ""
    channel_name: str = ""
    thumbnail_url: str = ""
    start_seconds: float = 0.0
    timestamp: str = ""
    citation: str = ""


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceInfo] = []
    intent: str = "factual"
    query_rewritten: str = ""
    chunks_retrieved: int = 0
    chunks_after_rerank: int = 0
    latency_ms: int = 0
    stage_timings: dict = {}
    from_cache: bool = False


# ── Ingestion ──────────────────────────────────────────

class IngestResponse(BaseModel):
    message: str
    doc_id: str
    task_id: Optional[str] = None
    chunks_created: int = 0
    status: str = "success"


class URLIngestRequest(BaseModel):
    url: str
    crawl: bool = False
    max_pages: int = Field(default=10, ge=1, le=50)


class SitemapIngestRequest(BaseModel):
    url: str
    max_pages: int = Field(default=50, ge=1, le=200)


class ConnectorIngestRequest(BaseModel):
    connector: Literal["confluence", "notion", "google_drive", "sharepoint"]
    url: str = ""
    access_token: str = ""
    max_items: int = Field(default=25, ge=1, le=200)


class YouTubeIngestRequest(BaseModel):
    url: str
    chunker: Literal["sliding_window", "structural", "semantic"] = "sliding_window"


class YouTubeIngestResponse(BaseModel):
    video_id: str
    title: str
    channel_name: str
    thumbnail_url: str
    chunk_count: int
    already_existed: bool


class IngestStatusResponse(BaseModel):
    doc_id: str
    filename: str
    status: str
    chunks_created: int = 0
    created_at: Optional[datetime] = None


# ── Auth ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = "user"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "user"


# ── Admin ──────────────────────────────────────────────

class SystemStats(BaseModel):
    total_documents: int = 0
    total_chunks: int = 0
    ollama_status: str = "unknown"
    qdrant_status: str = "unknown"


class FeedbackRequest(BaseModel):
    query_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str = ""


# ── Internal Models ────────────────────────────────────

class RawDocument(BaseModel):
    source_id: str
    source_type: str  # "pdf", "docx", "html", "txt"
    filename: str
    title: str = ""
    raw_content: str = ""
    metadata: dict = {}
    content_hash: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChunkData(BaseModel):
    text: str
    chunk_index: int
    start_char: int = 0
    end_char: int = 0
    metadata: dict = {}
