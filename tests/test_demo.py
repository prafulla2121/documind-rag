"""DEMO_MODE guards: no server-side URL fetching, upload size cap, query rate limit, example questions."""
import asyncio
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import tenancy
from app.core.config import settings


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    monkeypatch.setattr(tenancy, "_demo_counts", {"hour": None, "day": None, "ips": {}, "total": 0})


def client():
    from app.main import app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def test_demo_refuses_url_fetching_and_big_uploads(demo):
    async def scenario():
        async with client() as c:
            for path, body in [("/api/ingest/url", {"url": "http://169.254.169.254/"}),
                               ("/api/ingest/sitemap", {"url": "http://localhost/sitemap.xml"}),
                               ("/api/ingest/youtube", {"url": "https://youtu.be/dQw4w9WgXcQ"}),
                               ("/api/models/validate", {"provider": "ollama", "model_name": "x", "api_base_url": "http://10.0.0.1"})]:
                r = await c.post(path, json=body)
                assert r.status_code == 403, path
            big = b"a" * (1024 * 1024 + 1)
            r = await c.post("/api/ingest/upload", files={"file": ("big.txt", big, "text/plain")})
            assert r.status_code == 413
            info = (await c.get("/api/demo")).json()
            assert info["demo_mode"] is True and len(info["examples"]) == 3
    asyncio.run(scenario())


def test_demo_rate_limit_per_ip_hour_and_per_day(demo, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_QUERIES_PER_HOUR", 2)
    monkeypatch.setattr(settings, "DEMO_QUERIES_PER_DAY", 3)

    def req(ip):
        return Request({"type": "http", "headers": [(b"x-forwarded-for", ip.encode())], "client": ("10.0.0.1", 1)})

    async def scenario():
        await tenancy.demo_rate_limit(req("1.1.1.1"))
        await tenancy.demo_rate_limit(req("1.1.1.1"))
        with pytest.raises(HTTPException) as per_ip:
            await tenancy.demo_rate_limit(req("1.1.1.1"))
        assert per_ip.value.status_code == 429
        await tenancy.demo_rate_limit(req("2.2.2.2"))  # other visitor still allowed
        with pytest.raises(HTTPException):  # global daily cap (3) reached
            await tenancy.demo_rate_limit(req("3.3.3.3"))
    asyncio.run(scenario())


def test_rate_limit_is_off_outside_demo(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    asyncio.run(tenancy.demo_rate_limit(None))


def test_hash_embedder_ranks_shared_words_higher():
    from app.ingestion.embedder import HashEmbedder
    e = HashEmbedder()
    q = e.embed_query("battery charge time")
    near, far = e.embed_documents(["How long does the battery take to charge", "Warranty covers the glass"])
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    assert dot(q, near) > dot(q, far)


def test_demo_process_never_imports_torch(tmp_path):
    """Demo app with the hash embedder and reranker off: preload + one query, no torch in sys.modules."""
    code = """
import asyncio, sys, httpx
from app.main import app
async def go():
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/api/query/", json={"query": "How long does the HL-7 battery last?", "stream": False})
            assert r.status_code == 200 and r.json()["sources"], r.text
asyncio.run(go())
assert "torch" not in sys.modules and "sentence_transformers" not in sys.modules
print("ok")
"""
    root = Path(__file__).resolve().parent.parent
    env = {**__import__("os").environ, "DEMO_MODE": "true", "EMBEDDING_PROVIDER": "hash", "GEMINI_API_KEY": "",
           "PLATFORM_LLM_PROVIDER": "stub", "DATA_DIR": str(tmp_path), "UPLOAD_DIR": str(tmp_path / "up"),
           "QDRANT_PATH": str(tmp_path / "q"), "BM25_INDEX_PATH": str(tmp_path / "bm25.pkl"),
           "SQLITE_DB_PATH": str(tmp_path / "m.db"), "REDIS_URL": ""}
    out = subprocess.run([sys.executable, "-c", code], cwd=root / "backend", env=env, capture_output=True, text=True, timeout=300)
    assert out.stdout.strip().endswith("ok"), out.stderr[-2000:]
