"""
Tiny local RAG quality smoke test.

Run after ingesting documents:
    python eval_rag_quality.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.api.dependencies import get_bm25, get_embedder, get_vector_store
from app.rag.retriever import HybridRetriever


EVAL_QUERIES = [
    {
        "query": "Explain gradient descent in neural networks",
        "must_include_any": ["gradient", "descent", "neural"],
    },
]


def main() -> int:
    retriever = HybridRetriever(get_vector_store(), get_bm25(), get_embedder())
    failures = []

    for item in EVAL_QUERIES:
        results = retriever.retrieve(item["query"], top_k=5)
        joined = " ".join(result.get("text", "") for result in results).lower()
        if not any(term in joined for term in item["must_include_any"]):
            failures.append(item["query"])

    if failures:
        print("RAG quality smoke test failed for:")
        for query in failures:
            print(f"- {query}")
        return 1

    print("RAG quality smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
