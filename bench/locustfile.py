"""
Query load test for /v1/query.

    BENCH_KEYS=acme:acme-key,globex:globex-key locust -f bench/locustfile.py --headless \
        -u 10 -r 10 -t 60s --host http://127.0.0.1:8000 --csv bench/results/q10

Questions come from evals/golden.jsonl. A counter is appended to each question so
every request misses the response cache and runs the full retrieval path
(the tokenizers ignore digits and '#', so retrieval sees the same words).
"""
import itertools
import json
import os
import random
import time
from pathlib import Path

from locust import HttpUser, between, task

GOLDEN = Path(__file__).resolve().parent.parent / "evals" / "golden.jsonl"
QUESTIONS = [json.loads(line)["question"] for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
KEYS = [pair.split(":", 1)[1] for pair in os.environ["BENCH_KEYS"].split(",")]
COUNTER = itertools.count(int(time.time() * 1000))  # unique across runs, so no cache hits


class QueryUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.key = random.choice(KEYS)

    @task
    def ask(self):
        q = f"{random.choice(QUESTIONS)} #{next(COUNTER)}"
        with self.client.post("/v1/query", json={"query": q}, headers={"X-API-Key": self.key},
                              name="/v1/query", catch_response=True) as r:
            if r.status_code == 200 and r.json().get("from_cache"):
                r.failure("cache hit (benchmark should measure the full path)")
