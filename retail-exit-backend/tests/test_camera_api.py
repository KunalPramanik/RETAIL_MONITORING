"""Automated Tests for Camera Fleet Management API

Tests camera creation, retrieval, updates, and startup duplicate endpoint reconciliation.
"""

import pytest
from httpx import AsyncClient
from src.main import reconcile_duplicate_cameras
from tests.conftest import TestingSessionLocal
from src.db.models import Camera, Store, Lane, get_utc_now
import uuid


@pytest.mark.anyio
async def test_camera_crud_endpoints(async_client: AsyncClient):
    # Setup baseline store and lane in database
    async with TestingSessionLocal() as session:
        store = Store(store_id="STORE-TEST-1", name="Test Store", timezone="UTC")
        session.add(store)
        lane = Lane(lane_id="LANE-TEST-1", store_id="STORE-TEST-1", label="Exit Lane 1", status="ONLINE")
        session.add(lane)
        await session.commit()

    # 1. List cameras
    list_resp = await async_client.get("/api/cameras")
    assert list_resp.status_code == 200
    initial_count = len(list_resp.json())

    # 2. Register new camera
    cam_payload = {
        "label": "Overhead East Exit Portal",
        "ipAddress": "192.168.1.120",
        "rtspPath": "/live/ch0",
        "laneId": "LANE-TEST-1",
        "pairingMethod": "MANUAL",
    }
    create_resp = await async_client.post("/api/cameras", json=cam_payload)
    assert create_resp.status_code in (200, 201), create_resp.text
    cam_data = create_resp.json()
    assert cam_data["label"] == "Overhead East Exit Portal"
    assert "cameraId" in cam_data
    camera_id = cam_data["cameraId"]

    # 3. Retrieve camera by ID
    get_resp = await async_client.get(f"/api/cameras/{camera_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["cameraId"] == camera_id

    # 4. Update camera
    update_payload = {"label": "Overhead East Exit Portal - Calibrated"}
    update_resp = await async_client.patch(f"/api/cameras/{camera_id}", json=update_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["label"] == "Overhead East Exit Portal - Calibrated"


@pytest.mark.anyio
async def test_duplicate_camera_reconciliation():
    """Startup reconciliation merges duplicate cameras with identical endpoints."""
    now = get_utc_now()
    async with TestingSessionLocal() as session:
        cam1 = Camera(
            camera_id="CAM-DUP-PRIMARY",
            label="Primary Cam",
            ip_address="10.0.0.50",
            rtsp_path="/stream1",
            status="ONLINE",
            added_at=now,
        )
        cam2 = Camera(
            camera_id="CAM-DUP-SECONDARY",
            label="Duplicate Cam",
            ip_address="10.0.0.50",
            rtsp_path="/stream1",
            status="ONLINE",
            added_at=now,
        )
        session.add_all([cam1, cam2])
        await session.commit()

        # Execute reconciliation routine
        reconciled = await reconcile_duplicate_cameras(session)
        assert reconciled >= 1

        # Verify duplicate is soft-deleted
        updated_cam2 = await session.get(Camera, "CAM-DUP-SECONDARY")
        assert updated_cam2.removed_at is not None

        # Verify primary remains active
        updated_cam1 = await session.get(Camera, "CAM-DUP-PRIMARY")
        assert updated_cam1.removed_at is None
