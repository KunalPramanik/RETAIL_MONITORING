"""Automated Tests for AlarmCoordinator and Turnstile Interlock System

Validates multi-channel alarm execution (TURNSTILE_LOCK, SIREN, PUSH, TTS)
based on incident severity.
"""

import pytest
from src.engine.alarm import AlarmCoordinator
from src.db.models import Alert, Lane, Store, get_utc_now
from tests.conftest import TestingSessionLocal


@pytest.mark.anyio
async def test_high_severity_alarm_dispatch():
    async with TestingSessionLocal() as session:
        store = Store(store_id="STORE-ALARM-1", name="Alarm Store", timezone="UTC")
        session.add(store)
        lane = Lane(lane_id="LANE-ALARM-1", store_id="STORE-ALARM-1", label="Exit Lane 1", status="ONLINE")
        session.add(lane)
        await session.flush()

        high_alert = Alert(
            alert_id="ALT-HIGH-TEST",
            alert_type="OVER_CARRY",
            severity="HIGH",
            delta_units=5,
            status="OPEN",
            created_at=get_utc_now(),
        )
        session.add(high_alert)
        await session.flush()

        dispatches = await AlarmCoordinator.dispatch_alert_alarms(
            session=session,
            alert=high_alert,
            lane=lane,
            auto_lock_turnstile=True,
            audio_alarm_enabled=True,
        )

        channels = [d.channel for d in dispatches]
        assert "TURNSTILE_LOCK" in channels
        assert "SIREN" in channels
        assert "PUSH" in channels
        assert len(dispatches) >= 3


@pytest.mark.anyio
async def test_medium_severity_alarm_dispatch():
    async with TestingSessionLocal() as session:
        med_alert = Alert(
            alert_id="ALT-MED-TEST",
            alert_type="SENSOR_DISAGREEMENT",
            severity="MEDIUM",
            delta_units=2,
            status="OPEN",
            created_at=get_utc_now(),
        )
        session.add(med_alert)
        await session.flush()

        dispatches = await AlarmCoordinator.dispatch_alert_alarms(
            session=session,
            alert=med_alert,
        )

        channels = [d.channel for d in dispatches]
        assert "TTS" in channels
        assert "TURNSTILE_LOCK" not in channels
