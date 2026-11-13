"""
Centralized Embedding Service using sentence-transformers.
Always batch — never embed one at a time.
"""
from functools import lru_cache
from typing import List
import hashlib
import logging
import re
import zlib

import httpx
import numpy as np

from app.core.config import settings

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
            # Imported here so demo mode (Gemini embeddings) never loads torch.
            from sentence_transformers import SentenceTransformer
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


def _normalize(rows) -> List[List[float]]:
    arr = np.asarray(rows, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return (arr / np.where(norms == 0, 1, norms)).tolist()


class GeminiEmbedder:
    """Gemini embedding API over REST (httpx), so no torch and no grpc in the process."""
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
    BATCH = 100  # batchEmbedContents request limit

    def __init__(self, model_name: str, api_key: str, dimension: int):
        self.model_name, self.api_key, self.dimension = model_name, api_key, dimension

    def _embed(self, texts: List[str], task_type: str) -> List[List[float]]:
        vectors = []
        for i in range(0, len(texts), self.BATCH):
            requests = [{
                "model": f"models/{self.model_name}",
                "content": {"parts": [{"text": t}]},
                "taskType": task_type,
                "outputDimensionality": self.dimension,
            } for t in texts[i:i + self.BATCH]]
            r = httpx.post(self.URL.format(model=self.model_name), json={"requests": requests},
                           headers={"x-goog-api-key": self.api_key}, timeout=60)
            r.raise_for_status()
            vectors += [e["values"] for e in r.json()["embeddings"]]
        # gemini-embedding-001 only returns unit vectors at its full 3072 dims.
        return _normalize(vectors)

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT") if texts else []

    def embed_query(self, query: str) -> List[float]:
        return self._embed([query], "RETRIEVAL_QUERY")[0]

    def get_cache_key(self, text: str) -> str:
        return f"emb:{self.model_name}:{hashlib.md5(text.encode()).hexdigest()}"


class HashEmbedder:
    """Keyless stub: hashed bag of words. Not semantic; BM25 carries retrieval. For tests and a demo with no key."""
    dimension = 384
    STOPWORDS = frozenset("a an and are as at be by can do does for from has have how i in is it its my of on or "
                          "the that this to was what when where which who why will with you your".split())

    def _vec(self, text: str) -> List[float]:
        v = np.zeros(self.dimension, dtype=np.float32)
        for tok in re.findall(r"\w+", text.lower()):
            if tok not in self.STOPWORDS:
                v[zlib.crc32(tok.encode()) % self.dimension] += 1
        return np.log1p(v)  # damp repeated words so one frequent term cannot dominate

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        return _normalize([self._vec(t) for t in texts]) if texts else []

    def embed_query(self, query: str) -> List[float]:
        return _normalize([self._vec(query)])[0]

    def get_cache_key(self, text: str) -> str:
        return f"emb:hash:{hashlib.md5(text.encode()).hexdigest()}"


@lru_cache(maxsize=1)
def make_embedder():
    """EMBEDDING_PROVIDER picks the backend; see config.py."""
    if settings.EMBEDDING_PROVIDER == "gemini":
        return GeminiEmbedder(settings.GEMINI_EMBEDDING_MODEL, settings.GEMINI_API_KEY, settings.GEMINI_EMBEDDING_DIM)
    if settings.EMBEDDING_PROVIDER == "hash":
        return HashEmbedder()
    return Embedder(model_name=settings.EMBEDDING_MODEL)
