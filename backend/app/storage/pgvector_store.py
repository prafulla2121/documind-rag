"""
Postgres + pgvector backend: one `chunks` table holds text, metadata, the embedding
and a generated tsvector. Dense search uses an HNSW cosine index; keyword search uses
Postgres full-text search, so it replaces the per-process BM25 pickle and stays current
when a separate worker process ingests.

Every search must carry a tenant_id filter; it is a real column, not a JSON field.
"""
import json
import logging
import re
import uuid
from typing import List, Optional

from psycopg_pool import ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    doc_id text NOT NULL,
    text text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{{}}',
    embedding vector({dim}) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tenant_doc ON chunks (tenant_id, doc_id);
CREATE INDEX IF NOT EXISTS chunks_tsv ON chunks USING gin (tsv);
"""
SCORE_THRESHOLD = 0.15  # same cut-off as the Qdrant backend


def _vec(values: List[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


def _split_filters(filters: Optional[dict]) -> tuple[str, dict]:
    filters = dict(filters or {})
    tenant_id = filters.pop("tenant_id", None)
    if not tenant_id:
        raise ValueError("pgvector search needs a tenant_id filter")
    return tenant_id, filters


class PgVectorStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.pool = ConnectionPool(settings.pgvector_dsn, min_size=1, max_size=10, open=True)
            cls._instance._ready = False
        return cls._instance

    def create_collection(self, vector_dim: int = 384):
        if self._ready:
            return
        with self.pool.connection() as conn:
            conn.execute(SCHEMA.format(dim=int(vector_dim)))
        self._ready = True

    def upsert_chunks(self, chunks: list, embeddings: List[List[float]]):
        rows = []
        for chunk, embedding in zip(chunks, embeddings):
            meta = {**chunk.metadata, "chunk_index": chunk.chunk_index}
            rows.append((
                str(uuid.uuid4()), meta.get("tenant_id", "default"), meta.get("doc_id", ""),
                chunk.text, json.dumps(meta, default=str), _vec(embedding),
            ))
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (id, tenant_id, doc_id, text, metadata, embedding) "
                "VALUES (%s, %s, %s, %s, %s::jsonb, %s::vector)",
                rows,
            )
        logger.info(f"Inserted {len(rows)} chunks into pgvector")

    def search(self, query_vector: List[float], top_k: int = 20, filters: Optional[dict] = None) -> list:
        tenant_id, extra = _split_filters(filters)
        vec = _vec(query_vector)
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT id, text, metadata, 1 - (embedding <=> %s::vector) AS score FROM chunks "
                "WHERE tenant_id = %s AND metadata @> %s::jsonb "
                "ORDER BY embedding <=> %s::vector LIMIT %s",
                (vec, tenant_id, json.dumps(extra), vec, top_k),
            ).fetchall()
        return [
            {"id": str(r[0]), "text": r[1], "score": float(r[3]), "metadata": r[2]}
            for r in rows if r[3] >= SCORE_THRESHOLD
        ]

    def keyword_search(self, query: str, top_k: int = 20, filters: Optional[dict] = None) -> list:
        tenant_id, extra = _split_filters(filters)
        # OR the words (plainto_tsquery would AND them, which misses most natural questions).
        words = re.findall(r"[a-z]{2,}", query.lower())
        if not words:
            return []
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT id, text, metadata, ts_rank(tsv, q) AS score "
                "FROM chunks, to_tsquery('english', %s) q "
                "WHERE tenant_id = %s AND metadata @> %s::jsonb AND tsv @@ q "
                "ORDER BY score DESC LIMIT %s",
                (" | ".join(words), tenant_id, json.dumps(extra), top_k),
            ).fetchall()
        return [
            {"id": str(r[0]), "text": r[1], "score": float(r[3]), "metadata": r[2], "retrieval_method": "fts"}
            for r in rows
        ]

    def get_collection_info(self) -> dict:
        try:
            with self.pool.connection() as conn:
                count = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
            return {"vectors_count": count, "points_count": count, "status": "green"}
        except Exception:
            return {"vectors_count": 0, "points_count": 0, "status": "not_found"}

    def delete_by_doc_id(self, doc_id: str):
        with self.pool.connection() as conn:
            conn.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))

    def fetch_all_texts(self) -> List[dict]:
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT id, text, metadata FROM chunks").fetchall()
        return [{"id": str(r[0]), "text": r[1], "metadata": r[2]} for r in rows]


class PgKeywordIndex:
    """Stands in for BM25Index when VECTOR_BACKEND=pgvector. Postgres keeps it current."""

    def search(self, query: str, top_k: int = 20, filters: dict = None) -> list:
        return PgVectorStore().keyword_search(query, top_k=top_k, filters=filters)

    def rebuild_from_vector_store(self) -> int:
        return PgVectorStore().get_collection_info()["points_count"]
