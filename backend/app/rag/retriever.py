"""
Hybrid Retriever — combines dense (Qdrant) + sparse (BM25) via Reciprocal Rank Fusion.
"""
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    RRF FORMULA: score(d) = Σ 1/(k + rank(d))
    k=60 reduces impact of high-rank outliers.
    """

    def __init__(self, vector_store, bm25_index, embedder):
        self.vector_store = vector_store
        self.bm25 = bm25_index
        self.embedder = embedder
        self.k = 60  # RRF constant

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[dict] = None,
    ) -> List[Dict]:

        # 1. Dense retrieval (Qdrant)
        query_vector = self.embedder.embed_query(query)
        dense_results = self.vector_store.search(
            query_vector, top_k=top_k, filters=filters
        )

        # 2. Sparse retrieval (BM25)
        sparse_results = self.bm25.search(query, top_k=top_k, filters=filters)

        # 3. Reciprocal Rank Fusion
        fused = self._rrf_merge(dense_results, sparse_results)

        logger.info(f"Retrieved: {len(dense_results)} dense, {len(sparse_results)} sparse → {len(fused)} fused")

        return fused[:top_k]

    def _rrf_merge(self, dense: List[Dict], sparse: List[Dict]) -> List[Dict]:
        rrf_scores = {}
        all_docs = {}

        # Score dense results
        for rank, doc in enumerate(dense):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (self.k + rank + 1)
            all_docs[doc_id] = {**doc, "retrieval_methods": ["dense"]}

        # Score sparse results
        for rank, doc in enumerate(sparse):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (self.k + rank + 1)
            if doc_id in all_docs:
                all_docs[doc_id]["retrieval_methods"].append("sparse")
            else:
                all_docs[doc_id] = {**doc, "retrieval_methods": ["sparse"]}

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)

        result = []
        for doc_id in sorted_ids:
            doc = all_docs[doc_id]
            doc["rrf_score"] = rrf_scores[doc_id]
            result.append(doc)

        return result
