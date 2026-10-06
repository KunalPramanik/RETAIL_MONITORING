"""Instant Mobile Security Dispatcher & Multi-Channel Webhook Service

Generates structured incident cards for mobile security teams, floor supervisors,
and automated physical access control (gate locks / turnstiles).

Channels Supported:
- Generic SecOps Webhook (JSON payload with HMAC-SHA256 signature)
- Telegram Bot Markdown Card
- WhatsApp Cloud API Business Message Card
- Automated Barrier Relay Trigger (Gate Lock Command)

Strictly enforces the Zero-Speculation Identity Rule:
- Unverified carriers (< 0.65 similarity) are explicitly labeled UNKNOWN_PERSON.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hmac
import hashlib
import json
import logging

from src.core.config import settings

logger = logging.getLogger("secops.realtime.mobile")


@dataclass
class MobileAlertCard:
    alert_id: str
    timestamp: str
    severity: str                         # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    alert_type: str                       # "OVER_CARRY", "UNAUTHORIZED_EXIT", "HOLLOW_PALLET", "PPE_VIOLATION"
    location_name: str
    camera_id: str
    carrier_name: str                     # "UNKNOWN_PERSON" or verified employee name
    carrier_status: str                   # "UNKNOWN_PERSON" or "VERIFIED_EMPLOYEE"
    carrier_confidence: float
    discrepancy_delta: int
    material_name: str
    snapshot_url: Optional[str]
    action_lock_gate_url: str
    action_override_url: str
    hmac_signature: str


class MobileSecurityDispatcher:
    """Formats and dispatches high-consequence security alerts to mobile devices and gates."""

    @classmethod
    def generate_hmac_signature(cls, payload_bytes: bytes, secret: Optional[str] = None) -> str:
        """Generates HMAC-SHA256 signature for tamper-proof webhook verification."""
        key = (secret or settings.MOBILE_HMAC_SECRET).encode("utf-8")
        return hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()

    @classmethod
    def create_alert_card(
        cls,
        alert_id: str,
        alert_type: str,
        severity: str,
        location_name: str,
        camera_id: str,
        carrier_name: Optional[str],
        carrier_confidence: float,
        discrepancy_delta: int,
        material_name: str,
        snapshot_url: Optional[str] = None,
        base_api_url: Optional[str] = None,
    ) -> MobileAlertCard:
        """Creates an authenticated mobile security alert card."""
        # Enforce Zero-Speculation Rule
        if (
            carrier_confidence < 0.65
            or not carrier_name
            or carrier_name.strip() in ("", "UNKNOWN", "UNKNOWN_PERSON")
        ):
            safe_carrier = "UNKNOWN_PERSON"
            status = "UNKNOWN_PERSON"
        else:
            safe_carrier = carrier_name.strip()
            status = "VERIFIED_EMPLOYEE"

        now_iso = datetime.now(timezone.utc).isoformat()
        api_url = (base_api_url or os.getenv("BASE_API_URL") or "").rstrip("/")
        lock_url = f"{api_url}/api/v1/alerts/{alert_id}/gate-lock" if api_url else f"/api/v1/alerts/{alert_id}/gate-lock"
        override_url = f"{api_url}/api/v1/alerts/{alert_id}/override" if api_url else f"/api/v1/alerts/{alert_id}/override"

        raw_content = f"{alert_id}:{alert_type}:{safe_carrier}:{discrepancy_delta}:{now_iso}"
        signature = cls.generate_hmac_signature(raw_content.encode("utf-8"))

        return MobileAlertCard(
            alert_id=alert_id,
            timestamp=now_iso,
            severity=severity,
            alert_type=alert_type,
            location_name=location_name,
            camera_id=camera_id,
            carrier_name=safe_carrier,
            carrier_status=status,
            carrier_confidence=round(carrier_confidence, 4),
            discrepancy_delta=discrepancy_delta,
            material_name=material_name,
            snapshot_url=snapshot_url,
            action_lock_gate_url=lock_url,
            action_override_url=override_url,
            hmac_signature=signature,
        )

    @classmethod
    def format_telegram_markdown(cls, card: MobileAlertCard) -> str:
        """Formats the alert as a high-visibility Telegram Markdown message."""
        icon = "🚨" if card.severity in ("CRITICAL", "HIGH") else "⚠️"
        lines = [
            f"{icon} *SECURITY ALERT: {card.alert_type}*",
            f"*Severity:* `{card.severity}`",
            f"*Location:* {card.location_name} (Cam `{card.camera_id}`)",
            f"*Carrier:* *{card.carrier_name}* ({card.carrier_status}, Conf: {card.carrier_confidence * 100:.1f}%)",
            f"*Discrepancy:* *{'+' if card.discrepancy_delta > 0 else ''}{card.discrepancy_delta} units* of `{card.material_name}`",
            f"*Timestamp:* `{card.timestamp}`",
            "",
            f"🔒 [LOCK EXIT GATE]({card.action_lock_gate_url})  |  🔓 [SUPERVISOR OVERRIDE]({card.action_override_url})",
        ]
        if card.snapshot_url:
            lines.insert(1, f"[View Camera Evidence]({card.snapshot_url})")
        return "\n".join(lines)

    @classmethod
    def format_whatsapp_payload(cls, card: MobileAlertCard, recipient_phone: str) -> Dict[str, Any]:
        """Formats structured WhatsApp Cloud API interactive message with buttons."""
        return {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {
                    "type": "text",
                    "text": f"🚨 ALERT: {card.alert_type} ({card.severity})",
                },
                "body": {
                    "text": (
                        f"Location: {card.location_name}\n"
                        f"Carrier: {card.carrier_name} ({card.carrier_status})\n"
                        f"Delta: {card.discrepancy_delta} {card.material_name}\n"
                        f"Alert ID: {card.alert_id}"
                    ),
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": f"LOCK_{card.alert_id}", "title": "🔒 Lock Gate"},
                        },
                        {
                            "type": "reply",
                            "reply": {"id": f"OVERRIDE_{card.alert_id}", "title": "🔓 Override"},
                        },
                    ]
                },
            },
        }
