"""Phase 4 Realtime Gateway & Cache Optimization Test Suite

Covers:
- F4: WebSocket gateway resilience (dead-connection pruning, send timeout, heartbeat keep-alive, ping-pong, token authentication)
- F6: Non-blocking cache invalidation (SCAN / UNLINK cursor pagination replacing blocking KEYS, async flushdb)
"""

import asyncio
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from jose import jwt

from src.core.config import settings
from src.realtime.hub import ConnectionManager
from src.realtime.events import WebSocketEnvelope
from src.cache import CacheService
from src.main import app


@pytest.mark.asyncio
async def test_websocket_broadcast_parallel_send_timeout_pruning():
    """F4: Verifies that a hung/slow client times out during broadcast and is pruned without blocking peer clients."""
    hub = ConnectionManager()
    await hub.start()

    fast_ws = AsyncMock()
    fast_ws.accept = AsyncMock()
    fast_ws.send_text = AsyncMock()

    slow_ws = AsyncMock()
    slow_ws.accept = AsyncMock()
    async def hung_send(data):
        await asyncio.sleep(2.0)
    slow_ws.send_text = hung_send

    await hub.connect(fast_ws)
    await hub.connect(slow_ws)
    assert len(hub.active_connections) == 2

    # Temporarily set send timeout to 0.1s
    orig_timeout = settings.websocket.send_timeout_sec
    settings.websocket.send_timeout_sec = 0.1
    try:
        t0 = time.monotonic()
        await hub.broadcast_event("new_event", {"eventId": "EVT-100", "status": "VERIFIED"})
        elapsed = time.monotonic() - t0

        # Broadcast completed promptly due to parallel execution and timeout
        assert elapsed < 0.5
        # Fast client received message
        assert fast_ws.send_text.await_count == 1
        # Slow/hanging client was pruned from active connections
        assert fast_ws in hub.active_connections
        assert slow_ws not in hub.active_connections
        assert len(hub.active_connections) == 1
    finally:
        settings.websocket.send_timeout_sec = orig_timeout
        await hub.stop()


@pytest.mark.asyncio
async def test_websocket_heartbeat_pinger():
    """F4: Verifies that heartbeat_pinger emits periodic telemetry envelopes."""
    hub = ConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock(side_effect=lambda data: hub.disconnect(mock_ws))

    await hub.connect(mock_ws)

    orig_interval = settings.websocket.ping_interval_sec
    settings.websocket.ping_interval_sec = 0.01
    try:
        await asyncio.wait_for(hub.heartbeat_pinger(mock_ws), timeout=1.0)
        assert mock_ws.send_text.await_count == 1
        sent_envelope = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent_envelope["type"] == "heartbeat"
        assert sent_envelope["payload"]["status"] == "HEALTHY"
    finally:
        settings.websocket.ping_interval_sec = orig_interval
        await hub.stop()


def test_websocket_gateway_token_authentication():
    """F4: Verifies that /ws/live enforces JWT token verification when tokens are supplied or required."""
    client = TestClient(app)

    # 1. Invalid token is rejected with 4003 policy violation
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/live?token=invalid_garbage_token"):
            pass

    # 2. Valid JWT token is accepted
    valid_token = jwt.encode(
        {"sub": "admin", "role": "ADMIN", "exp": int(time.time()) + 3600},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    with client.websocket_connect(f"/ws/live?token={valid_token}") as ws:
        # Ping-pong exchange
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"


def test_websocket_gateway_json_ping_pong():
    """F4: Verifies structured JSON ping/pong exchange on /ws/live."""
    client = TestClient(app)
    with client.websocket_connect("/ws/live") as ws:
        ws.send_text(json.dumps({"type": "ping"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "pong"
        assert "timestamp" in resp


@pytest.mark.asyncio
async def test_cache_memory_non_blocking_invalidation():
    """F6: Verifies in-memory TTL cache invalidation with exact keys, prefixes, and wildcards."""
    cache = CacheService()

    await cache.set("cameras:list", {"count": 4}, ttl_seconds=60)
    await cache.set("cameras:detail:cam1", {"ip": "10.0.0.1"}, ttl_seconds=60)
    await cache.set("products:catalog", ["SKU1", "SKU2"], ttl_seconds=60)

    # Assert keys are present
    assert await cache.get("cameras:list") == {"count": 4}
    assert await cache.get("cameras:detail:cam1") == {"ip": "10.0.0.1"}
    assert await cache.get("products:catalog") == ["SKU1", "SKU2"]

    # Invalidate by prefix "cameras"
    await cache.invalidate("cameras")
    assert await cache.get("cameras:list") is None
    assert await cache.get("cameras:detail:cam1") is None
    # Unrelated namespace preserved
    assert await cache.get("products:catalog") == ["SKU1", "SKU2"]

    # Invalidate by wildcard pattern "products:*"
    await cache.invalidate("products:*")
    assert await cache.get("products:catalog") is None


@pytest.mark.asyncio
async def test_cache_redis_scan_unlink_invalidation():
    """F6: Verifies that Redis invalidation uses non-blocking scan_iter and unlink instead of keys and delete."""
    cache = CacheService()

    mock_redis = AsyncMock()
    # Mock scan_iter returning keys in batches
    async def async_scan_iter(match, count):
        for k in ["cameras:item1", "cameras:item2", "cameras:item3"]:
            yield k

    mock_redis.scan_iter = async_scan_iter
    mock_redis.unlink = AsyncMock()
    mock_redis.flushdb = AsyncMock()

    cache._redis = mock_redis
    cache._redis_checked = True

    # Invalidate prefix
    await cache.invalidate("cameras")

    # Assert unlink was called for the batch instead of blocking keys
    assert mock_redis.unlink.await_count >= 1
    # Verify mock_redis.keys was NEVER called
    assert not hasattr(mock_redis, "keys") or mock_redis.keys.await_count == 0

    # Clear calls flushdb asynchronously
    await cache.clear()
    mock_redis.flushdb.assert_awaited_once_with(asynchronous=True)

