"""Integration Tests for Full Multi-Modal Edge Ingestion Pipeline"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.main import app
from src.db.session import get_db
from src.db.models import Base, ExitEvent, Alert
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
async def test_ingest_clean_pass_event(client, test_session):
    """Ingesting 3 cases of Spring Water (72 units) matched with invoice inv_88201 (72 units) should produce PASS."""
    ingest_payload = {
        "laneId": "LANE-01",
        "employeeBadgeId": "RFID-BADGE-8841",
        "lineItems": [
            {
                "productId": "prod_001",  # Spring water, pack 24
                "casesQty": 3,            # 72 units
                "singlesQty": 0,
            }
        ],
        "invoiceId": "inv_88201",  # 72 units declared
        "simulateRfidAttenuation": False,
    }

    resp = await client.post("/api/ingest/event", json=ingest_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["laneId"] == "LANE-01"
    assert data["consensusUnits"] == 72
    assert data["verdict"] == "PASS"
    assert data["severity"] == "NONE"


@pytest.mark.asyncio
async def test_ingest_over_carry_high_severity_event(client, test_session):
    """Ingesting 8 cases of laundry pods (48 units) vs 24 declared for Marcus Vance (repeat offender) -> HIGH severity."""
    ingest_payload = {
        "laneId": "LANE-02",
        "employeeBadgeId": "RFID-BADGE-4419",  # Marcus Vance (repeat offender with 4 mismatches)
        "lineItems": [
            {
                "productId": "prod_004",  # Laundry Pods, pack 6
                "casesQty": 8,            # 48 units detected
                "singlesQty": 0,
            }
        ],
        "invoiceId": "inv_88204",  # 24 units declared
        "simulateRfidAttenuation": False,
    }

    resp = await client.post("/api/ingest/event", json=ingest_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "MISMATCH"
    assert data["severity"] == "HIGH"
    assert data["deltaUnits"] == 24

    # Verify Alert was created in database
    alert_res = await test_session.execute(
        select(Alert).where(Alert.event_id == data["eventId"])
    )
    alert = alert_res.scalar_one_or_none()
    assert alert is not None
    assert alert.severity == "HIGH"
    assert alert.status == "OPEN"


@pytest.mark.asyncio
async def test_inject_scenario_endpoint(client):
    """Test scenario simulation endpoint."""
    resp = await client.post("/api/ingest/scenario?scenario_type=CASE_PACK_OVER")
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "MISMATCH"

