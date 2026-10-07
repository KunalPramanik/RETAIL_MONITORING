"""Unified High-Performance Caching Layer

Provides asynchronous caching with TTL support.
Attempts connection to Redis (if configured and reachable); seamlessly falls back
to an in-memory TTL cache dictionary with zero external dependency requirements.
Supports key-based and prefix/pattern-based invalidation on writes.
"""

import os
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
            from src.core.config import settings
            redis_url = settings.REDIS_URL or os.getenv("REDIS_URL", "")
            if not redis_url:
                logger.info("REDIS_URL not configured; using high-speed in-memory TTL cache.")
                self._redis = None
                return None
            try:
                import redis.asyncio as aioredis  # type: ignore
                r = aioredis.from_url(redis_url, decode_responses=True)
                await r.ping()
                self._redis = r
                logger.info(f"Connected to Redis cache backend at {redis_url}")
            except Exception as e:
                logger.debug(f"Redis not reachable at {redis_url} ({e}); using high-speed in-memory TTL cache.")
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
        if not entry or not isinstance(entry, dict):
            return None

        expires_at = entry.get("expires_at", 0)
        if time.monotonic() > expires_at:
            self._memory_store.pop(key, None)
            return None

        return entry.get("value")

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Stores a JSON-serializable value with TTL in seconds, enforcing bounded memory limits."""
        r = await self._get_redis()
        if r:
            try:
                await r.setex(key, ttl_seconds, json.dumps(value, default=str))
                return
            except Exception as err:
                logger.warning(f"Redis set failed ({err}), falling back to memory store")

        # Enforce bounded capacity to prevent unbounded memory growth
        MAX_CACHE_ENTRIES = 2048
        if len(self._memory_store) >= MAX_CACHE_ENTRIES:
            now = time.monotonic()
            expired_keys = [k for k, v in self._memory_store.items() if now > v.get("expires_at", 0)]
            for k in expired_keys:
                self._memory_store.pop(k, None)

            # If still saturated, prune oldest 10%
            if len(self._memory_store) >= MAX_CACHE_ENTRIES:
                oldest_keys = sorted(
                    self._memory_store.keys(),
                    key=lambda k: self._memory_store[k].get("expires_at", 0)
                )[:200]
                for k in oldest_keys:
                    self._memory_store.pop(k, None)

        self._memory_store[key] = {
            "value": value,
            "expires_at": time.monotonic() + ttl_seconds,
        }

    async def invalidate(self, key_or_prefix: str) -> None:
        """Invalidates keys matching an exact key or prefix string non-blockingly."""
        r = await self._get_redis()
        if r:
            try:
                # 1. Direct delete of exact key if not wildcard
                if "*" not in key_or_prefix:
                    try:
                        await r.unlink(key_or_prefix)
                    except Exception:
                        await r.delete(key_or_prefix)

                # 2. Incremental non-blocking SCAN iteration to avoid O(N) Redis freeze
                pattern = key_or_prefix if "*" in key_or_prefix else f"{key_or_prefix}*"
                batch = []
                async for k in r.scan_iter(match=pattern, count=100):
                    batch.append(k)
                    if len(batch) >= 100:
                        try:
                            await r.unlink(*batch)
                        except Exception:
                            await r.delete(*batch)
                        batch.clear()

                if batch:
                    try:
                        await r.unlink(*batch)
                    except Exception:
                        await r.delete(*batch)
            except Exception as err:
                logger.warning(f"Redis non-blocking invalidate failed: {err}")

        # Invalidate in-memory fallback store
        clean_prefix = key_or_prefix.rstrip("*")
        keys_to_delete = [
            k for k in list(self._memory_store.keys()) if k == key_or_prefix or k.startswith(clean_prefix)
        ]
        for k in keys_to_delete:
            self._memory_store.pop(k, None)

    async def clear(self) -> None:
        """Clears all cached entries asynchronously."""
        r = await self._get_redis()
        if r:
            try:
                await r.flushdb(asynchronous=True)
            except Exception as err:
                logger.warning(f"Redis async clear failed: {err}")
        self._memory_store.clear()


cache_service = CacheService()

