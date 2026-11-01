import asyncio

from evals.run_evals import SAMPLE_DOC, first_hit_rank, hit_rate, load_golden, mrr, run, to_markdown


def test_first_hit_rank_ignores_case_and_whitespace():
    chunks = ["nothing here", "It  WEIGHS\n410 grams."]
    assert first_hit_rank(chunks, "weighs 410 grams") == 2
    assert first_hit_rank(chunks, "IP67") is None


def test_hit_rate_and_mrr():
    ranks = [1, 2, None, 5]
    assert hit_rate(ranks, 1) == 0.25
    assert hit_rate(ranks, 5) == 0.75
    assert mrr(ranks) == (1 + 0.5 + 0.2) / 4
    assert hit_rate([], 5) == 0.0 and mrr([]) == 0.0


def test_golden_set_is_answerable_from_sample_doc():
    doc = " ".join(SAMPLE_DOC.read_text(encoding="utf-8").lower().split())
    golden = load_golden()
    assert 10 <= len(golden) <= 20
    assert len({g["id"] for g in golden}) == len(golden)
    for item in golden:
        assert " ".join(item["evidence"].lower().split()) in doc, item["id"]


def test_intent_detection_does_not_match_inside_words():
    from app.rag.query_processor import QueryProcessor

    qp = QueryProcessor()
    assert qp._detect_intent("Which light mode runs the longest?") != "chitchat"
    assert qp._detect_intent("How bright is High mode?") != "chitchat"
    assert qp._detect_intent("hi there") == "chitchat"


def test_stub_eval_end_to_end():
    results = asyncio.run(run("stub", "stub", k=5))
    summary = results["summary"]
    assert summary["questions"] == len(load_golden())
    assert summary["hit_rate_at_5"] >= 0.9
    assert summary["answered_from_docs"] == 1.0
    assert "| hit_rate_at_5 |" in to_markdown(results)
