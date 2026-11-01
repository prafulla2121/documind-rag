"""
Tenant auth + rate limit for the /v1 platform API.

Each tenant has its own API key (TENANT_API_KEYS="acme:key1,globex:key2"). The key
maps to a tenant_id, and that tenant_id is the filter on every read and write.
"""
import hashlib
import hmac
import time

from fastapi import Depends, Header, HTTPException

from app.core.config import settings
from app.core.telemetry import RATE_LIMITED

RATE_WINDOW_SECONDS = 60


def parse_tenant_keys(raw: str) -> dict[str, str]:
    """'acme:key1,globex:key2' -> {sha256(key): tenant}. Only hashes are kept in memory."""
    keys = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        tenant, sep, key = pair.partition(":")
        if not sep or not tenant.strip() or not key.strip():
            raise ValueError(f"Bad TENANT_API_KEYS entry: {pair.split(':')[0]}:***")
        if tenant.strip() == "default":
            raise ValueError("Tenant name 'default' is reserved for the legacy /api data")
        keys[hashlib.sha256(key.strip().encode()).hexdigest()] = tenant.strip()
    return keys


def _lookup(api_key: str) -> str | None:
    digest = hashlib.sha256(api_key.encode()).hexdigest()
    # shortcut: keys come from an env var, re-parsed per request (microseconds); move to a DB table for self-serve keys.
    for known, tenant in parse_tenant_keys(settings.TENANT_API_KEYS).items():
        if hmac.compare_digest(known, digest):
            return tenant
    return None


async def require_tenant(x_api_key: str = Header(default="")) -> str:
    tenant = _lookup(x_api_key) if x_api_key else None
    if not tenant:
        raise HTTPException(401, "Missing or invalid X-API-Key")
    return tenant


async def rate_limited_tenant(tenant: str = Depends(require_tenant)) -> str:
    """Fixed one-minute window per tenant, counted in Redis so all API replicas share it."""
    from app.api.dependencies import get_queue

    redis = await get_queue()
    window = int(time.time() // RATE_WINDOW_SECONDS)
    key = f"ratelimit:{tenant}:{window}"
    async with redis.pipeline(transaction=True) as pipe:
        count, _ = await pipe.incr(key).expire(key, RATE_WINDOW_SECONDS * 2).execute()
    if count > settings.RATE_LIMIT_PER_MINUTE:
        RATE_LIMITED.inc()
        retry = RATE_WINDOW_SECONDS - int(time.time()) % RATE_WINDOW_SECONDS
        raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": str(retry)})
    return tenant
