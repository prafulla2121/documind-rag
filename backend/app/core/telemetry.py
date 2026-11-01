"""
HTTP-level observability: structured (JSON) logs with a request id, Prometheus metrics,
and optional Langfuse tracing. RAG-level traces stay in app/rag/observability.py.
"""
import contextvars
import json
import logging
import os
import time
import uuid

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

request_id_var = contextvars.ContextVar("request_id", default="-")

REQUEST_LATENCY = Histogram(
    "documind_request_latency_seconds", "HTTP request latency", ["method", "route", "status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
QUEUE_DEPTH = Gauge("documind_queue_depth", "Ingestion jobs waiting in the queue")
# No tenant label: /metrics has no auth, so it must not list tenant names. Expose it on the internal network only.
RATE_LIMITED = Counter("documind_rate_limited_total", "Requests rejected by the rate limit")


class _RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        out = {
            "ts": round(record.created, 3),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


def setup_logging(fmt: str = "text"):
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(JsonFormatter() if fmt == "json" else logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(request_id)s | %(name)s | %(message)s"
    ))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Sets/returns X-Request-ID and records latency per route template (not raw path)."""

    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            route = request.scope.get("route")
            REQUEST_LATENCY.labels(request.method, getattr(route, "path", "unmatched"), str(status)).observe(
                time.perf_counter() - start
            )
            request_id_var.reset(token)


async def metrics_response(queue=None) -> Response:
    if queue is not None:
        from arq.constants import default_queue_name
        QUEUE_DEPTH.set(await queue.zcard(default_queue_name))
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


_langfuse = None


def langfuse_client():
    """Langfuse client if LANGFUSE_PUBLIC_KEY is set and the SDK is installed, else None."""
    global _langfuse
    if _langfuse is None and os.getenv("LANGFUSE_PUBLIC_KEY"):
        try:
            from langfuse import Langfuse  # optional: pip install langfuse
            _langfuse = Langfuse()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Langfuse disabled: {e}")
            _langfuse = False
    return _langfuse or None
