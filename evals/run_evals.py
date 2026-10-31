"""
DocuMind eval runner.

Ingests evals/harbor_lamp_guide.md into a throw-away index, runs every
question in evals/golden.jsonl through the real retriever, reranker and
RAGPipeline, and writes a markdown report.

    # CI / no API keys: real retrieval, stub LLM, judge skipped
    python evals/run_evals.py --provider stub

    # Local model as answerer and judge
    python evals/run_evals.py --provider ollama --model llama3.2:3b

Any provider from app/providers/registry.py works (openai, anthropic, gemini,
groq, ...); the key is read from LLM_API_KEY.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = ROOT / "evals"
SAMPLE_DOC = EVALS_DIR / "harbor_lamp_guide.md"
GOLDEN = EVALS_DIR / "golden.jsonl"
EVAL_USER = "eval-user"


# ── Metrics ─────────────────────────────────────────────

def first_hit_rank(chunk_texts: list[str], evidence: str) -> int | None:
    """1-based rank of the first chunk that contains the evidence phrase."""
    needle = " ".join(evidence.lower().split())
    for rank, text in enumerate(chunk_texts, 1):
        if needle in " ".join(text.lower().split()):
            return rank
    return None


def hit_rate(ranks: list[int | None], k: int) -> float:
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks) if ranks else 0.0


def mrr(ranks: list[int | None]) -> float:
    return sum(1 / r for r in ranks if r) / len(ranks) if ranks else 0.0


def load_golden(path: Path = GOLDEN) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── Offline provider ────────────────────────────────────

def make_stub_provider():
    from app.providers.base import BaseLLMProvider, ModelConfig

    class StubProvider(BaseLLMProvider):
        """Not a model. Answers RAG prompts by echoing the retrieved context so the
        pipeline runs end to end without keys. Other prompts (query rewrite,
        expansion) raise, and the pipeline falls back to its non-LLM path."""

        async def generate(self, messages):
            if messages[0]["role"] != "system":
                raise RuntimeError("stub provider only answers RAG prompts")
            context = messages[-1]["content"].split("CONTEXT:", 1)[-1].split("\n---\n", 1)[0]
            return context.strip()

        async def stream(self, messages):
            yield await self.generate(messages)

        def get_token_count(self, text: str) -> int:
            return len(text) // 4

        def __str__(self):
            return "stub"

    return StubProvider(ModelConfig(provider="stub", model_name="stub", api_key=""))


def make_provider(name: str, model: str):
    if name == "stub":
        return make_stub_provider()
    from app.providers.base import ModelConfig
    from app.providers.registry import get_llm_provider
    return get_llm_provider(ModelConfig(
        provider=name,
        model_name=model,
        api_key=os.getenv("LLM_API_KEY", ""),
        api_base_url=os.getenv("LLM_BASE_URL", ""),
        temperature=0.0,
    ))


# ── Runner ──────────────────────────────────────────────

def isolate_storage() -> Path:
    """Point every app data path at a temp dir. Must run before `app` is imported."""
    tmp = Path(tempfile.mkdtemp(prefix="documind-eval-"))
    os.environ.update({
        "DATA_DIR": str(tmp),
        "UPLOAD_DIR": str(tmp / "uploads"),
        "QDRANT_PATH": str(tmp / "qdrant"),
        "BM25_INDEX_PATH": str(tmp / "bm25.pkl"),
        "SQLITE_DB_PATH": str(tmp / "metadata.db"),
        "REDIS_URL": "",
    })
    sys.path.insert(0, str(ROOT / "backend"))
    return tmp


async def run(provider_name: str, model: str, k: int) -> dict:
    from app.api.dependencies import get_bm25, get_pipeline
    from app.ingestion.pipeline import IngestionPipeline
    from app.rag.observability import RAGEvaluator

    ingested = IngestionPipeline().ingest_file(str(SAMPLE_DOC), user_id=EVAL_USER)
    get_bm25().rebuild_from_vector_store()
    pipeline = get_pipeline()
    llm = make_provider(provider_name, model)
    judge = None if provider_name == "stub" else RAGEvaluator(llm)

    rows = []
    for item in load_golden():
        question = item["question"]
        candidates = pipeline.retriever.retrieve(question, top_k=10, filters={"user_id": EVAL_USER})
        ranked = pipeline.reranker.rerank(question, candidates, limit=k)
        contexts = [c["text"] for c in ranked]
        # What the LLM actually sees: the pipeline compresses reranked chunks to a few sentences.
        compressed = pipeline.compressor.compress(question, ranked)
        result = await pipeline.query(question, llm, user_id=EVAL_USER)
        scores = await judge.evaluate(question, result["answer"], contexts) if judge else {}
        rows.append({
            **item,
            "rank": first_hit_rank(contexts, item["evidence"]),
            "in_context": first_hit_rank([compressed], item["evidence"]) is not None,
            "intent": result.get("intent"),
            "chunks_used": result.get("chunks_after_rerank", 0),
            "answer_out": result["answer"],
            **scores,
        })

    ranks = [r["rank"] for r in rows]
    summary = {
        "provider": provider_name,
        "model": model if provider_name != "stub" else "stub",
        "doc_chunks": ingested["num_chunks"],
        "questions": len(rows),
        "k": k,
        "hit_rate_at_1": hit_rate(ranks, 1),
        f"hit_rate_at_{k}": hit_rate(ranks, k),
        "mrr": mrr(ranks),
        "evidence_survives_compression": sum(r["in_context"] for r in rows) / len(rows),
        "answered_from_docs": sum(1 for r in rows if r["chunks_used"]) / len(rows),
    }
    if judge:
        for metric in ("faithfulness", "relevance"):
            summary[metric] = sum(r[metric] for r in rows) / len(rows)
    return {"summary": summary, "rows": rows}


def to_markdown(results: dict) -> str:
    s = results["summary"]
    lines = ["# DocuMind eval report", ""]
    lines += ["| Metric | Value |", "| --- | --- |"]
    for key, value in s.items():
        lines.append(f"| {key} | {value:.2f} |" if isinstance(value, float) else f"| {key} | {value} |")
    if "faithfulness" not in s:
        lines += ["", "_Stub provider: faithfulness and answer relevance (LLM-as-judge) were skipped. "
                  "Retrieval metrics are real._"]
    lines += ["", "| id | question | evidence rank | in compressed context | intent | chunks used | faithfulness | relevance |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in results["rows"]:
        lines.append(
            f"| {r['id']} | {r['question']} | {r['rank'] or 'miss'} | {'yes' if r['in_context'] else 'no'} "
            f"| {r['intent']} | {r['chunks_used']} "
            f"| {r.get('faithfulness', '-')} | {r.get('relevance', '-')} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", default="stub")
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--k", type=int, default=5, help="rerank depth used for hit rate")
    parser.add_argument("--out", default=str(EVALS_DIR / "report.md"))
    parser.add_argument("--min-hit-rate", type=float, default=0.0, help="exit 1 if hit_rate@k is below this")
    args = parser.parse_args(argv)

    isolate_storage()
    results = asyncio.run(run(args.provider, args.model, args.k))
    report = to_markdown(results)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)

    if results["summary"][f"hit_rate_at_{args.k}"] < args.min_hit_rate:
        print(f"FAIL: hit_rate@{args.k} below {args.min_hit_rate}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
