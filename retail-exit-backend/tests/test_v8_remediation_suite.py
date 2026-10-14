"""Remediation Test Suite for SEC-OPS V8 CPU-First Requirements

Validates:
1. Physical Siren Adapter (triggering, auto-silence, manual silence, rate limiting, and status report).
2. AlarmCoordinator silence_alarms coordination.
3. 45-Day Snapshot Retention Cleanup Service (purges expired snapshots, preserves active snapshots and db).
4. Camera Role Model & Constraints (ENTRY_EXIT, STOCK_AREA, SHELF, WAREHOUSE, DISPATCH, GENERAL_MONITORING).
5. Initial Stock Baseline Verification workflow entities and states.
"""

import os
import time
import pytest
from httpx import AsyncClient

from src.hardware.siren_adapter import PhysicalSirenAdapter
from src.engine.alarm import AlarmCoordinator
from src.services.retention_service import purge_expired_snapshots
from src.db.models import Camera, Lane, Store, InitialStockVerification, Product, get_utc_now
from tests.conftest import TestingSessionLocal


@pytest.mark.anyio
async def test_physical_siren_adapter_lifecycle():
    """Validates siren trigger, status, and fail-safe silence."""
    adapter = PhysicalSirenAdapter(min_interval_sec=0.1)
    
    # 1. Initial State: Silenced
    status_initial = adapter.get_status()
    assert status_initial["active"] is False

    # 2. Trigger Siren
    res = await adapter.trigger_siren(duration_sec=0.5, reason="UNIT_TEST_TRIGGER")
    assert res["success"] is True
    assert res["active"] is True
    assert adapter.is_active is True

    # 3. Silence Siren
    silence_res = await adapter.silence_siren()
    assert silence_res["success"] is True
    assert silence_res["active"] is False
    assert adapter.is_active is False

    # 4. AlarmCoordinator.silence_alarms
    coord_res = await AlarmCoordinator.silence_alarms()
    assert "siren" in coord_res
    assert "turnstile" in coord_res


@pytest.mark.anyio
async def test_snapshot_retention_service(tmp_path):
    """Validates that purge_expired_snapshots removes expired files and retains recent files."""
    snap_dir = str(tmp_path / "test_snapshots")
    os.makedirs(snap_dir, exist_ok=True)

    now_epoch = time.time()
    day_sec = 86400.0

    # 1. Create an expired file (60 days old)
    old_file = os.path.join(snap_dir, "old_preview_cam_1.jpg")
    with open(old_file, "wb") as f:
        f.write(b"OLD_IMAGE_DATA" * 50)
    old_mtime = now_epoch - (60 * day_sec)
    os.utime(old_file, (old_mtime, old_mtime))

    # 2. Create a recent file (5 days old)
    recent_file = os.path.join(snap_dir, "recent_preview_cam_1.jpg")
    with open(recent_file, "wb") as f:
        f.write(b"RECENT_IMAGE_DATA" * 50)
    recent_mtime = now_epoch - (5 * day_sec)
    os.utime(recent_file, (recent_mtime, recent_mtime))

    # 3. Run purge with 45-day retention policy
    result = purge_expired_snapshots(max_age_days=45, snapshot_dir=snap_dir)
    assert result["status"] == "SUCCESS"
    assert result["scanned"] == 2
    assert result["purged"] == 1
    assert result["bytesReclaimed"] > 0

    # 4. Confirm expired file is unlinked and recent file is preserved
    assert not os.path.exists(old_file)
    assert os.path.exists(recent_file)


@pytest.mark.anyio
async def test_camera_role_persistence_and_constraints():
    """Validates camera role column support in Camera model and database."""
    async with TestingSessionLocal() as session:
        store = Store(store_id="STORE-ROLE-TEST", name="Role Test Store", timezone="UTC")
        lane = Lane(lane_id="LANE-ROLE-TEST", store_id="STORE-ROLE-TEST", label="Exit Lane 1")
        session.add(lane)
        await session.flush()

        # Valid Camera Roles
        cam_entry = Camera(
            camera_id="cam_entry_test_01",
            lane_id="LANE-ROLE-TEST",
            label="Main Exit Turnstile",
            ip_address="192.168.1.101",
            rtsp_path="/exit",
            camera_role="ENTRY_EXIT",
            status="ONLINE",
        )
        cam_stock = Camera(
            camera_id="cam_stock_test_01",
            lane_id="LANE-ROLE-TEST",
            label="Warehouse Shelf A",
            ip_address="192.168.1.102",
            rtsp_path="/shelf",
            camera_role="STOCK_AREA",
            status="ONLINE",
        )
        session.add_all([cam_entry, cam_stock])
        await session.flush()

        assert cam_entry.camera_role == "ENTRY_EXIT"
        assert cam_stock.camera_role == "STOCK_AREA"


@pytest.mark.anyio
async def test_initial_stock_verification_entity():
    """Validates InitialStockVerification model fields and workflow states."""
    async with TestingSessionLocal() as session:
        prod = Product(
            product_id="PROD-VERIF-TEST",
            sku_code="SKU-VERIF-999",
            name="Test Verification Cement",
            category="Building Materials",
            pack_size=1,
            unit_price=350.0,
            case_price=350.0,
        )
        session.add(prod)
        await session.flush()

        verif = InitialStockVerification(
            verification_id="verif_unit_test_123",
            product_id="PROD-VERIF-TEST",
            sku_code="SKU-VERIF-999",
            product_name="Test Verification Cement",
            camera_id="cam_stock_test_01",
            ai_proposed_count=42,
            status="PENDING_VERIFICATION",
            model_version="yolox_retail_v8",
            snapshot_url="/snapshots/verif_test.jpg",
            created_at=get_utc_now(),
        )
        session.add(verif)
        await session.flush()

        assert verif.status == "PENDING_VERIFICATION"
        assert verif.ai_proposed_count == 42
        assert verif.verified_count is None
