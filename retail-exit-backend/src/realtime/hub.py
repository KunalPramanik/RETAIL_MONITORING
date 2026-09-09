"""WebSocket Connection & Broadcast Hub

Manages active browser connections and fans out real-time alerts, events, and KPI updates.
"""

from typing import List, Dict, Any, Set, cast
from fastapi import WebSocket
import logging
import json

from src.realtime.events import WebSocketEnvelope

logger = logging.getLogger("secops.ws")


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, envelope: WebSocketEnvelope):
        """Broadcasts a typed message envelope to all connected clients."""
        if not self.active_connections:
            return

        payload_json = envelope.model_dump_json()
        dead_connections = set()

        for conn in self.active_connections:
            try:
                await conn.send_text(payload_json)
            except Exception as e:
                logger.error(f"Failed to send message to client: {e}")
                dead_connections.add(conn)

        for dead in dead_connections:
            self.disconnect(dead)

    async def broadcast_event(self, event_type: str, payload: Dict[str, Any]):
        """Helper to construct envelope and broadcast."""
        envelope = WebSocketEnvelope(type=cast(Any, event_type), payload=payload)
        await self.broadcast(envelope)


# Global singleton instance
ws_hub = ConnectionManager()

