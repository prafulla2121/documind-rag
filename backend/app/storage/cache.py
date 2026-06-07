"""
Cache Manager — hybrid caching (Redis with In-Memory fallback).
Supports embedding caching and response caching with TTL.
"""
import hashlib
import json
import time
import logging
from typing import Optional, Any
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Production-grade cache manager.
    Uses Redis if REDIS_URL is configured, otherwise falls back to local in-memory store.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.redis_url = settings.REDIS_URL
        self.redis = None
        self._local_store = {}
        self._local_ttls = {}
        self._corpus_version = 1
        
        if self.redis_url:
            try:
                self.redis = redis.from_url(self.redis_url, decode_responses=True)
                logger.info(f"Redis cache initialized at {self.redis_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}. Falling back to in-memory.")
                self.redis = None
        else:
            logger.info("No REDIS_URL configured. Using in-memory cache.")
            
        self._initialized = True

    def _is_local_expired(self, key: str) -> bool:
        if key in self._local_ttls:
            return time.time() > self._local_ttls[key]
        return False

    # --- Embedding Cache ---

    async def get_embedding(self, text: str) -> Optional[list]:
        key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"
        
        if self.redis:
            try:
                val = await self.redis.get(key)
                if val:
                    return json.loads(val)
            except Exception as e:
                logger.warning(f"Redis get_embedding error: {e}")
        
        # Local fallback
        if key in self._local_store and not self._is_local_expired(key):
            return self._local_store[key]
        return None

    async def set_embedding(self, text: str, embedding: list, ttl: int = 604800):
        key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"
        
        if self.redis:
            try:
                await self.redis.setex(key, ttl, json.dumps(embedding))
                return
            except Exception as e:
                logger.warning(f"Redis set_embedding error: {e}")
        
        # Local store
        self._local_store[key] = embedding
        self._local_ttls[key] = time.time() + ttl

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
        key = self._response_cache_key(query, user_id, filters, model_id)
        
        if self.redis:
            try:
                val = await self.redis.get(key)
                if val:
                    return json.loads(val)
            except Exception as e:
                logger.warning(f"Redis get_response error: {e}")
                
        if key in self._local_store and not self._is_local_expired(key):
            return self._local_store[key]
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
        if not response.get("sources"):
            return # Only cache grounded responses
            
        key = self._response_cache_key(query, user_id, filters, model_id)
        
        if self.redis:
            try:
                await self.redis.setex(key, ttl, json.dumps(response))
                return
            except Exception as e:
                logger.warning(f"Redis set_response error: {e}")
                
        self._local_store[key] = response
        self._local_ttls[key] = time.time() + ttl

    async def invalidate_responses(self):
        """Clear all response cache entries (call after new ingestion)."""
        self._corpus_version += 1
        
        if self.redis:
            try:
                # In Redis we use versioning in the key instead of scanning for keys
                logger.info(f"Incremented corpus version to {self._corpus_version}")
            except Exception as e:
                logger.warning(f"Redis invalidation error: {e}")
        
        keys_to_remove = [k for k in self._local_store if k.startswith("resp:")]
        for k in keys_to_remove:
            self._local_store.pop(k, None)
            self._local_ttls.pop(k, None)
        
        logger.info("Local response cache invalidated")

    def get_cache_stats(self) -> dict:
        emb_count = sum(1 for k in self._local_store if k.startswith("emb:"))
        resp_count = sum(1 for k in self._local_store if k.startswith("resp:"))
        return {
            "mode": "redis" if self.redis else "in-memory",
            "local_embedding_cache": emb_count,
            "local_response_cache": resp_count,
            "corpus_version": self._corpus_version,
        }
