"""Tests for Multi-Camera Employee Movement Tracking & Store Material Counting

Verifies:
- GET /api/employees/{employee_id}/movement returns entry/exit counts and materials handled
- Material attribution (cement, rebar, tiles, aluminum tin) across camera passes
- Audit of Unknown Personnel movements
"""

import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
import uuid

from src.main import app
from src.db.session import AsyncSessionLocal
from src.db.models import (
    Employee,
    ExitEvent,
    ExitEventLineItem,
    Product,
    Lane,
    TripwireCrossingEvent,
    VirtualTripwireConfig,
)


@pytest.mark.asyncio
async def test_employee_movement_tracking_known():
    """Verify movement tracking endpoint for an enrolled known employee."""
    async with AsyncSessionLocal() as session:
        # Create test employee
        emp_id = f"emp_test_{uuid.uuid4().hex[:6]}"
        emp = Employee(
            employee_id=emp_id,
            name="Marcus Vance",
            role="Warehouse Dispatcher",
            rfid_badge_id=f"RFID-{uuid.uuid4().hex[:6]}",
            shift_id="SHIFT-MORNING-A",
            active_flag=True,
        )
        session.add(emp)

        # Create products for materials
        p_cem = Product(
            product_id=f"prod_cem_{uuid.uuid4().hex[:6]}",
            sku_code=f"MAT-CEM-{uuid.uuid4().hex[:4]}",
            name="Cement Bag (50kg)",
            category="Building Materials",
            pack_size=1,
            unit_price=9.50,
            case_price=95.00,
        )
        p_rod = Product(
            product_id=f"prod_rod_{uuid.uuid4().hex[:6]}",
            sku_code=f"MAT-ROD-{uuid.uuid4().hex[:4]}",
            name="Bundled Iron Rods / Rebar",
            category="Building Materials",
            pack_size=1,
            unit_price=24.00,
            case_price=240.00,
        )
        session.add_all([p_cem, p_rod])

        # Create test lane
        lane = Lane(
            lane_id=f"LANE-{uuid.uuid4().hex[:4]}",
            store_id="store_0402",
            label="Gate 2 — Logistics North",
            status="ONLINE",
        )
        session.add(lane)
        await session.flush()

        # Inbound Entry event: carrying 5x Cement Bags
        ev1 = ExitEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:6]}",
            ts=datetime.now(timezone.utc),
            lane_id=lane.lane_id,
            employee_id=emp_id,
            cases_detected=5,
            units_detected=5,
            vision_count=5,
            vision_confidence=0.98,
            consensus_units=5,
            consensus_method="weighted_vote_v2",
            declared_units=5,
            delta_units=0,
            verdict="PASS",
            severity="NONE",
            notes="[ENTRY] Carrier: Marcus Vance. Inbound traversal.",
        )
        session.add(ev1)
        await session.flush()

        li1 = ExitEventLineItem(
            line_item_id=str(uuid.uuid4()),
            event_id=ev1.event_id,
            product_id=p_cem.product_id,
            cases_qty=5,
            units_qty=5,
        )
        session.add(li1)

        # Outbound Exit event: carrying 2x Iron Rods
        ev2 = ExitEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:6]}",
            ts=datetime.now(timezone.utc),
            lane_id=lane.lane_id,
            employee_id=emp_id,
            cases_detected=2,
            units_detected=2,
            vision_count=2,
            vision_confidence=0.97,
            consensus_units=2,
            consensus_method="weighted_vote_v2",
            declared_units=2,
            delta_units=0,
            verdict="PASS",
            severity="NONE",
            notes="[EXIT] Carrier: Marcus Vance. Outbound dispatch.",
        )
        session.add(ev2)
        await session.flush()

        li2 = ExitEventLineItem(
            line_item_id=str(uuid.uuid4()),
            event_id=ev2.event_id,
            product_id=p_rod.product_id,
            cases_qty=2,
            units_qty=2,
        )
        session.add(li2)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/employees/{emp_id}/movement")
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["employeeId"] == emp_id
        assert data["name"] == "Marcus Vance"
        assert data["totalEntries"] == 1
        assert data["totalExits"] == 1
        assert data["totalTraversals"] == 2
        assert "Gate 2" in data["lastSeenCamera"]

        # Check materials breakdown
        mat_summary = data["materialsHandledSummary"]
        assert "Cement Bag (50kg)" in mat_summary
        assert mat_summary["Cement Bag (50kg)"]["in"] == 5

        assert "Bundled Iron Rods / Rebar" in mat_summary
        assert mat_summary["Bundled Iron Rods / Rebar"]["out"] == 2

        # Check individual movement records
        assert len(data["movements"]) == 2
        directions = [m["direction"] for m in data["movements"]]
        assert "ENTRY" in directions
        assert "EXIT" in directions


@pytest.mark.asyncio
async def test_employee_movement_tracking_unknown():
    """Verify movement tracking endpoint for Unknown / Unverified persons."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/employees/unknown/movement")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["employeeId"] == "unknown"
        assert "Unknown" in data["name"]
        assert isinstance(data["totalEntries"], int)
        assert isinstance(data["totalExits"], int)
        assert isinstance(data["movements"], list)
