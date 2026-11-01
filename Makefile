# Needs Docker. On Windows without make, run the commands after each target by hand.
.PHONY: up down logs test bench-ingest bench-query

up:
	docker compose up -d --build
	docker compose ps

down:
	docker compose down

logs:
	docker compose logs -f api worker

test:
	pytest tests -q

# Benchmarks against the running stack (compose default key: demo:demo-key).
bench-ingest:
	python bench/ingest_throughput.py --docs 60 --keys $${BENCH_KEYS:-demo:demo-key}

bench-query:
	BENCH_KEYS=$${BENCH_KEYS:-demo:demo-key} locust -f bench/locustfile.py --headless -u 10 -r 10 -t 60s --host http://localhost:8000 --csv bench/results/q10
