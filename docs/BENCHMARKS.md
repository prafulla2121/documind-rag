# Benchmarks

Measured on 2026-11-01. Every number here comes from a run on the machine below; nothing is
estimated. Raw locust output is in [`bench/results/`](../bench/results/).

## Machine and setup

| | |
| --- | --- |
| CPU | Intel Core i5-1155G7 (4 cores / 8 threads), laptop |
| RAM | 16 GB |
| OS | Windows 11 Home, Python 3.12.10, torch 2.15 CPU |
| Postgres | 16.2 + pgvector 0.6.2 (the `pgserver` pip package's binaries; no Docker on this machine) |
| Redis | Microsoft Garnet 2.2.5 (Redis-protocol server) on 127.0.0.1 |
| API | 1 uvicorn process unless stated, `VECTOR_BACKEND=pgvector`, `LOG_FORMAT=json` |
| Worker | 1 arq worker, `WORKER_MAX_JOBS=2` |
| Models | all-MiniLM-L6-v2 embeddings, ms-marco-MiniLM-L-6-v2 reranker, both on CPU |
| LLM | `PLATFORM_LLM_PROVIDER=stub` (returns the retrieved context; no model call) |
| Load generator | locust 2.47 on the same laptop (it shares the CPU) |

So these numbers measure the platform (HTTP, auth, rate limit, queue, embedding, pgvector +
full-text search, reranking, compression), **not** an LLM. A real LLM adds its own latency on top.

Not the docker-compose stack: Docker is not installed here. The services are the same
software (Postgres + pgvector, a Redis-protocol server, the same app code) run as local processes.

## Ingestion throughput (queue → worker → pgvector)

```bash
python bench/ingest_throughput.py --docs 60 --keys acme:acme-key,globex:globex-key
```

60 markdown documents (each `evals/harbor_lamp_guide.md`, 2.7 KB, 8 chunks, with a unique first
line), spread over 2 tenants, uploaded one after another, then polled until every job completed.
Time runs from the first upload to the last job finishing.

| Run | Failed | Chunks | Upload (60 files) | End to end | Docs/min | Chunks/min |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 480 | 0.37 s | 15.7 s | 229.8 | 1,838 |
| 2 | 0 | 480 | 0.39 s | 15.8 s | 228.2 | 1,826 |
| 3 | 0 | 480 | 0.29 s | 18.1 s | 198.4 | 1,587 |

The API accepts uploads at 150–210 docs/s; the worker is the bottleneck, as intended.

**Bug found by this benchmark:** in the first runs, `GET /v1/jobs/{id}` sometimes returned 404 for
a job that existed. arq's `Job.info()` reads the result key and then the job key; a job that
finishes between the two reads is in neither. Fixed in `api/routes/v1.py` by re-reading the result
before answering 404. Before the fix 2 of 3 runs hit it; after it, 3 of 3 passed.

## Query latency (`POST /v1/query`)

```bash
BENCH_KEYS=acme:acme-key,globex:globex-key locust -f bench/locustfile.py --headless \
    -u 10 -r 10 -t 60s --host http://127.0.0.1:8000 --csv bench/results/q10
```

Corpus during the test: 3,848 chunks (acme 1,928, globex 1,920). Each locust user waits 0.5–1.5 s
between requests and asks a golden-set question with a unique counter appended, so every request
misses the response cache (verified: 0 cache hits reported). 60 s per run.

| Users | API processes | Requests | Failures | p50 | p95 | Max | Req/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 40 | 0 | 470 ms | 860 ms | 1.1 s | 0.68 |
| 10 | 1 | 120 | 0 | 3.7 s | 6.4 s | 6.4 s | 2.09 |
| 25 | 1 | 125 | 0 | 10.0 s | 13.0 s | 13.1 s | 2.16 |
| 10 | 4 (torch default threads) | 26 | 0 | 14.0 s | 22.0 s | 21.9 s | 0.48 |
| 25 | 4 (torch default threads) | 51 | 4 (500) | 19.0 s | 44.0 s | 43.6 s | 1.00 |
| 10 | 4 (`OMP_NUM_THREADS=2`) | 106 | 0 | 3.2 s | 9.2 s | 13.3 s | 1.77 |
| 25 | 4 (`OMP_NUM_THREADS=2`) | 131 | 0 | 9.2 s | 15.0 s | 16.6 s | 2.26 |

Numbers are locust's final console summary. The CSV files are its last periodic snapshot, so
their counts can be one or two requests lower.

### Where the time goes

Per-stage timings from `RAGPipeline` for the 15 golden questions, in-process, no cache,
3 separate runs (median per run):

| Stage | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| Retrieval (embed + pgvector + full-text, RRF) | 131 ms | 121 ms | 137 ms |
| Cross-encoder rerank | 608 ms | 770 ms | 973 ms |
| Context build + compression | 6 ms | 12 ms | 13 ms |
| Total | 826 ms | 949 ms | 1,161 ms |

### What this shows

- **The reranker is the cost.** It is 74–84% of query time; vector + keyword search in Postgres
  is about 120–140 ms.
- **Throughput tops out at about 2.1–2.3 req/s on this laptop**, and latency then grows with
  queue length (p50 3.7 s at 10 users, 10 s at 25).
- **More API processes did not help here.** With 4 processes and default torch threads, each
  process tried to use all 8 CPU threads; throughput fell to 0.48–1.0 req/s and 4 requests
  failed with 500 (Redis connect timeouts: the event loop was blocked longer than arq's 1 s
  connect timeout). Limiting torch to 2 threads per process removed the failures but gave the
  same ~2.2 req/s as one process. The limit is total CPU for cross-encoder inference, not the
  process model.
- Tried and dropped: lowering the cross-encoder `max_length` from 512 to 256 tokens did not
  lower rerank time (chunks are already shorter than 256 tokens), so the change was reverted.
- Next steps that would move the number: rerank fewer candidates (`top_k` 10 → 5, check evals),
  a quantized / ONNX reranker, a GPU inference service shared by API replicas, or more machines.

## Retrieval quality on both backends

`python evals/run_evals.py --provider stub` (15 golden questions, 1 document, 8 chunks):

| Backend | hit@1 | hit@5 | MRR | Evidence survives compression |
| --- | --- | --- | --- | --- |
| Qdrant + BM25 (default) | 0.93 | 1.00 | 0.97 | 0.80 |
| pgvector + Postgres full-text search | 0.93 | 1.00 | 0.97 | 0.80 |

Same scores, but the set is tiny; it shows no regression here, not equal quality at scale.

## Reproduce

Docker (recommended): `make up`, then `make bench-ingest` and `make bench-query` against the
compose stack (`demo:demo-key`). Without Docker, start Postgres with pgvector and a
Redis-compatible server, then run the API and worker from `backend/` as in the README, with
`VECTOR_BACKEND=pgvector PLATFORM_LLM_PROVIDER=stub RATE_LIMIT_PER_MINUTE=1000000`.
