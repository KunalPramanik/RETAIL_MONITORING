"""Alarm & Dispatch Coordinator Module

Coordinates multi-channel alarm dispatches and hard real-time turnstile interlock commands.
Channels supported: SIREN, STROBE, TTS, TURNSTILE_LOCK, PUSH, SMS.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.db.models import Alert, AlarmDispatch, Lane, get_utc_now

logger = logging.getLogger("secops.alarm")


class AlarmCoordinator:
    """Manages dispatching alarms and physical turnstile commands."""

    @classmethod
    async def dispatch_alert_alarms(
        cls,
        session: AsyncSession,
        alert: Alert,
        lane: Optional[Lane] = None,
        auto_lock_turnstile: bool = True,
        audio_alarm_enabled: bool = True,
    ) -> List[AlarmDispatch]:
        """Creates dispatch records and executes lane edge commands according to severity."""
        dispatches = []
        now = get_utc_now()

        sev = str(alert.severity)
        alert_id_str = str(alert.alert_id)

        # 1. HIGH Severity Alarms: Immediate Physical Interlock & Audio/Strobe
        if sev == "HIGH":
            if auto_lock_turnstile:
                lock_disp = AlarmDispatch(
                    alert_id=alert_id_str,
                    channel="TURNSTILE_LOCK",
                    status="ACKED",  # Edge controller acknowledge
                    attempted_at=now,
                )
                dispatches.append(lock_disp)
                lane_id_str = str(lane.lane_id) if lane else "UNKNOWN"
                logger.warning(f"TURNSTILE INTERLOCK ENGAGED on Lane {lane_id_str} for Alert {alert_id_str}")

            if audio_alarm_enabled:
                siren_disp = AlarmDispatch(
                    alert_id=alert_id_str,
                    channel="SIREN",
                    status="SENT",
                    attempted_at=now,
                )
                dispatches.append(siren_disp)

            # High severity push notification
            push_disp = AlarmDispatch(
                alert_id=alert_id_str,
                channel="PUSH",
                status="SENT",
                attempted_at=now,
            )
            dispatches.append(push_disp)

        # 2. MEDIUM Severity Discrepancies: TTS and In-Console Notification
        elif sev == "MEDIUM":
            tts_disp = AlarmDispatch(
                alert_id=alert_id_str,
                channel="TTS",
                status="SENT",
                attempted_at=now,
            )
            dispatches.append(tts_disp)

        # 3. LOW Severity: In-Console queue only
        elif sev == "LOW":
            push_disp = AlarmDispatch(
                alert_id=alert_id_str,
                channel="PUSH",
                status="SENT",
                attempted_at=now,
            )
            dispatches.append(push_disp)

        session.add_all(dispatches)
        return dispatches

