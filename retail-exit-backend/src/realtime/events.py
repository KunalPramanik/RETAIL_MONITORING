"""Typed Real-Time Event Envelopes

Defines structured, versioned WebSocket payloads consumed by the frontend control console.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Literal
from datetime import datetime, timezone


class WebSocketEnvelope(BaseModel):
    version: str = "1.0"
    type: Literal[
        "new_event",
        "new_alert",
        "alert_status_changed",
        "kpi_update",
        "lane_status_changed",
        "turnstile_lock_changed",
        "camera_status_changed",
        "pairing_token_used",
        "heartbeat",
        "database_reset",
        "invoice_uploaded",
        "detection_update",
    ]
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: Dict[str, Any]
