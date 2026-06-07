"""
RAG Observability — structured JSONL trace logging for every pipeline run.
Append to rag_traces.jsonl for offline analysis and quality improvement.
"""
import time
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RAGTracer:
    """
    Logs every RAG pipeline step to a JSONL file.
    Each line = one complete query trace. Easy to grep, parse, and analyze.
    """

    def __init__(self, log_dir: str = "logs"):
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        self.log_file = Path(log_dir) / "rag_traces.jsonl"

    def log_trace(
        self,
        session_id: str,
        user_id: str,
        query: str,
        retrieved_chunks: list,
        reranked_chunks: list,
        final_answer: str,
        latency_ms: float,
        model_used: str,
        intent: str = "",
        query_rewritten: str = "",
        eval_scores: Optional[dict] = None,
    ):
        trace = {
            "ts": time.time(),
            "session_id": session_id,
            "user_id": user_id,
            "query": query,
            "query_rewritten": query_rewritten,
            "intent": intent,
            "retrieved_count": len(retrieved_chunks),
            "reranked_count": len(reranked_chunks),
            "answer_preview": final_answer[:300],
            "latency_ms": latency_ms,
            "model": model_used,
            "eval": eval_scores or {},
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace) + "\n")
        except Exception as e:
            logger.error(f"Failed to write trace: {e}")

    def read_recent(self, n: int = 50) -> list:
        """Read the N most recent traces for the admin dashboard."""
        if not self.log_file.exists():
            return []
        try:
            lines = self.log_file.read_text(encoding="utf-8").strip().splitlines()
            return [json.loads(l) for l in lines[-n:] if l]
        except Exception:
            return []


class RAGEvaluator:
    """
    LLM-as-judge evaluation: measures RAG quality without ground truth.
    Faithfulness (0–1): Is the answer grounded in the retrieved context?
    Relevance (0–1): Does the answer address the user's question?
    """

    def __init__(self, llm_provider):
        self.llm = llm_provider

    async def faithfulness(self, answer: str, contexts: list) -> float:
        ctx = "\n---\n".join(contexts[:3])  # Use top 3 chunks to avoid token overflow
        prompt = f"""Rate from 0.0 to 1.0 how faithful this answer is to the given context.
1.0 = every claim directly supported by context.
0.0 = answer contains hallucinated facts not in context.
Reply with ONLY a decimal number, nothing else.

Context:
{ctx}

Answer: {answer}

Faithfulness score:"""
        try:
            r = await self.llm.generate([{"role": "user", "content": prompt}])
            return max(0.0, min(1.0, float(r.strip())))
        except Exception:
            return 0.5

    async def relevance(self, query: str, answer: str) -> float:
        prompt = f"""Rate from 0.0 to 1.0 how well this answer addresses the question.
1.0 = directly and completely answers.
0.0 = off-topic or non-answer.
Reply with ONLY a decimal number, nothing else.

Question: {query}
Answer: {answer}

Relevance score:"""
        try:
            r = await self.llm.generate([{"role": "user", "content": prompt}])
            return max(0.0, min(1.0, float(r.strip())))
        except Exception:
            return 0.5

    async def evaluate(self, query: str, answer: str, chunks: list) -> dict:
        f = await self.faithfulness(answer, chunks)
        r = await self.relevance(query, answer)
        return {
            "faithfulness": round(f, 2),
            "relevance": round(r, 2),
            "overall": round((f + r) / 2, 2),
        }
