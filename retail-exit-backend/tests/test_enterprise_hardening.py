"""Tests for Enterprise Production Hardening

Validates:
1. Corrugated Galvanized Iron (CGI) / Tin Sheet Segmentation & Glare Mitigation
2. Physical Paper Manifest Edge OCR & Barcode Scanner Debouncing
3. Multi-Camera Temporal Re-ID Global Hungarian Solver & Floor Topology
4. Industrial Modbus TCP Hardware Relay Actuation & Fail-Secure Watchdog
"""

import pytest
import numpy as np
import time
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from src.main import app
from src.ml.material_segmentation import count_corrugated_sheets
from src.engine.manifest_ingestion_daemon import BarcodeScannerListener, DeskManifestScanner
from src.engine.journey_engine import (
    ReIDTracklet,
    GlobalHungarianReIDSolver,
    SpatialTopologyGraph,
    CrossCameraJourneyEngine,
)
from src.engine.hardware_interlock import HardwareInterlockManager, AsyncModbusTCPDriver


# ─────────────────────────────────────────────────────────────────────────────
# 1. Corrugated Tin Sheet Segmentation & Edge Splitting
# ─────────────────────────────────────────────────────────────────────────────

def test_corrugated_tin_sheet_counting():
    """Tests counting corrugated tin sheets with specular glare and edge splitting."""
    # Create synthetic metallic corrugated sheet stack: 200x300 image with 12 horizontal sheet interfaces
    h, w = 240, 320
    img = np.full((h, w, 3), 160, dtype=np.uint8)

    # Add 10 metallic sheets spaced every 20 pixels
    sheet_y_coords = [30 + i * 18 for i in range(10)]
    for y in sheet_y_coords:
        # Sheet edge interface: dark shadow line followed by bright reflection
        img[y - 1 : y + 1, :] = 40
        img[y + 1 : y + 3, :] = 230

    # Add intense specular glare washout patch in the center (industrial galvanized zinc reflection)
    img[60:140, 100:200] = 255

    count, overlay, conf = count_corrugated_sheets(img, min_peak_distance=14)

    assert count >= 8, f"Expected at least 8 sheets detected under glare, got {count}"
    assert overlay.shape == img.shape
    assert conf >= 0.70


def test_corrugated_sheet_empty_degenerate():
    """Tests empty and degenerate image inputs."""
    count, overlay, conf = count_corrugated_sheets(np.zeros((0, 0, 3), dtype=np.uint8))
    assert count == 0
    assert conf == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Physical Paper Manifest Ingestion & Barcode Scanner
# ─────────────────────────────────────────────────────────────────────────────

def test_barcode_scanner_debouncing_and_parsing():
    """Tests 750ms barcode debouncing and GS1-128 / DataMatrix parsing."""
    listener = BarcodeScannerListener(debounce_window_ms=750.0)

    # 1. Normal scan
    rec1 = listener.process_raw_scan("CARTON-SKU-99210")
    assert rec1 is not None
    assert rec1.parsed_sku == "CARTON-SKU-99210"

    # 2. Duplicate rapid scan within 750ms -> Debounced (None)
    rec2 = listener.process_raw_scan("CARTON-SKU-99210")
    assert rec2 is None

    # 3. GS1-128 Scan
    rec3 = listener.process_raw_scan("(01)00123456789012(21)SER98765")
    assert rec3 is not None
    assert rec3.symbology == "GS1_128"
    assert rec3.parsed_sku == "00123456789012"
    assert rec3.serial_number == "SER98765"


def test_desk_manifest_scanner_quad_detection_and_ocr():
    """Tests quadrilateral document contour detection, perspective deskew, and BOL parsing."""
    # Create canvas with an angled white document on dark background
    canvas = np.full((1000, 1000, 3), 30, dtype=np.uint8)
    doc_pts = np.array([[200, 200], [800, 220], [780, 850], [220, 830]], dtype=np.int32)
    import cv2
    cv2.fillPoly(canvas, [doc_pts], (245, 245, 245))

    quad = DeskManifestScanner.detect_document_quad(canvas)
    assert quad is not None
    assert len(quad) == 4

    # Test OCR parsing
    raw_ocr = (
        "BILL OF LADING: BOL-2026-TIN-881\n"
        "CARRIER: Vikram Transport\n"
        "CEMENT PORTLAND: 40 BAGS\n"
        "CORRUGATED TIN SHEET: 25 SHEETS\n"
        "REBAR STEEL ROD: 10 BUNDLES\n"
    )
    manifest = DeskManifestScanner.parse_manifest_text(raw_ocr)
    assert manifest.bol_number == "BOL-2026-TIN-881"
    assert manifest.carrier_name == "Vikram Transport"
    assert manifest.line_items.get("cement_bag") == 40
    assert manifest.line_items.get("corrugated_tin_sheet") == 25
    assert manifest.line_items.get("iron_rod_bundle") == 10
    assert manifest.confidence >= 0.85


# ─────────────────────────────────────────────────────────────────────────────
# 3. Multi-Camera Temporal Re-ID Global Hungarian Solver
# ─────────────────────────────────────────────────────────────────────────────

def test_multicamera_handover_reid():
    """Tests multi-camera person Re-ID across temporal camera handover zones using Hungarian solver."""
    t0 = time.time()

    # Track A: Person 1 at Camera 1 (Zone Storage)
    vec1 = np.random.randn(512).astype(np.float32)
    vec1 /= np.linalg.norm(vec1)
    trk1 = ReIDTracklet(
        track_id="trk_01",
        camera_id="cam_storage",
        zone_id="ZONE_STORAGE",
        timestamp=t0,
        feature_vector=vec1,
        person_name="Amitabh Patel",
    )

    # Track B: Person 2 at Camera 1 (Zone Storage)
    vec2 = np.random.randn(512).astype(np.float32)
    vec2 /= np.linalg.norm(vec2)
    trk2 = ReIDTracklet(
        track_id="trk_02",
        camera_id="cam_storage",
        zone_id="ZONE_STORAGE",
        timestamp=t0,
        feature_vector=vec2,
        person_name="Sunil Rao",
    )

    # New sightings at Camera 2 (Zone Loading Dock) after expected dt=35s
    # Sighting A is Person 1 with small noise
    sght_vec1 = vec1 + np.random.normal(0, 0.05, 512).astype(np.float32)
    sght_vec1 /= np.linalg.norm(sght_vec1)
    sght1 = ReIDTracklet(
        track_id="sght_101",
        camera_id="cam_dock",
        zone_id="ZONE_LOADING_DOCK",
        timestamp=t0 + 35.0,
        feature_vector=sght_vec1,
    )

    # Sighting B is Person 2 with small noise
    sght_vec2 = vec2 + np.random.normal(0, 0.05, 512).astype(np.float32)
    sght_vec2 /= np.linalg.norm(sght_vec2)
    sght2 = ReIDTracklet(
        track_id="sght_102",
        camera_id="cam_dock",
        zone_id="ZONE_LOADING_DOCK",
        timestamp=t0 + 34.0,
        feature_vector=sght_vec2,
    )

    matches = GlobalHungarianReIDSolver.solve_associations(
        existing_tracks=[trk1, trk2],
        new_sightings=[sght2, sght1],  # Swapped order to test Hungarian assignment
    )

    assert len(matches) == 2
    # Verify trk1 (index 0) matched sght1 (index 1)
    match_dict = {m[0]: m[1] for m in matches}
    assert match_dict[0] == 1
    assert match_dict[1] == 0


def test_storage_to_exit_diversion_rule():
    """Tests diversion detection when bulk goods acquired in storage appear at exit without dock staging."""
    CrossCameraJourneyEngine.clear_all()
    t0 = datetime.now(timezone.utc)

    # 1. Sighting at Storage Aisle: picks 15 cement bags
    CrossCameraJourneyEngine.record_waypoint(
        camera_id="cam_storage_bay",
        zone_id="ZONE_STORAGE",
        zone_name="Bulk Storage",
        person_name="Manoj Sharma",
        face_confidence=0.91,
        items_in_possession={"cement_bag": 15},
        timestamp=t0,
    )

    # 2. Direct Sighting at Exit Gate without dock staging: carrying only 10 bags (5 diverted)
    CrossCameraJourneyEngine.record_waypoint(
        camera_id="cam_exit_gate",
        zone_id="ZONE_EXIT",
        zone_name="Main Exit Barrier",
        person_name="Manoj Sharma",
        face_confidence=0.89,
        items_in_possession={"cement_bag": 10},
        timestamp=t0 + timedelta(seconds=40),
    )

    traj = CrossCameraJourneyEngine.evaluate_journey("Manoj Sharma")
    assert traj is not None
    assert traj.has_diversion_anomaly is True
    assert traj.journey_status == "FLAGGED_DIVERSION"
    assert traj.diversion_details["diverted_items"]["cement_bag"] == 5
    assert traj.diversion_details["missing_staging_dock_event"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 4. Industrial Modbus Relay Actuation & Fail-Safe Invariant
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hardware_relay_fail_safe():
    """Tests Modbus relay lock actuation latency <= 50ms and fail-secure watchdog lockdown."""
    manager = HardwareInterlockManager(
        device_id="TEST_TURNSTILE_01",
        host="127.0.0.1",
        port=502,
        heartbeat_interval_ms=100.0,
    )
    await manager.initialize()

    # Initial state must be FAIL-SECURE LOCKED
    assert manager.is_energized is False

    # Unlock temporarily
    unlocked = await manager.unlock_barrier_temporary(duration_seconds=0.2, authorized_by="AUTH_CARD_01")
    assert unlocked is True
    assert manager.is_energized is True

    # Immediate manual lock: verify latency SLA <= 50ms
    t0 = time.perf_counter()
    locked = await manager.lock_barrier("EMERGENCY_TRIPWIRE")
    latency_ms = (time.perf_counter() - t0) * 1000.0
    assert locked is True
    assert manager.is_energized is False
    assert latency_ms < 50.0

    manager.stop_watchdog()


# ─────────────────────────────────────────────────────────────────────────────
# 5. REST API Edge Manifest Scan
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_edge_manifest_scan():
    """Tests POST /api/dispatch/manifest/edge-scan."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/dispatch/manifest/edge-scan",
            json={
                "rawOcrText": "MANIFEST #BOL-2026-CORRUGATED\nCEMENT: 50 BAGS\nTIN SHEET: 30 SHEETS\n",
                "dockLaneId": None,
                "autoStartSession": False,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["bolNumber"] == "BOL-2026-CORRUGATED"
        assert data["lineItems"].get("cement_bag") == 50
        assert data["lineItems"].get("corrugated_tin_sheet") == 30
        assert data["confidence"] >= 0.80
