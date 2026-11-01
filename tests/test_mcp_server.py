import asyncio
import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from evals.run_evals import ROOT, SAMPLE_DOC, make_stub_provider
from mcp_server import server


def call(tool: str, args: dict | None = None):
    async def _run():
        async with create_connected_server_and_client_session(server.mcp) as client:
            return await client.call_tool(tool, args or {})
    return asyncio.run(_run())


def payload(result):
    assert not result.isError, result.content
    return json.loads(result.content[0].text) if len(result.content) == 1 else [json.loads(c.text) for c in result.content]


def test_lists_the_three_tools():
    async def _run():
        async with create_connected_server_and_client_session(server.mcp) as client:
            return {t.name for t in (await client.list_tools()).tools}
    assert asyncio.run(_run()) == {"ingest_document", "query", "list_documents"}


@pytest.fixture
def allow_repo(monkeypatch):
    monkeypatch.setattr(server, "ALLOWED_ROOT", ROOT)
    monkeypatch.setattr(server, "get_provider", make_stub_provider)


def test_ingest_list_and_query(allow_repo):
    ingested = payload(call("ingest_document", {"path": str(SAMPLE_DOC)}))
    assert ingested["status"] == "completed" and ingested["num_chunks"] > 0

    docs = payload(call("list_documents"))
    docs = docs if isinstance(docs, list) else [docs]
    assert any(d["doc_id"] == ingested["doc_id"] for d in docs)

    # Stub answers echo the compressed context, so this checks retrieval reached the doc.
    answer = payload(call("query", {"question": "What water resistance rating does the lantern have?"}))
    assert "IP67" in answer["answer"]
    assert answer["sources"][0]["title"] == SAMPLE_DOC.name


def test_ingest_rejects_paths_outside_root(monkeypatch):
    monkeypatch.setattr(server, "ALLOWED_ROOT", SAMPLE_DOC.parent)
    result = call("ingest_document", {"path": str(ROOT / "README.md")})
    assert result.isError
    assert "outside DOCUMIND_MCP_ROOT" in result.content[0].text


def test_ingest_rejects_unsupported_type(allow_repo):
    result = call("ingest_document", {"path": str(ROOT / "evals" / "run_evals.py")})
    assert result.isError
    assert "Unsupported file type" in result.content[0].text
