"""Integration Tests for Alert Lifecycle and Append-Only Audit Trail"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.main import app
from src.db.session import get_db
from src.db.models import Base, Alert, AuditLog
from src.db.seed import seed_database


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await seed_database(session)
        yield session


@pytest.fixture
async def client(test_session):
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_acknowledge_alert(client, test_session):
    """Test acknowledging an open alert."""
    resp = await client.post(
        "/api/alerts/ALT-8001/acknowledge",
        json={"acknowledgedBy": "Officer Vance"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["resolvedBy"] == "Officer Vance"

    # Verify audit log row was written
    audit_res = await test_session.execute(
        select(AuditLog).where(AuditLog.entity_id == "ALT-8001", AuditLog.action == "ACKNOWLEDGE_ALERT")
    )
    audit_entry = audit_res.scalar_one_or_none()
    assert audit_entry is not None
    assert audit_entry.actor_id == "Officer Vance"


@pytest.mark.asyncio
async def test_resolve_alert_mandatory_note_validation(client):
    """Resolution must fail if resolution note is empty or too short."""
    # Empty note
    resp = await client.post(
        "/api/alerts/ALT-8001/resolve",
        json={"resolvedBy": "David Torres", "resolutionNote": "   "},
    )
    assert resp.status_code in [400, 422]

    # Short note (< 5 chars)
    resp_short = await client.post(
        "/api/alerts/ALT-8001/resolve",
        json={"resolvedBy": "David Torres", "resolutionNote": "ok"},
    )
    assert resp_short.status_code in [400, 422]


@pytest.mark.asyncio
async def test_resolve_alert_success(client, test_session):
    """Successful resolution should set status to RESOLVED and log audit trail."""
    note = "Physical cart inspected at East Loading bay. 12 units unaccounted were returned to stock."
    resp = await client.post(
        "/api/alerts/ALT-8001/resolve",
        json={"resolvedBy": "David Torres", "resolutionNote": note},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESOLVED"
    assert data["resolutionNote"] == note

    # Verify audit log
    audit_res = await test_session.execute(
        select(AuditLog).where(AuditLog.entity_id == "ALT-8001", AuditLog.action == "RESOLVE_ALERT")
    )
    audit_entry = audit_res.scalar_one_or_none()
    assert audit_entry is not None
    assert audit_entry.after_state["status"] == "RESOLVED"

