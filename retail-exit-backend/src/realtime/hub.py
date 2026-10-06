"""WebSocket Connection & Distributed Broadcast Hub

Manages active browser connections and fans out real-time alerts, events, and KPI updates.
Supports both zero-dependency standalone in-memory fan-out and distributed multi-pod
Redis Pub/Sub clustering across Kubernetes replicas.
"""

from typing import List, Dict, Any, Set, Optional, cast
from fastapi import WebSocket
import logging
import asyncio
import json

from src.core.config import settings
from src.realtime.events import WebSocketEnvelope

logger = logging.getLogger("secops.ws")


class ConnectionManager:
    """Manages active WebSocket browser connections and orchestrates real-time broadcast fanout."""

    REDIS_CHANNEL = "secops:events:broadcast"

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._redis_client = None
        self._redis_sub_task: Optional[asyncio.Task] = None
        self._is_running: bool = False

    async def start(self):
        """Initializes cluster communication backend (Redis Pub/Sub if configured)."""
        self._is_running = True
        if settings.REDIS_URL:
            try:
                import redis.asyncio as aioredis
                self._redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_timeout=2.0,
                    socket_connect_timeout=2.0,
                )
                self._redis_sub_task = asyncio.create_task(self._redis_listener_loop())
                logger.info(f"WebSocket Hub started in DISTRIBUTED CLUSTER mode (Redis Pub/Sub: {self.REDIS_CHANNEL})")
            except Exception as e:
                logger.warning(f"Could not connect to Redis Pub/Sub ({e}). Defaulting to standalone in-memory broadcast.")
                self._redis_client = None
        else:
            logger.info("WebSocket Hub started in STANDALONE IN-MEMORY mode (no external broker required).")

    async def stop(self):
        """Cleanly terminates cluster listeners and disposes connections."""
        self._is_running = False
        if self._redis_sub_task:
            self._redis_sub_task.cancel()
            try:
                await self._redis_sub_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"Exception during Redis subscriber shutdown: {e}")

        if self._redis_client:
            try:
                await self._redis_client.close()
            except Exception as e:
                logger.debug(f"Exception closing Redis client: {e}")
            self._redis_client = None
        logger.info("WebSocket Hub shut down cleanly.")

    async def _redis_listener_loop(self):
        """Background worker subscribing to cluster broadcast channel and fanning out to local clients."""
        while self._is_running and self._redis_client:
            try:
                pubsub = self._redis_client.pubsub()
                await pubsub.subscribe(self.REDIS_CHANNEL)
                logger.debug(f"Subscribed to Redis channel '{self.REDIS_CHANNEL}' for cluster event fan-out.")

                while self._is_running:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message.get("type") == "message":
                        raw_data = message.get("data")
                        if isinstance(raw_data, bytes):
                            raw_data = raw_data.decode("utf-8")
                        if raw_data:
                            await self._broadcast_local_raw(raw_data)
                    await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._is_running:
                    break
                logger.warning(f"Redis Pub/Sub subscriber disconnected: {e}. Reconnecting in 3s...")
                await asyncio.sleep(3.0)

    async def connect(self, websocket: WebSocket):
        """Registers and accepts a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Unregisters a closed or terminated WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def _broadcast_local_raw(self, payload_json: str):
        """Directly sends a serialized JSON string to all currently connected local WebSockets."""
        if not self.active_connections:
            return

        dead_connections = set()
        for conn in list(self.active_connections):
            try:
                await conn.send_text(payload_json)
            except Exception as e:
                logger.debug(f"Failed to send message to client: {e}")
                dead_connections.add(conn)

        for dead in dead_connections:
            self.disconnect(dead)

    async def broadcast(self, envelope: WebSocketEnvelope):
        """Broadcasts a typed message envelope across the cluster or locally."""
        payload_json = envelope.model_dump_json()

        # If clustered via Redis, publish to shared channel
        if self._redis_client is not None and self._is_running:
            try:
                await self._redis_client.publish(self.REDIS_CHANNEL, payload_json)
                return
            except Exception as e:
                logger.warning(f"Failed to publish to Redis Pub/Sub ({e}). Falling back to local broadcast.")

        # Standalone local fanout fallback
        await self._broadcast_local_raw(payload_json)

    async def broadcast_event(self, event_type: str, payload: Dict[str, Any]):
        """Helper to construct envelope and broadcast to all connected control room displays."""
        envelope = WebSocketEnvelope(type=cast(Any, event_type), payload=payload)
        await self.broadcast(envelope)


# Global singleton instance
ws_hub = ConnectionManager()

