"""Instant Mobile Push & External Webhook Notification Service

Dispatches formatted, real-time alert notifications to Slack Incoming Webhooks,
Telegram Bot API, and Mobile Push endpoints with anti-storm rate limiting.
Zero database schema changes: dispatches are recorded as channel='PUSH' in alarm_dispatch.
"""

from typing import Dict, Any, Optional, List
import os
import time
import httpx
import logging
from datetime import datetime, timezone

from src.db.models import Alert, Lane

logger = logging.getLogger("secops.notifications")


class NotificationService:
    """Manages multi-channel external alerts with anti-storm throttling and graceful failure tolerance."""

    def __init__(self, rate_limit_sec: float = 30.0):
        self.rate_limit_sec = rate_limit_sec
        self._last_notified_per_lane: Dict[str, float] = {}

    def is_rate_limited(self, lane_id: str, now_ts: Optional[float] = None) -> bool:
        """Checks if an alert for this lane was dispatched within the anti-storm window."""
        now = now_ts if now_ts is not None else time.time()
        last = self._last_notified_per_lane.get(lane_id, 0.0)
        return (now - last) < self.rate_limit_sec

    def record_dispatched(self, lane_id: str, now_ts: Optional[float] = None):
        """Records the timestamp of an outbound notification for rate-limiting."""
        now = now_ts if now_ts is not None else time.time()
        self._last_notified_per_lane[lane_id] = now

    def format_slack_payload(
        self,
        alert: Alert,
        lane_label: str = "Unknown Lane",
        console_base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Builds an enterprise Slack Block Kit message payload."""
        base_url = (console_base_url or os.getenv("CONSOLE_BASE_URL") or "").rstrip("/")
        sev = str(alert.severity)
        sev_emoji = "🚨" if sev in ("HIGH", "CRITICAL") else "⚠️"
        alert_id = str(alert.alert_id)
        evt_id = str(alert.event_id or "N/A")
        delta = int(alert.delta_units or 0)
        created_str = alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if alert.created_at else "Just now"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{sev_emoji} SEC-OPS LOSS PREVENTION ALERT: {sev}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:*\n{alert.alert_type}"},
                    {"type": "mrkdwn", "text": f"*Lane:*\n{lane_label}"},
                    {"type": "mrkdwn", "text": f"*Event ID:*\n`{evt_id}`"},
                    {"type": "mrkdwn", "text": f"*Discrepancy (Δ):*\n*+{delta} Units*"},
                    {"type": "mrkdwn", "text": f"*Timestamp:*\n{created_str}"},
                    {"type": "mrkdwn", "text": f"*Severity Level:*\n`{sev}`"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Inspect Event Dossier"},
                        "url": f"{base_url}/events?id={evt_id}" if base_url else f"/events?id={evt_id}",
                        "style": "danger" if sev in ("HIGH", "CRITICAL") else "primary",
                    }
                ],
            },
        ]
        return {"text": f"{sev_emoji} {sev} Alert on {lane_label}: {alert.alert_type}", "blocks": blocks}

    def format_telegram_payload(
        self,
        alert: Alert,
        chat_id: str,
        lane_label: str = "Unknown Lane",
        console_base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Builds a formatted HTML message payload for the Telegram Bot API."""
        base_url = (console_base_url or os.getenv("CONSOLE_BASE_URL") or "").rstrip("/")
        sev = str(alert.severity)
        sev_icon = "🚨" if sev in ("HIGH", "CRITICAL") else "⚠️"
        evt_id = str(alert.event_id or "N/A")
        delta = int(alert.delta_units or 0)
        created_str = alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if alert.created_at else "Just now"

        text = (
            f"{sev_icon} <b>SEC-OPS SECURITY ALERT: {sev}</b>\n\n"
            f"• <b>Alert Type:</b> <code>{alert.alert_type}</code>\n"
            f"• <b>Lane:</b> <code>{lane_label}</code>\n"
            f"• <b>Event ID:</b> <code>{evt_id}</code>\n"
            f"• <b>Discrepancy (Δ):</b> <b>+{delta} Units</b>\n"
            f"• <b>Detected At:</b> {created_str}\n\n"
            f"🔗 <a href='{console_base_url}/events?id={evt_id}'>Review in Console</a>"
        )
        return {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

    async def send_external_notifications(
        self,
        alert: Alert,
        lane: Optional[Lane] = None,
        slack_url: Optional[str] = None,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        push_webhook_url: Optional[str] = None,
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Dispatches external notifications to all configured channels with rate limiting."""
        lane_id = str(lane.lane_id) if lane else "UNKNOWN_LANE"
        lane_label = str(lane.label) if lane else lane_id

        # Anti-storm throttling
        if self.is_rate_limited(lane_id, now_ts):
            logger.warning(f"Notification rate-limited on lane {lane_id} (storm suppression active)")
            return {
                "status": "RATE_LIMITED",
                "detail": f"Suppressed duplicate notification on lane {lane_id} within {self.rate_limit_sec}s",
                "channelsSent": [],
            }

        channels_sent: List[str] = []
        errors: List[str] = []

        # Resolve endpoints from parameters or environment
        slack_target = slack_url or os.environ.get("SLACK_WEBHOOK_URL")
        tg_token = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        tg_chat = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        push_target = push_webhook_url or os.environ.get("MOBILE_PUSH_WEBHOOK_URL")

        async with httpx.AsyncClient(timeout=3.0) as client:
            # 1. Slack Incoming Webhook
            if slack_target:
                try:
                    payload = self.format_slack_payload(alert, lane_label)
                    resp = await client.post(slack_target, json=payload)
                    if resp.status_code < 300:
                        channels_sent.append("SLACK")
                    else:
                        errors.append(f"Slack HTTP {resp.status_code}")
                except Exception as exc:
                    errors.append(f"Slack err: {exc}")

            # 2. Telegram Bot API
            if tg_token and tg_chat:
                try:
                    tg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                    payload = self.format_telegram_payload(alert, tg_chat, lane_label)
                    resp = await client.post(tg_url, json=payload)
                    if resp.status_code < 300:
                        channels_sent.append("TELEGRAM")
                    else:
                        errors.append(f"Telegram HTTP {resp.status_code}")
                except Exception as exc:
                    errors.append(f"Telegram err: {exc}")

            # 3. Mobile Push Webhook
            if push_target:
                try:
                    push_payload = {
                        "title": f"SEC-OPS {alert.severity} Alert",
                        "body": f"Lane {lane_label}: {alert.alert_type} (Δ: +{alert.delta_units or 0})",
                        "data": {
                            "alertId": str(alert.alert_id),
                            "eventId": str(alert.event_id or ""),
                            "severity": str(alert.severity),
                            "laneId": lane_id,
                        },
                    }
                    resp = await client.post(push_target, json=push_payload)
                    if resp.status_code < 300:
                        channels_sent.append("PUSH_WEBHOOK")
                    else:
                        errors.append(f"Push HTTP {resp.status_code}")
                except Exception as exc:
                    errors.append(f"Push err: {exc}")

        # Update throttle timestamp if at least one channel was attempted
        self.record_dispatched(lane_id, now_ts)

        is_success = len(channels_sent) > 0 or len(errors) == 0
        return {
            "status": "DELIVERED" if is_success else "FAILED",
            "channelsSent": channels_sent,
            "errors": errors,
            "detail": f"Channels: {', '.join(channels_sent)}" if channels_sent else f"Failed: {'; '.join(errors)}",
        }


# Global singleton
notification_service = NotificationService()

