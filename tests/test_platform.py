"""
Platform API tests: tenant isolation, the async ingestion queue path, rate limits, metrics.

Redis is fakeredis (in-process) and the queue runs through a real arq Worker in burst
mode, so enqueue -> worker -> job status is the same code path as production. The vector
store is the default Qdrant temp index from conftest; tests/test_pgvector.py covers pgvector.
"""
import asyncio

import httpx
import pytest
from arq import Worker
from arq.connections import ArqRedis
from fakeredis import FakeServer
from fakeredis.aioredis import FakeRedis

from evals.run_evals import SAMPLE_DOC
from app.api import dependencies
from app.core.config import settings
from app.core.tenancy import parse_tenant_keys
from app.worker import ingest_file_job

KEYS = {"acme": "acme-key-123", "globex": "globex-key-456"}
QUESTION = "What water resistance rating does the lantern have?"


def headers(tenant):
    return {"X-API-Key": KEYS[tenant]}


@pytest.fixture
def platform(monkeypatch):
    dependencies.get_cache()  # create the cache singleton before REDIS_URL is faked below
    monkeypatch.setattr(settings, "TENANT_API_KEYS", ",".join(f"{t}:{k}" for t, k in KEYS.items()))
    monkeypatch.setattr(settings, "PLATFORM_LLM_PROVIDER", "stub")
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1000)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake")  # only so /metrics reads queue depth
    monkeypatch.setattr("arq.worker.log_redis_info", _no_info)  # fakeredis has no INFO command
    yield
    dependencies._queue = None


async def _no_info(*_):
    pass


async def fake_queue() -> ArqRedis:
    dependencies._queue = ArqRedis(connection_pool=FakeRedis(server=FakeServer()).connection_pool)
    return dependencies._queue


def client():
    from app.main import app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def run_worker(queue):
    async def startup(ctx):
        from app.ingestion.pipeline import IngestionPipeline
        ctx["pipeline"] = IngestionPipeline()
        ctx["cache"] = dependencies.get_cache()

    worker = Worker(functions=[ingest_file_job], redis_pool=queue, burst=True, on_startup=startup,
                    handle_signals=False, poll_delay=0.05)
    await worker.main()  # burst: returns when the queue is empty (no close(): it sends SIGUSR1, absent on Windows)
    return worker


def test_parse_tenant_keys():
    keys = parse_tenant_keys(" acme:k1 , globex:k2 ")
    assert sorted(keys.values()) == ["acme", "globex"]
    assert "k1" not in keys  # only hashes are kept
    with pytest.raises(ValueError) as err:
        parse_tenant_keys("acme:k1,broken")
    assert "k1" not in str(err.value)
    with pytest.raises(ValueError):
        parse_tenant_keys("default:k3")  # reserved for legacy /api data


def test_pipeline_filters_every_search_by_tenant():
    from app.api.dependencies import get_bm25, get_pipeline
    from app.ingestion.pipeline import IngestionPipeline
    from evals.run_evals import make_stub_provider

    IngestionPipeline().ingest_file(str(SAMPLE_DOC), user_id="iso", tenant_id="tenant-a")
    get_bm25().rebuild_from_vector_store()
    pipeline = get_pipeline()

    own = asyncio.run(pipeline.query(QUESTION, make_stub_provider(), user_id="iso", tenant_id="tenant-a"))
    other = asyncio.run(pipeline.query(QUESTION, make_stub_provider(), user_id="iso", tenant_id="tenant-b"))
    assert "IP67" in own["answer"] and own["sources"]
    assert other["sources"] == [] and "IP67" not in other["answer"]

    # A caller-supplied filter cannot widen the search to another tenant.
    forged = asyncio.run(pipeline.query(QUESTION, make_stub_provider(), user_id="iso",
                                        tenant_id="tenant-b", filters={"tenant_id": "tenant-a"}))
    assert forged["sources"] == []


def test_queue_path_and_tenant_isolation_over_http(platform):
    async def scenario():
        queue = await fake_queue()
        async with client() as c:
            assert (await c.post("/v1/query", json={"query": QUESTION})).status_code == 401
            assert (await c.post("/v1/query", json={"query": QUESTION},
                                 headers={"X-API-Key": "nope"})).status_code == 401

            resp = await c.post("/v1/documents", headers=headers("acme"),
                                files={"file": (SAMPLE_DOC.name, SAMPLE_DOC.read_bytes(), "text/markdown")})
            assert resp.status_code == 202, resp.text
            job_id = resp.json()["job_id"]

            queued = (await c.get(f"/v1/jobs/{job_id}", headers=headers("acme"))).json()
            assert queued["status"] == "queued"
            # The API only enqueued: nothing is indexed for acme until the worker runs.
            assert (await c.post("/v1/query", json={"query": QUESTION}, headers=headers("acme"))).json()["sources"] == []
            # Another tenant cannot see the job.
            assert (await c.get(f"/v1/jobs/{job_id}", headers=headers("globex"))).status_code == 404

            worker = await run_worker(queue)
            assert worker.jobs_complete == 1 and worker.jobs_failed == 0

            done = (await c.get(f"/v1/jobs/{job_id}", headers=headers("acme"))).json()
            assert done["status"] == "complete" and done["success"] is True
            assert done["result"]["num_chunks"] > 0

            mine = (await c.post("/v1/query", json={"query": QUESTION}, headers=headers("acme"))).json()
            theirs = (await c.post("/v1/query", json={"query": QUESTION}, headers=headers("globex"))).json()
            assert "IP67" in mine["answer"] and mine["sources"]
            assert theirs["sources"] == [] and "IP67" not in theirs["answer"]

            bad = await c.post("/v1/documents", headers=headers("acme"), files={"file": ("x.exe", b"MZ", "application/octet-stream")})
            assert bad.status_code == 400

    asyncio.run(scenario())


def test_rate_limit_is_per_tenant(platform, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)

    async def scenario():
        await fake_queue()
        async with client() as c:
            codes = [(await c.get("/v1/jobs/none", headers=headers("acme"))).status_code for _ in range(3)]
            assert codes == [404, 404, 429]
            limited = await c.get("/v1/jobs/none", headers=headers("acme"))
            assert int(limited.headers["Retry-After"]) > 0
            # globex has its own budget
            assert (await c.get("/v1/jobs/none", headers=headers("globex"))).status_code == 404

    asyncio.run(scenario())


def test_metrics_and_request_id(platform):
    async def scenario():
        queue = await fake_queue()
        await queue.enqueue_job("ingest_file_job", path="x", filename="x", tenant_id="acme")
        async with client() as c:
            resp = await c.get("/health", headers={"X-Request-ID": "req-42"})
            assert resp.headers["X-Request-ID"] == "req-42"
            assert len((await c.get("/health")).headers["X-Request-ID"]) == 32
            text = (await c.get("/metrics")).text
            assert 'documind_request_latency_seconds_bucket{le="0.01",method="GET",route="/health",status="200"}' in text
            assert "documind_queue_depth 1.0" in text

    asyncio.run(scenario())
