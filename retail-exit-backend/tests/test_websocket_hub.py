"""Automated Tests for WebSocket Connection & Broadcast Hub

Tests connection registration, message formatting, fanout broadcasting,
and graceful disconnection handling.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from src.realtime.hub import ConnectionManager


@pytest.mark.anyio
async def test_websocket_hub_lifecycle_and_broadcast():
    hub = ConnectionManager()
    assert len(hub.active_connections) == 0

    # 1. Connect mock WebSocket
    mock_ws1 = AsyncMock()
    mock_ws1.accept = AsyncMock()
    mock_ws1.send_text = AsyncMock()

    mock_ws2 = AsyncMock()
    mock_ws2.accept = AsyncMock()
    mock_ws2.send_text = AsyncMock()

    await hub.connect(mock_ws1)
    await hub.connect(mock_ws2)

    assert len(hub.active_connections) == 2
    mock_ws1.accept.assert_awaited_once()
    mock_ws2.accept.assert_awaited_once()

    # 2. Broadcast event to both clients
    test_payload = {"alertId": "ALT-100", "severity": "HIGH", "deltaUnits": 3}
    await hub.broadcast_event("new_alert", test_payload)

    assert mock_ws1.send_text.await_count == 1
    assert mock_ws2.send_text.await_count == 1

    sent_data = json.loads(mock_ws1.send_text.call_args[0][0])
    assert sent_data["type"] == "new_alert"
    assert sent_data["payload"]["alertId"] == "ALT-100"

    # 3. Disconnect one client
    hub.disconnect(mock_ws1)
    assert len(hub.active_connections) == 1
    assert mock_ws1 not in hub.active_connections
    assert mock_ws2 in hub.active_connections

    # 4. Handle client send exception during broadcast (dead client cleanup)
    mock_ws2.send_text.side_effect = Exception("Connection reset by peer")
    await hub.broadcast_event("heartbeat", {"status": "HEALTHY"})

    # Dead connection should be removed
    assert len(hub.active_connections) == 0
