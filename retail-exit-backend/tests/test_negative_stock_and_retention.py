"""Tests for Negative Stock Prohibition and Legal Hold Retention Protection.

Verifies:
1. Negative stock policy strictly rejects transactions that drop balance below 0 when allow_negative=False.
2. Generates an Alert with alert_type='NEGATIVE_STOCK' upon negative balance event.
3. Retention purge unlinks expired snapshots while preserving those protected by:
   - ExitEvent.legal_hold == True
   - Open / Acknowledged Alert investigations
"""

import os
import time
import pytest
from datetime import datetime, timezone, timedelta
from tests.conftest import TestingSessionLocal
from src.db.models import (
    Material,
    MaterialInventoryBalance,
    ExitEvent,
    Alert,
    Lane,
    Store,
    get_utc_now,
)
from src.engine.inventory_ledger_engine import InventoryLedgerEngine
from src.services.retention_service import purge_expired_snapshots, get_protected_snapshot_urls


@pytest.mark.asyncio
async def test_negative_stock_prohibition_and_alert():
    """Verifies that transactions reducing inventory below zero raise ValueError and log NEGATIVE_STOCK alert."""
    async with TestingSessionLocal() as session:
        mat = Material(
            material_id="MAT-NEG-001",
            sku_code="SKU-NEG-001",
            name="Industrial Fastener 10mm",
            category="Hardware",
        )
        bal = MaterialInventoryBalance(
            balance_id="BAL-NEG-001",
            material_id="MAT-NEG-001",
            opening_stock=10,
            current_stock=10,
        )
        session.add_all([mat, bal])
        await session.commit()

        engine = InventoryLedgerEngine()

        # 1. OUT transaction exceeding stock raises ValueError when allow_negative=False
        with pytest.raises(ValueError, match="Negative stock prohibited by inventory policy"):
            await engine.record_movement(
                session=session,
                material_id="MAT-NEG-001",
                transaction_type="OUT",
                package_quantity=15,  # 15 > 10 -> would result in -5
                allow_negative=False,
            )

        # 2. Verify NEGATIVE_STOCK alert was recorded in database
        from sqlalchemy import select
        res = await session.execute(
            select(Alert).where(
                (Alert.alert_type == "NEGATIVE_STOCK") &
                (Alert.delta_units == 5)
            )
        )
        alert = res.scalars().first()
        assert alert is not None
        assert alert.severity == "HIGH"
        assert alert.status == "OPEN"
        assert "Industrial Fastener 10mm" in alert.resolution_note


@pytest.mark.asyncio
async def test_legal_hold_and_open_alert_retention_protection(tmp_path):
    """Verifies that expired surveillance snapshots are protected from deletion when on legal hold or open alert."""
    test_snapshot_dir = str(tmp_path / "snapshots")
    os.makedirs(test_snapshot_dir, exist_ok=True)

    # Create 3 fake expired snapshots (mtime = 50 days ago)
    old_time = time.time() - (50 * 86400.0)

    snap_unprotected = os.path.join(test_snapshot_dir, "snap_unprotected.jpg")
    snap_legal_hold = os.path.join(test_snapshot_dir, "snap_legal_hold.jpg")
    snap_open_alert = os.path.join(test_snapshot_dir, "snap_open_alert.jpg")

    for fpath in [snap_unprotected, snap_legal_hold, snap_open_alert]:
        with open(fpath, "wb") as f:
            f.write(b"FAKE_JPEG_DATA_1234567890")
        os.utime(fpath, (old_time, old_time))

    # Setup database records for legal hold and open alert
    async with TestingSessionLocal() as session:
        store = Store(store_id="STORE-RET-1", name="Retention Store", timezone="UTC")
        lane = Lane(lane_id="LANE-RET-1", store_id="STORE-RET-1", label="Exit Lane Ret", status="ONLINE")
        session.add_all([store, lane])
        await session.flush()

        # ExitEvent with legal_hold == True
        ev_legal = ExitEvent(
            event_id="EV-LEGAL-HOLD-01",
            lane_id="LANE-RET-1",
            legal_hold=True,
            snapshot_url="/snapshots/snap_legal_hold.jpg",
            verdict="MISMATCH",
            severity="HIGH",
        )
        session.add(ev_legal)

        # ExitEvent with open alert
        ev_alert = ExitEvent(
            event_id="EV-OPEN-ALERT-01",
            lane_id="LANE-RET-1",
            legal_hold=False,
            snapshot_url="/snapshots/snap_open_alert.jpg",
            verdict="MISMATCH",
            severity="MEDIUM",
        )
        session.add(ev_alert)
        await session.flush()

        alert_rec = Alert(
            alert_id="ALT-OPEN-01",
            event_id="EV-OPEN-ALERT-01",
            alert_type="UNDER_DECLARE",
            severity="HIGH",
            status="OPEN",
        )
        session.add(alert_rec)
        await session.commit()

        # Query protected snapshots
        protected_set = await get_protected_snapshot_urls(session)
        assert "snap_legal_hold.jpg" in protected_set
        assert "snap_open_alert.jpg" in protected_set
        assert "snap_unprotected.jpg" not in protected_set

    # Execute purge with 45-day cutoff
    result = purge_expired_snapshots(
        max_age_days=45,
        snapshot_dir=test_snapshot_dir,
        protected_basenames=protected_set,
    )

    assert result["status"] == "SUCCESS"
    assert result["scanned"] == 3
    assert result["purged"] == 1
    assert result["protected"] == 2

    # Verify physical file existence on disk
    assert not os.path.exists(snap_unprotected), "Unprotected expired snapshot should have been deleted"
    assert os.path.exists(snap_legal_hold), "Snapshot under legal hold MUST be preserved"
    assert os.path.exists(snap_open_alert), "Snapshot under open alert investigation MUST be preserved"

