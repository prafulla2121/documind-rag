"""
Centralized Embedding Service using sentence-transformers.
Always batch — never embed one at a time.
"""
from sentence_transformers import SentenceTransformer
from typing import List
import hashlib
import logging

logger = logging.getLogger(__name__)


class Embedder:
    _instance = None
    _model = None

    def __new__(cls, model_name: str = "all-MiniLM-L6-v2"):
        if cls._instance is None or cls._model_name != model_name:
            cls._instance = super().__new__(cls)
            cls._model_name = model_name
        return cls._instance

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if self._model is None:
            logger.info(f"Loading embedding model: {model_name}")
            self._model = SentenceTransformer(model_name)
            self.dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded. Dimension: {self.dimension}")

    @property
    def model(self):
        return self._model

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """For ingestion — no prefix."""
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 10,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """For retrieval — adds BGE prefix if using BGE model."""
        if "bge" in self._model_name.lower():
            query = f"Represent this sentence for searching relevant passages: {query}"

        embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        )
        return embedding[0].tolist()

    def get_cache_key(self, text: str) -> str:
        return f"emb:{hashlib.md5(text.encode()).hexdigest()}"
