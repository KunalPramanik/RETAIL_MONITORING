"""Unified High-Performance Caching Layer

Provides asynchronous caching with TTL support.
Attempts connection to Redis (if configured and reachable); seamlessly falls back
to an in-memory TTL cache dictionary with zero external dependency requirements.
Supports key-based and prefix/pattern-based invalidation on writes.
"""

import time
import json
import logging
from typing import Optional, Any, Dict

logger = logging.getLogger("secops.cache")


class CacheService:
    def __init__(self):
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._redis = None
        self._redis_checked = False

    async def _get_redis(self):
        if not self._redis_checked:
            self._redis_checked = True
            try:
                import redis.asyncio as aioredis  # type: ignore
                r = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
                await r.ping()
                self._redis = r
                logger.info("Connected to Redis cache backend at redis://localhost:6379/0")
            except Exception as e:
                logger.debug(f"Redis not available ({e}); using high-speed in-memory TTL cache.")
                self._redis = None
        return self._redis

    async def get(self, key: str) -> Optional[Any]:
        """Retrieves cached JSON-serializable item if not expired."""
        r = await self._get_redis()
        if r:
            try:
                data = await r.get(key)
                if data:
                    return json.loads(data)
                return None
            except Exception as err:
                logger.warning(f"Redis get failed ({err}), falling back to memory store")

        entry = self._memory_store.get(key)
        if not entry:
            return None

        if time.monotonic() > entry["expires_at"]:
            del self._memory_store[key]
            return None

        return entry["value"]

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Stores a JSON-serializable value with TTL in seconds."""
        r = await self._get_redis()
        if r:
            try:
                await r.setex(key, ttl_seconds, json.dumps(value, default=str))
                return
            except Exception as err:
                logger.warning(f"Redis set failed ({err}), falling back to memory store")

        self._memory_store[key] = {
            "value": value,
            "expires_at": time.monotonic() + ttl_seconds,
        }

    async def invalidate(self, key_or_prefix: str) -> None:
        """Invalidates keys matching an exact key or prefix string."""
        r = await self._get_redis()
        if r:
            try:
                if "*" in key_or_prefix:
                    keys = await r.keys(key_or_prefix)
                    if keys:
                        await r.delete(*keys)
                else:
                    await r.delete(key_or_prefix)
                    prefix_keys = await r.keys(f"{key_or_prefix}*")
                    if prefix_keys:
                        await r.delete(*prefix_keys)
            except Exception as err:
                logger.warning(f"Redis invalidate failed: {err}")

        # Invalidate in-memory store
        clean_prefix = key_or_prefix.rstrip("*")
        keys_to_delete = [
            k for k in self._memory_store if k == key_or_prefix or k.startswith(clean_prefix)
        ]
        for k in keys_to_delete:
            self._memory_store.pop(k, None)

    async def clear(self) -> None:
        """Clears all cached entries."""
        r = await self._get_redis()
        if r:
            try:
                await r.flushdb()
            except Exception as err:
                logger.warning(f"Redis clear failed: {err}")
        self._memory_store.clear()


cache_service = CacheService()

