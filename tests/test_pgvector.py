"""
pgvector backend against a real Postgres. Skipped unless PGVECTOR_TEST_URL is set, e.g.
    PGVECTOR_TEST_URL=postgresql://postgres:postgres@localhost:5432/documind_test pytest tests/test_pgvector.py
The table is truncated, so point it at a throw-away database.
"""
import os

import pytest

URL = os.getenv("PGVECTOR_TEST_URL")
pytestmark = pytest.mark.skipif(not URL, reason="PGVECTOR_TEST_URL not set")


@pytest.fixture(scope="module")
def store():
    from app.core.config import settings
    from app.ingestion.chunkers.sliding_window import Chunk
    from app.storage.pgvector_store import PgVectorStore

    settings.PGVECTOR_URL = URL
    s = PgVectorStore()
    s.create_collection(vector_dim=3)
    with s.pool.connection() as conn:
        conn.execute("TRUNCATE chunks")
    s.upsert_chunks(
        [Chunk(text="acme lantern is IP67 waterproof", metadata={"tenant_id": "acme", "doc_id": "a1"}, chunk_index=0),
         Chunk(text="globex lantern secret roadmap", metadata={"tenant_id": "globex", "doc_id": "g1"}, chunk_index=0)],
        [[1, 0, 0], [1, 0, 0]],
    )
    return s


def test_dense_search_only_returns_own_tenant(store):
    hits = store.search([1, 0, 0], top_k=10, filters={"tenant_id": "acme"})
    assert [h["metadata"]["doc_id"] for h in hits] == ["a1"]
    assert hits[0]["score"] == pytest.approx(1.0)


def test_keyword_search_only_returns_own_tenant(store):
    hits = store.keyword_search("which lantern is waterproof", filters={"tenant_id": "globex"})
    assert [h["metadata"]["doc_id"] for h in hits] == ["g1"]
    assert store.keyword_search("waterproof", filters={"tenant_id": "acme"})[0]["metadata"]["doc_id"] == "a1"


def test_search_without_tenant_is_refused(store):
    with pytest.raises(ValueError):
        store.search([1, 0, 0], filters={"doc_id": "a1"})
    with pytest.raises(ValueError):
        store.keyword_search("lantern")


def test_extra_filters_use_jsonb_containment(store):
    assert store.search([1, 0, 0], filters={"tenant_id": "acme", "doc_id": "nope"}) == []
