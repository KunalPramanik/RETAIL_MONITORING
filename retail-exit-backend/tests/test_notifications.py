"""Tests for Instant Mobile Push & Slack/Telegram Webhooks with Anti-Storm Rate Limiting"""

import pytest
from unittest.mock import patch, MagicMock
from httpx import Response
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.db.models import Base, Alert, Lane, Store, get_utc_now
from src.engine.notification_service import NotificationService, notification_service
from src.engine.alarm import AlarmCoordinator


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


def test_slack_payload_formatting():
    """Verify Slack Block Kit payload structure with incident details and actions."""
    now = get_utc_now()
    alert = Alert(
        alert_id="ALT-SLACK-01",
        event_id="EVT-9988",
        alert_type="OVER_CARRY",
        severity="HIGH",
        delta_units=24,
        created_at=now,
    )
    svc = NotificationService()
    payload = svc.format_slack_payload(alert, lane_label="Exit Portal 3", console_base_url="http://secops.corp")

    assert "text" in payload
    assert "HIGH" in payload["text"]
    blocks = payload["blocks"]
    assert len(blocks) >= 3

    # Header block
    assert blocks[0]["type"] == "header"
    assert "HIGH" in blocks[0]["text"]["text"]

    # Section fields
    section_fields = blocks[1]["fields"]
    fields_text = " ".join(f["text"] for f in section_fields)
    assert "EVT-9988" in fields_text
    assert "Exit Portal 3" in fields_text
    assert "+24 Units" in fields_text

    # Action button
    action_elem = blocks[2]["elements"][0]
    assert "http://secops.corp/events?id=EVT-9988" in action_elem["url"]


def test_telegram_payload_formatting():
    """Verify Telegram HTML payload formatting."""
    now = get_utc_now()
    alert = Alert(
        alert_id="ALT-TG-01",
        event_id="EVT-7766",
        alert_type="UNDER_DECLARE",
        severity="CRITICAL",
        delta_units=12,
        created_at=now,
    )
    svc = NotificationService()
    payload = svc.format_telegram_payload(alert, chat_id="-100123456", lane_label="Lane 2")

    assert payload["chat_id"] == "-100123456"
    assert payload["parse_mode"] == "HTML"
    text = payload["text"]
    assert "CRITICAL" in text
    assert "EVT-7766" in text
    assert "+12 Units" in text
    assert "Lane 2" in text


@pytest.mark.asyncio
async def test_anti_storm_rate_limiting():
    """Anti-storm rate limiting must suppress duplicate alerts for the same lane within 30 seconds."""
    svc = NotificationService(rate_limit_sec=30.0)
    alert1 = Alert(
        alert_id="ALT-STORM-1",
        event_id="EVT-001",
        alert_type="SENSOR_DISAGREEMENT",
        severity="HIGH",
        delta_units=6,
    )
    alert2 = Alert(
        alert_id="ALT-STORM-2",
        event_id="EVT-002",
        alert_type="SENSOR_DISAGREEMENT",
        severity="HIGH",
        delta_units=8,
    )
    lane1 = Lane(lane_id="LANE-STORM-1", label="Lane 1", store_id="STORE-1")
    lane2 = Lane(lane_id="LANE-STORM-2", label="Lane 2", store_id="STORE-1")

    t0 = 5000.0

    # 1. First alert on Lane 1 at t=5000 -> Allowed
    res1 = await svc.send_external_notifications(alert1, lane=lane1, now_ts=t0)
    assert res1["status"] != "RATE_LIMITED"

    # 2. Second alert on Lane 1 at t=5010 (10s later, within 30s) -> MUST BE RATE-LIMITED
    res2 = await svc.send_external_notifications(alert2, lane=lane1, now_ts=t0 + 10.0)
    assert res2["status"] == "RATE_LIMITED"
    assert "Suppressed duplicate" in res2["detail"]

    # 3. Alert on Lane 2 at t=5012 -> Different lane, MUST BE ALLOWED
    res3 = await svc.send_external_notifications(alert2, lane=lane2, now_ts=t0 + 12.0)
    assert res3["status"] != "RATE_LIMITED"

    # 4. Third alert on Lane 1 at t=5035 (35s later, after rate limit expires) -> Allowed
    res4 = await svc.send_external_notifications(alert1, lane=lane1, now_ts=t0 + 35.0)
    assert res4["status"] != "RATE_LIMITED"


@pytest.mark.asyncio
async def test_mock_webhook_dispatch_and_failure_tolerance():
    """Verify HTTP dispatch to Slack and Telegram, and verify network failure doesn't throw."""
    svc = NotificationService(rate_limit_sec=0.0)  # zero rate limit for testing
    alert = Alert(
        alert_id="ALT-WEBHOOK-01",
        event_id="EVT-FAIL-TEST",
        alert_type="INTRUSION",
        severity="HIGH",
        delta_units=5,
    )
    lane = Lane(lane_id="LANE-TEST", label="Lane Alpha", store_id="STORE-1")

    # Mock httpx.AsyncClient to simulate a successful Slack response and a failed Telegram response
    with patch("httpx.AsyncClient.post") as mock_post:
        # Simulate Slack succeeds (200), Telegram returns 500 error
        def side_effect(url, **kwargs):
            if "slack.com" in str(url):
                return Response(status_code=200, text="ok")
            elif "telegram.org" in str(url):
                return Response(status_code=500, text="Internal Server Error")
            return Response(status_code=200, text="ok")

        mock_post.side_effect = side_effect

        res = await svc.send_external_notifications(
            alert=alert,
            lane=lane,
            slack_url="https://hooks.slack.com/services/TEST/SLACK/URL",
            telegram_token="MOCK_BOT_TOKEN",
            telegram_chat_id="12345",
        )

        assert "SLACK" in res["channelsSent"]
        assert any("Telegram HTTP 500" in e for e in res["errors"])
        assert res["status"] == "DELIVERED"  # At least one channel succeeded


@pytest.mark.asyncio
async def test_alarm_coordinator_push_integration(test_session: AsyncSession):
    """Verify AlarmCoordinator dispatches PUSH channel with external notification results."""
    now = get_utc_now()
    store = Store(store_id="STORE-NOTIF", name="Store Notif", timezone="UTC")
    lane = Lane(lane_id="LANE-NOTIF", store_id="STORE-NOTIF", label="Portal Notif", status="ONLINE")
    alert = Alert(
        alert_id="ALT-COORD-01",
        event_id="EVT-ALARM-01",
        alert_type="OVER_CARRY",
        severity="HIGH",
        delta_units=10,
        status="OPEN",
        created_at=now,
    )
    test_session.add_all([store, lane, alert])
    await test_session.commit()

    dispatches = await AlarmCoordinator.dispatch_alert_alarms(
        session=test_session,
        alert=alert,
        lane=lane,
        auto_lock_turnstile=False,
        audio_alarm_enabled=False,
    )

    push_dispatches = [d for d in dispatches if d.channel == "PUSH"]
    assert len(push_dispatches) == 1
    assert push_dispatches[0].status == "SENT"

