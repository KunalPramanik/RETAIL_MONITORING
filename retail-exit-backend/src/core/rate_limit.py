"""Distributed & In-Memory Rate Limiting Engine

Provides sliding-window rate limiting for sensitive endpoints (Auth, Camera Hardware Probes, OCR).
Gracefully leverages Redis Pub/Sub / Cache when available, falling back to local thread-safe deques.
"""

import time
import logging
from collections import deque
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
from src.core.config import settings

logger = logging.getLogger("secops.core.rate_limit")

# Global in-memory storage: key -> deque of timestamp floats
_memory_storage: Dict[str, deque] = {}
_redis_client = None


async def get_redis_client():
    """Lazily retrieves or initializes the async Redis client if configured."""
    global _redis_client
    if not settings.REDIS_URL:
        return None
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
            )
        except Exception as e:
            logger.warning(f"Failed to connect to Redis for rate limiting: {e}. Falling back to in-memory store.")
            _redis_client = None
    return _redis_client


def get_client_identifier(request: Request) -> str:
    """Extracts client IP address or forwarding proxy header."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        if client_ip:
            return client_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown_client"


class RateLimiter:
    """FastAPI Dependency for enforcing sliding-window request quotas."""

    def __init__(self, times: int, seconds: int = 60, scope: str = "default"):
        self.times = times
        self.seconds = seconds
        self.scope = scope

    async def __call__(self, request: Request):
        client_id = get_client_identifier(request)
        key = f"ratelimit:{self.scope}:{client_id}"
        now = time.time()
        window_start = now - self.seconds

        # Attempt Redis sliding window if configured
        redis = await get_redis_client()
        if redis is not None:
            try:
                pipe = redis.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, self.seconds)
                results = await pipe.execute()
                current_count = results[1]

                if current_count >= self.times:
                    retry_after = max(1, int(self.seconds))
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded for {self.scope}. Maximum {self.times} requests per {self.seconds}s.",
                        headers={"Retry-After": str(retry_after)},
                    )
                return True
            except HTTPException:
                raise
            except Exception as e:
                logger.debug(f"Redis rate limit check error ({e}), falling back to in-memory bucket.")

        # In-memory sliding window fallback
        bucket = _memory_storage.setdefault(key, deque())
        while bucket and bucket[0] <= window_start:
            bucket.popleft()

        if len(bucket) >= self.times:
            oldest = bucket[0]
            retry_after = max(1, int(oldest + self.seconds - now) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {self.scope}. Maximum {self.times} requests per {self.seconds}s.",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        return True


def clear_rate_limit_storage():
    """Utility function to clear in-memory rate limiting storage (primarily for test isolation)."""
    _memory_storage.clear()

