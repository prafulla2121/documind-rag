"""
Ingestion throughput through the real queue: upload N documents to /v1/documents,
then poll /v1/jobs until every job is done. Reports docs/min and chunks/min measured
from the first upload to the last job finishing (API + Redis + worker + Postgres).

    python bench/ingest_throughput.py --docs 60 --keys acme:acme-key,globex:globex-key

Each document is evals/harbor_lamp_guide.md (2.7 KB, 8 chunks) with a unique header line.
"""
import argparse
import statistics
import time
from pathlib import Path

import httpx

DOC = (Path(__file__).resolve().parent.parent / "evals" / "harbor_lamp_guide.md").read_text(encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://127.0.0.1:8000")
    p.add_argument("--docs", type=int, default=60)
    p.add_argument("--keys", required=True, help="tenant:key,tenant:key (docs are spread across tenants)")
    args = p.parse_args()
    keys = [pair.split(":", 1)[1] for pair in args.keys.split(",")]

    with httpx.Client(base_url=args.host, timeout=60) as c:
        start = time.perf_counter()
        jobs = []
        for i in range(args.docs):
            key = keys[i % len(keys)]
            body = f"# Bench copy {i}\n\n{DOC}".encode()
            r = c.post("/v1/documents", headers={"X-API-Key": key}, files={"file": (f"doc{i}.md", body, "text/markdown")})
            r.raise_for_status()
            jobs.append((r.json()["job_id"], key))
        enqueue_s = time.perf_counter() - start

        pending, done = dict(jobs), {}
        while pending:
            for job_id, key in list(pending.items()):
                resp = c.get(f"/v1/jobs/{job_id}", headers={"X-API-Key": key})
                if resp.status_code != 200:
                    raise SystemExit(f"job {job_id}: HTTP {resp.status_code} {resp.text[:300]}")
                r = resp.json()
                if r["status"] == "complete":
                    done[job_id] = r
                    pending.pop(job_id)
            time.sleep(0.2)
        total_s = time.perf_counter() - start

    failed = [j for j in done.values() if not j["success"]]
    chunks = sum(j["result"]["num_chunks"] for j in done.values() if j["success"])
    print(f"docs={args.docs} failed={len(failed)} chunks={chunks}")
    print(f"enqueue_all_s={enqueue_s:.2f} (API accept rate {args.docs / enqueue_s:.1f} docs/s)")
    print(f"end_to_end_s={total_s:.1f} docs_per_min={args.docs / total_s * 60:.1f} chunks_per_min={chunks / total_s * 60:.0f}")


if __name__ == "__main__":
    main()
