"""
Cross-Encoder Reranker.
Takes top-K candidates from retrieval and re-scores using (query, passage) pairs.
Much more accurate than bi-encoder similarity alone.
"""
from sentence_transformers import CrossEncoder
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class Reranker:
    _instance = None
    _model = None

    def __new__(cls, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", top_k: int = 5):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", top_k: int = 5):
        if self._model is None:
            logger.info(f"Loading reranker model: {model_name}")
            self._model = CrossEncoder(model_name, max_length=512)
            self.top_k = top_k
            logger.info("Reranker model loaded")
        self.top_k = top_k

    def rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        if not candidates:
            return []

        # Create (query, passage) pairs
        pairs = [(query, self._rerank_text(doc)) for doc in candidates]

        # Score all pairs
        scores = self._model.predict(pairs, show_progress_bar=False)

        # Attach scores and sort
        for doc, score in zip(candidates, scores):
            doc["rerank_score"] = float(score)

        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        logger.info(f"Reranked {len(candidates)} → top {self.top_k}")

        return reranked[:self.top_k]

    def _rerank_text(self, doc: Dict) -> str:
        metadata = doc.get("metadata", {})
        metadata_prefix = "\n".join(
            value for value in [
                metadata.get("video_title") or metadata.get("title", ""),
                metadata.get("channel_name", ""),
                metadata.get("filename", ""),
                metadata.get("source_type", ""),
            ]
            if value
        )
        if metadata_prefix:
            return f"{metadata_prefix}\n\n{doc['text']}"
        return doc["text"]
