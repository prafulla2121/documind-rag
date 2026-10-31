"""
DocuMind MCP server (stdio).

Exposes the DocuMind RAG pipeline as MCP tools, running in-process:
  ingest_document(path)   parse, chunk, embed and index a local file
  query(question)         hybrid retrieval + rerank + LLM answer with sources
  list_documents()        documents currently in the index

Run:  python mcp_server/server.py
Env:  DOCUMIND_LLM_PROVIDER (default ollama), DOCUMIND_LLM_MODEL (default LLM_MODEL),
      DOCUMIND_LLM_API_KEY, DOCUMIND_LLM_BASE_URL, DOCUMIND_USER_ID (default anonymous),
      DOCUMIND_MCP_ROOT (only files under this folder can be ingested; default: home dir)
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from app.api.dependencies import get_bm25, get_cache, get_pipeline, get_vector_store  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.ingestion.pipeline import IngestionPipeline  # noqa: E402
from app.providers.base import ModelConfig  # noqa: E402
from app.providers.registry import get_llm_provider  # noqa: E402

SUPPORTED = {".pdf", ".docx", ".html", ".htm", ".txt", ".md", ".csv"}
USER_ID = os.getenv("DOCUMIND_USER_ID", "anonymous")
ALLOWED_ROOT = Path(os.getenv("DOCUMIND_MCP_ROOT") or Path.home()).resolve()

mcp = FastMCP("documind")


def get_provider():
    return get_llm_provider(ModelConfig(
        provider=os.getenv("DOCUMIND_LLM_PROVIDER", "ollama"),
        model_name=os.getenv("DOCUMIND_LLM_MODEL", settings.LLM_MODEL),
        api_key=os.getenv("DOCUMIND_LLM_API_KEY", ""),
        api_base_url=os.getenv("DOCUMIND_LLM_BASE_URL", ""),
    ))


@mcp.tool()
async def ingest_document(path: str) -> dict:
    """Index a local file (pdf, docx, html, txt, md, csv) so it can be queried."""
    file = Path(path).expanduser().resolve()
    # The caller is an LLM: never let it read files outside the folder the user allowed.
    if not file.is_relative_to(ALLOWED_ROOT):
        raise ValueError(f"Path is outside DOCUMIND_MCP_ROOT ({ALLOWED_ROOT})")
    if not file.is_file():
        raise ValueError(f"File not found: {file}")
    if file.suffix.lower() not in SUPPORTED:
        raise ValueError(f"Unsupported file type {file.suffix}; use one of {sorted(SUPPORTED)}")

    result = await asyncio.to_thread(IngestionPipeline().ingest_file, str(file), file.name, USER_ID)
    if result.get("num_chunks"):
        # Same follow-up as the HTTP upload route: refresh BM25 and drop stale cached answers.
        get_bm25().rebuild_from_vector_store()
        await get_cache().invalidate_responses()
    return {k: result.get(k) for k in ("doc_id", "title", "num_chunks", "status")}


@mcp.tool()
async def query(question: str, top_k: int = 10) -> dict:
    """Answer a question from the indexed documents. Returns the answer and its sources."""
    if not question.strip():
        raise ValueError("question is empty")
    result = await get_pipeline().query(
        question, get_provider(), user_id=USER_ID, rag_config={"top_k": max(1, min(top_k, 50))},
    )
    return {
        "answer": result["answer"],
        "sources": [
            {"title": s.get("title"), "excerpt": s.get("excerpt"), "score": round(float(s.get("score") or 0), 4)}
            for s in result.get("sources", [])
        ],
    }


@mcp.tool()
async def list_documents() -> list[dict]:
    """List documents in the index (read from the vector store, so it shows what query can see)."""
    docs: dict[str, dict] = {}
    for chunk in await asyncio.to_thread(get_vector_store().fetch_all_texts):
        meta = chunk["metadata"]
        if meta.get("user_id") != USER_ID:
            continue
        doc = docs.setdefault(meta.get("doc_id", ""), {
            "doc_id": meta.get("doc_id", ""),
            "title": meta.get("title", ""),
            "source_type": meta.get("source_type", ""),
            "num_chunks": 0,
        })
        doc["num_chunks"] += 1
    return list(docs.values())


if __name__ == "__main__":
    mcp.run()  # stdio transport
