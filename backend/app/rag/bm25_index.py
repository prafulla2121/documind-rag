"""
BM25 Index — sparse keyword search alongside Qdrant dense search.
Maintained in parallel for hybrid retrieval.
"""
from rank_bm25 import BM25Okapi
import pickle
import os
import re
from typing import List
import logging

logger = logging.getLogger(__name__)


class BM25Index:

    STOPWORDS = {"the", "a", "an", "is", "in", "of", "to", "and", "or", "for", "it", "on", "at", "by", "be", "this", "that", "with"}

    def __init__(self, index_path: str = None):
        from app.core.config import settings
        self.index_path = index_path or settings.BM25_INDEX_PATH
        self.index = None
        self.doc_store: List[tuple] = []  # (id, text, metadata)

    def build(self, documents: List[dict]):
        """Build BM25 index from a list of {id, text, metadata} dicts."""
        if not documents:
            logger.warning("No documents to build BM25 index from")
            return

        self.doc_store = [(d["id"], d["text"], d.get("metadata", {})) for d in documents]
        tokenized = [self._tokenize(self._search_text(d["text"], d.get("metadata", {}))) for d in documents]
        self.index = BM25Okapi(tokenized)
        self._save()
        logger.info(f"BM25 index built with {len(documents)} documents")

    def search(self, query: str, top_k: int = 20, filters: dict = None) -> List[dict]:
        if not self.index:
            self._load()

        if not self.index:
            return []

        query_tokens = self._tokenize(query)
        scores = self.index.get_scores(query_tokens)

        top_indices = scores.argsort()[::-1]
        
        results = []
        for i in top_indices:
            if scores[i] <= 0:
                continue
            
            metadata = self.doc_store[i][2]
            
            match = True
            if filters:
                for k, v in filters.items():
                    if metadata.get(k) != v:
                        match = False
                        break
                        
            if match:
                results.append({
                    "id": self.doc_store[i][0],
                    "text": self.doc_store[i][1],
                    "score": float(scores[i]),
                    "metadata": metadata,
                    "retrieval_method": "bm25",
                })
                
            if len(results) >= top_k:
                break

        return results

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        tokens = re.findall(r"\b[a-z]{2,}\b", text)
        return [t for t in tokens if t not in self.STOPWORDS]

    def _search_text(self, text: str, metadata: dict) -> str:
        """Blend source metadata into sparse search without changing answer context."""
        metadata_parts = [
            metadata.get("title", ""),
            metadata.get("filename", ""),
            metadata.get("video_title", ""),
            metadata.get("channel_name", ""),
            metadata.get("source_type", ""),
        ]
        title_boost = " ".join(part for part in metadata_parts if part)
        return f"{title_boost}\n{title_boost}\n{text}"

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            with open(self.index_path, "wb") as f:
                pickle.dump({"index": self.index, "doc_store": self.doc_store}, f)
        except Exception as e:
            logger.error(f"Failed to save BM25 index: {e}")

    def _load(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "rb") as f:
                    data = pickle.load(f)
                    self.index = data["index"]
                    self.doc_store = data["doc_store"]
                logger.info(f"BM25 index loaded: {len(self.doc_store)} documents")
            except Exception as e:
                logger.error(f"Failed to load BM25 index: {e}")

    def rebuild_from_vector_store(self):
        """Rebuild BM25 index from all documents in Qdrant."""
        from app.storage.vector_store import VectorStore
        vs = VectorStore()
        all_docs = vs.fetch_all_texts()
        if all_docs:
            self.build(all_docs)
        return len(all_docs)
