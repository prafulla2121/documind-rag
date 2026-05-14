"""
In-Memory Cache — replaces Redis for no-Docker setup.
Two-level cache: embedding cache + response cache.
"""
import hashlib
import json
import time
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    In-memory cache with TTL support.
    For production, replace with Redis.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._store = {}
            cls._ttls = {}
            cls._corpus_version = 1
        return cls._instance

    def _is_expired(self, key: str) -> bool:
        if key in self._ttls:
            return time.time() > self._ttls[key]
        return False

    def _cleanup_expired(self):
        """Remove expired entries (called periodically)."""
        expired = [k for k in self._ttls if self._is_expired(k)]
        for k in expired:
            self._store.pop(k, None)
            self._ttls.pop(k, None)

    # --- Embedding Cache ---

    async def get_embedding(self, text: str) -> Optional[list]:
        key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"
        if key in self._store and not self._is_expired(key):
            return self._store[key]
        return None

    async def set_embedding(self, text: str, embedding: list, ttl: int = 604800):
        key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"
        self._store[key] = embedding
        self._ttls[key] = time.time() + ttl

    # --- Response Cache ---

    def _response_cache_key(
        self,
        query: str,
        user_id: str = "anonymous",
        filters: Optional[dict] = None,
        model_id: str = "unknown",
    ) -> str:
        normalized = " ".join(query.lower().strip().split())
        payload = json.dumps(
            {
                "q": normalized,
                "u": user_id,
                "f": filters or {},
                "m": model_id,
                "v": self._corpus_version,
            },
            sort_keys=True,
        )
        return f"resp:{hashlib.md5(payload.encode()).hexdigest()}"

    async def get_response(
        self,
        query: str,
        user_id: str = "anonymous",
        filters: Optional[dict] = None,
        model_id: str = "unknown",
    ) -> Optional[dict]:
        key = self._response_cache_key(
            query=query,
            user_id=user_id,
            filters=filters,
            model_id=model_id,
        )
        if key in self._store and not self._is_expired(key):
            return self._store[key]
        return None

    async def set_response(
        self,
        query: str,
        response: dict,
        user_id: str = "anonymous",
        filters: Optional[dict] = None,
        model_id: str = "unknown",
        ttl: int = 3600,
    ):
        key = self._response_cache_key(
            query=query,
            user_id=user_id,
            filters=filters,
            model_id=model_id,
        )
        if response.get("sources"):
            self._store[key] = response
            self._ttls[key] = time.time() + ttl

    async def invalidate_responses(self):
        """Clear all response cache entries (call after new ingestion)."""
        keys_to_remove = [k for k in self._store if k.startswith("resp:")]
        for k in keys_to_remove:
            self._store.pop(k, None)
            self._ttls.pop(k, None)
        self._corpus_version += 1
        logger.info(f"Invalidated {len(keys_to_remove)} cached responses")

    def get_cache_stats(self) -> dict:
        self._cleanup_expired()
        emb_count = sum(1 for k in self._store if k.startswith("emb:"))
        resp_count = sum(1 for k in self._store if k.startswith("resp:"))
        return {
            "embedding_cache": emb_count,
            "response_cache": resp_count,
            "corpus_version": self._corpus_version,
        }
