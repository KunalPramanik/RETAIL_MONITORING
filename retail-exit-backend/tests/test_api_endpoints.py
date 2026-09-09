"""Integration Tests for REST API Endpoints"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.main import app
from src.db.session import get_db
from src.db.models import Base
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
async def test_get_live_kpis(client):
    """Test /api/kpis/live endpoint returns expected telemetry fields."""
    resp = await client.get("/api/kpis/live")
    assert resp.status_code == 200
    data = resp.json()
    assert "todayThroughputUnits" in data
    assert "openAlertsCount" in data
    assert "openAlertsBySeverity" in data
    assert "consensusAccuracyRate" in data
    assert "activeLanesCount" in data


@pytest.mark.asyncio
async def test_get_events_list(client):
    """Test /api/events list endpoint with pagination and sorting."""
    resp = await client.get("/api/events?limit=10")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) > 0
    first = events[0]
    assert "eventId" in first
    assert "laneId" in first
    assert "consensusUnits" in first
    assert "verdict" in first
    assert "severity" in first


@pytest.mark.asyncio
async def test_get_event_detail(client):
    """Test /api/events/{id} detail endpoint."""
    resp = await client.get("/api/events/EVT-2026-9045")
    assert resp.status_code == 200
    data = resp.json()
    assert data["eventId"] == "EVT-2026-9045"
    assert data["employeeId"] == "emp_102"
    assert len(data["lineItems"]) > 0
    assert len(data["rawVisionDetections"]) > 0


@pytest.mark.asyncio
async def test_products_crud(client):
    """Test /api/products listing and creation."""
    # List
    resp = await client.get("/api/products")
    assert resp.status_code == 200
    products = resp.json()
    assert len(products) >= 10

    # Create
    new_prod = {
        "skuCode": "SKU-TST-NEW-10",
        "name": "Test Spark Drink 500ml",
        "category": "Beverages",
        "packSize": 10,
        "unitPrice": 2.50,
        "casePrice": 22.00,
        "reorderThreshold": 50,
    }
    create_resp = await client.post("/api/products", json=new_prod)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["skuCode"] == "SKU-TST-NEW-10"
    assert created["packSize"] == 10


@pytest.mark.asyncio
async def test_employees_list_and_history(client):
    """Test /api/employees list and history endpoints."""
    resp = await client.get("/api/employees")
    assert resp.status_code == 200
    employees = resp.json()
    assert len(employees) >= 6

    # History for Marcus Vance (emp_102)
    hist_resp = await client.get("/api/employees/emp_102/history")
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert hist["employee"]["employeeId"] == "emp_102"
    assert "events" in hist


@pytest.mark.asyncio
async def test_invoices_list(client):
    """Test /api/invoices list endpoint."""
    resp = await client.get("/api/invoices")
    assert resp.status_code == 200
    invoices = resp.json()
    assert len(invoices) >= 4


@pytest.mark.asyncio
async def test_lanes_list_and_toggle(client):
    """Test /api/lanes list and turnstile toggle."""
    resp = await client.get("/api/lanes")
    assert resp.status_code == 200
    lanes = resp.json()
    assert len(lanes) == 4

    toggle_resp = await client.post("/api/lanes/LANE-01/turnstile/toggle")
    assert toggle_resp.status_code == 200
    data = toggle_resp.json()
    assert data["status"] == "COMMAND_ACKED"


@pytest.mark.asyncio
async def test_health_check(client):
    """Test /health and /metrics endpoints."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "HEALTHY"

    metrics_resp = await client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "secops_events_total" in metrics_resp.text

