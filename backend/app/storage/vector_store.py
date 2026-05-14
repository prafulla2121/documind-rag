"""
Vector Store — Qdrant in local file mode (no server needed).
Stores vectors on disk via qdrant_client local path mode.
"""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams,
    PointStruct, Filter, FieldCondition, MatchValue,
)
from typing import List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    _instance = None

    def __new__(cls, path: str = None, collection_name: str = "company_docs"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self, path: str = None, collection_name: str = "company_docs"):
        if self._initialized:
            return
        from app.core.config import settings
        self._path = path or settings.QDRANT_PATH
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.client = QdrantClient(path=self._path)
        self._initialized = True
        logger.info(f"Qdrant initialized at: {self._path}")

    def create_collection(self, vector_dim: int = 384):
        """Create collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in collections:
            logger.info(f"Collection '{self.collection_name}' already exists.")
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_dim,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Created collection '{self.collection_name}' with dim={vector_dim}")

    def upsert_chunks(self, chunks: list, embeddings: List[List[float]]):
        """Batch upsert chunks with their embeddings."""
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            metadata = chunk.metadata if hasattr(chunk, "metadata") else {}
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "text": chunk.text if hasattr(chunk, "text") else str(chunk),
                    "source_url": metadata.get("source_url", ""),
                    "source_type": metadata.get("source_type", ""),
                    "title": metadata.get("title", ""),
                    "section_heading": metadata.get("section_heading", ""),
                    "chunk_index": chunk.chunk_index if hasattr(chunk, "chunk_index") else 0,
                    "chunk_method": metadata.get("chunk_method", ""),
                    "doc_id": metadata.get("doc_id", ""),
                    "filename": metadata.get("filename", ""),
                    "user_id": metadata.get("user_id", "anonymous"),
                },
            ))

        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[i:i + batch_size],
            )
        logger.info(f"Upserted {len(points)} chunks to Qdrant")

    def search(
        self,
        query_vector: List[float],
        top_k: int = 20,
        filters: Optional[dict] = None,
    ) -> list:
        """Dense vector search with optional metadata filtering."""
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(FieldCondition(
                    key=key,
                    match=MatchValue(value=value),
                ))
            qdrant_filter = Filter(must=conditions)

        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
                score_threshold=0.3,
            )
        except Exception as e:
            logger.error(f"Qdrant search error: {e}")
            return []

        return [
            {
                "id": str(r.id),
                "text": r.payload.get("text", ""),
                "score": r.score,
                "metadata": {k: v for k, v in r.payload.items() if k != "text"},
            }
            for r in results
        ]

    def get_collection_info(self) -> dict:
        """Get collection stats."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": str(info.status),
            }
        except Exception:
            return {"vectors_count": 0, "points_count": 0, "status": "not_found"}

    def delete_by_doc_id(self, doc_id: str):
        """Delete all chunks for a document."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )

    def fetch_all_texts(self) -> List[dict]:
        """Fetch all documents for BM25 index building."""
        results = []
        offset = None
        while True:
            response = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
            )
            points, next_offset = response
            for point in points:
                results.append({
                    "id": str(point.id),
                    "text": point.payload.get("text", ""),
                    "metadata": {k: v for k, v in point.payload.items() if k != "text"},
                })
            if next_offset is None:
                break
            offset = next_offset
        return results
