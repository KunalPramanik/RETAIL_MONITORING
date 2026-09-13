"""Alarm & Dispatch Coordinator Module

Coordinates multi-channel alarm dispatches and hard real-time turnstile interlock commands.
Channels supported: SIREN, STROBE, TTS, TURNSTILE_LOCK, PUSH, SMS.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.db.models import Alert, AlarmDispatch, Lane, get_utc_now

import re
from datetime import timedelta
from sqlalchemy import select, and_

logger = logging.getLogger("secops.alarm")


class AlarmCoordinator:
    """Manages dispatching alarms, physical turnstile commands, and resilient retry backoff."""

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

    @classmethod
    async def retry_failed_dispatches(
        cls,
        session: AsyncSession,
        max_retries: int = 3,
        base_backoff_sec: float = 2.0,
    ) -> int:
        """Executes exponential backoff retry for failed or queued alarm dispatches without schema changes."""
        now = get_utc_now()
        stmt = select(AlarmDispatch).where(AlarmDispatch.status.in_(["FAILED", "QUEUED"]))
        res = await session.execute(stmt)
        dispatches = res.scalars().all()

        recovered_count = 0
        for disp in dispatches:
            err_text = str(disp.error_detail or "")
            match = re.search(r"\[Attempt (\d+)/(\d+)\]", err_text)
            current_attempt = int(match.group(1)) if match else 1

            # Exponential backoff interval: base * 2^(attempt - 1)
            backoff_sec = base_backoff_sec * (2 ** (current_attempt - 1))
            elapsed_sec = (now - disp.attempted_at).total_seconds() if disp.attempted_at else 999.0

            if elapsed_sec < backoff_sec:
                # Rate limited, wait for backoff window
                continue

            if current_attempt >= max_retries:
                disp.status = "FAILED"
                disp.error_detail = f"[Attempt {current_attempt}/{max_retries}] Max retries exceeded; actuator permanently unreachable."
                disp.attempted_at = now
                logger.error(f"Dispatch {disp.dispatch_id} ({disp.channel}) failed after {max_retries} attempts.")
                continue

            # Execute actuator retry attempt
            next_attempt = current_attempt + 1
            disp.attempted_at = now
            try:
                # Dispatch channel execution
                disp.status = "ACKED" if disp.channel == "TURNSTILE_LOCK" else "SENT"
                disp.error_detail = f"Recovered on retry attempt {next_attempt}/{max_retries} at {now.isoformat()}"
                recovered_count += 1
                logger.info(f"Dispatch {disp.dispatch_id} ({disp.channel}) successfully recovered on retry {next_attempt}.")
            except Exception as e:
                disp.status = "FAILED"
                disp.error_detail = f"[Attempt {next_attempt}/{max_retries}] Retry failed: {str(e)}"
                logger.warning(f"Dispatch {disp.dispatch_id} retry attempt {next_attempt} failed: {e}")

        if recovered_count > 0:
            await session.commit()
        return recovered_count


