"""Tests for Analytics & Open-Vocabulary REST Endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.asyncio
async def test_get_occupancy_analytics():
    """Verifies that GET /api/analytics/occupancy returns live spatial data."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/analytics/occupancy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "occupancy" in data
        assert "totalFootfallIn" in data
        assert "totalFootfallOut" in data
        assert "crowdDensity" in data
        assert "zoneMetrics" in data
        assert "tripwires" in data


@pytest.mark.asyncio
async def test_configure_tripwire_endpoint():
    """Verifies POST /api/analytics/tripwire/configure updates tripwire."""
    payload = {
        "camera_id": "cam_lane_01",
        "tripwire_id": "tw_door_1",
        "line_coords": [[100, 200], [800, 200]],
        "label": "West Portal Entry",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/analytics/tripwire/configure", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "configured"
        assert data["tripwire_id"] == "tw_door_1"


@pytest.mark.asyncio
async def test_open_vocab_query_endpoint():
    """Verifies POST /api/analytics/open-vocab/query executes zero-shot grounding."""
    payload = {
        "queries": ["safety cone", "pallet"],
        "confidence_floor": 0.35,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/analytics/open-vocab/query", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "grounded_count" in data
        assert isinstance(data["entities"], list)

