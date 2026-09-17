"""Industrial Dispatch & Warehouse Exit Intelligence Platform — Automated Test Suite

Covers all 7 Master Verification Stages:
- Stage 1: Stack Before/After Removal Delta Calculation
- Stage 2: Instance Segmentation Mask Separation on Touching/Stacked Objects
- Stage 3: Automated Manifest Reconciliation (OVER_AUTHORIZED vs. UNDER_COUNT)
- Stage 4: Virtual Tripwire Directional Line Crossing (ENTRY vs. EXIT)
- Stage 5: Tripwire Biometric Handshake (VERIFIED_KNOWN vs. UNKNOWN_INTRUDER)
- Stage 6: Anti-Tailgating Multi-Person Crossing & Trailing Silhouette Concealment
- Stage 7: Camera Stream Gap Logging During Active Dispatch Sessions
- Stage 8: Dispatch & Tripwire REST API Endpoints Integration
"""

import pytest
import numpy as np
import cv2
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.main import app
from src.db.session import get_db
from src.db.models import (
    Base,
    Store,
    Camera,
    Lane,
    Employee,
    Alert,
    DispatchSession,
    VirtualTripwireConfig,
    TripwireCrossingEvent,
    get_utc_now,
)
from src.ml.material_segmentation import MaterialSegmentationService
from src.engine.dispatch_engine import DispatchEngine
from src.engine.tripwire_engine import TripwireEngine


@pytest.fixture
async def test_session():
    """In-memory SQLite database session fixture with initialized schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # Seed test store, dock lane, camera, and authorized employee
        store = Store(
            store_id="STORE-01",
            name="Central Industrial Warehouse",
        )
        dock = Lane(
            lane_id="DOCK-01",
            label="Loading Bay Dock 1",
            store_id="STORE-01",
            status="ONLINE",
        )
        cam = Camera(
            camera_id="CAM-DOCK-01",
            lane_id="DOCK-01",
            label="Dock 1 High-Angle Mast",
            ip_address="192.168.1.150",
            rtsp_path="/live/dock1",
            pipeline_mode="MATERIAL_SEGMENTATION",
            status="ONLINE",
            added_at=get_utc_now(),
        )
        emp = Employee(
            employee_id="EMP-TRUCK-01",
            name="Rajesh Sharma",
            role="CARRIER_DRIVER",
            rfid_badge_id="RFID-TRUCK-01",
            face_embedding=[0.1] * 512,
            active_flag=True,
            created_at=get_utc_now(),
        )

        session.add_all([store, dock, cam, emp])
        await session.commit()
        yield session


@pytest.fixture
async def client(test_session):
    """FastAPI test HTTP client override."""
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ==============================================================================
# STAGE 1: Stack Before/After Removal Delta Calculation
# ==============================================================================
def test_stage1_removal_delta_calculation():
    """Verifies stack delta logic: Delta = Before Count - After Count."""
    before = {
        "Cement Bag (50kg)": 40,
        "Bundled Iron Rods / Rebar": 12,
        "Industrial Wooden Pallet": 4,
    }
    after = {
        "Cement Bag (50kg)": 34,
        "Bundled Iron Rods / Rebar": 10,
        "Industrial Wooden Pallet": 4,
    }

    delta = MaterialSegmentationService.calculate_stack_removal_delta(before, after)
    assert delta["Cement Bag (50kg)"] == 6
    assert delta["Bundled Iron Rods / Rebar"] == 2
    assert delta["Industrial Wooden Pallet"] == 0

    # Raw difference (negative delta indicates items added to stack)
    after_added = {"Cement Bag (50kg)": 45}
    delta_added = MaterialSegmentationService.calculate_stack_removal_delta(before, after_added)
    assert delta_added["Cement Bag (50kg)"] == -5


# ==============================================================================
# STAGE 2: Instance Segmentation Mask Separation on Touching Objects
# ==============================================================================
def test_stage2_instance_segmentation_touching_objects():
    """Verifies that touching rectangular items (cement bags) are segmented into individual masks."""
    # Synthesize an image containing 3 touching rectangular bags on a pallet
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Background texture (dark concrete floor)
    frame[:] = (30, 30, 30)

    # 3 touching cement bags (adjacent sacks with crevice borders between them)
    # Bag 1: (100, 150) to (240, 230)
    cv2.rectangle(frame, (100, 150), (240, 228), (200, 200, 200), -1)
    # Bag 2: (100, 232) to (240, 308)
    cv2.rectangle(frame, (100, 232), (240, 308), (210, 210, 210), -1)
    # Bag 3: (100, 312) to (240, 390)
    cv2.rectangle(frame, (100, 312), (240, 390), (205, 205, 205), -1)

    result = MaterialSegmentationService.segment_materials(frame, min_confidence=0.40)
    assert result.total_instances >= 2, f"Expected at least 2 distinct instances, got {result.total_instances}"
    assert len(result.instances) == result.total_instances

    # Check mask polygons exist and have valid coordinates
    for inst in result.instances:
        assert len(inst.polygon) >= 3
        assert inst.area_pixels > 0
        assert inst.confidence >= 0.40

    # Verify annotation rendering produces valid non-empty output
    annotated = MaterialSegmentationService.annotate_frame_with_masks(frame, result.instances)
    assert annotated.shape == frame.shape
    assert not np.array_equal(annotated, frame)


# ==============================================================================
# STAGE 3: Manifest Reconciliation (OVER_AUTHORIZED vs. UNDER_COUNT)
# ==============================================================================
def test_stage3_manifest_reconciliation():
    """Verifies reconciliation against shipping manifests."""
    # Case A: Exact Match
    delta_match = {"Cement Bag (50kg)": 20}
    manifest_match = {"Cement Bag (50kg)": 20}
    status, var, details = MaterialSegmentationService.reconcile_with_manifest(delta_match, manifest_match)
    assert status == "MATCH"
    assert var == 0
    item_map = {d["sku"]: d for d in details}
    assert item_map["Cement Bag (50kg)"]["status"] == "MATCH"

    # Case B: OVER_AUTHORIZED (Theft / Excess Removal)
    delta_over = {"Cement Bag (50kg)": 25}
    manifest_over = {"Cement Bag (50kg)": 20}
    status, var, details = MaterialSegmentationService.reconcile_with_manifest(delta_over, manifest_over)
    assert status == "OVER_AUTHORIZED"
    assert var == 5
    item_map_over = {d["sku"]: d for d in details}
    assert item_map_over["Cement Bag (50kg)"]["variance"] == 5

    # Case C: UNDER_COUNT (Short Shipment)
    delta_under = {"Cement Bag (50kg)": 16}
    manifest_under = {"Cement Bag (50kg)": 20}
    status, var, details = MaterialSegmentationService.reconcile_with_manifest(delta_under, manifest_under)
    assert status == "UNDER_COUNT"
    assert var == 4
    item_map_under = {d["sku"]: d for d in details}
    assert item_map_under["Cement Bag (50kg)"]["variance"] == -4



# ==============================================================================
# STAGE 4: Virtual Tripwire Directional Line Crossing
# ==============================================================================
def test_stage4_tripwire_directional_crossing():
    """Verifies 2D vector line segment intersection and ENTRY vs EXIT resolution."""
    # Horizontal tripwire across center: start (0.0, 0.5), end (1.0, 0.5)
    # Line normal points downwards towards increasing Y (ENTRY)
    line_start = (0.0, 0.5)
    line_end = (1.0, 0.5)

    # Moving downward across the line: from (0.5, 0.3) to (0.5, 0.7)
    crossed, direction = TripwireEngine.check_trajectory_crossing(
        p_prev=(0.5, 0.3),
        p_curr=(0.5, 0.7),
        line_start=line_start,
        line_end=line_end,
    )
    assert crossed is True
    assert direction == "ENTRY"

    # Moving upward across the line: from (0.5, 0.7) to (0.5, 0.3)
    crossed, direction = TripwireEngine.check_trajectory_crossing(
        p_prev=(0.5, 0.7),
        p_curr=(0.5, 0.3),
        line_start=line_start,
        line_end=line_end,
    )
    assert crossed is True
    assert direction == "EXIT"

    # Moving parallel without crossing: from (0.2, 0.3) to (0.8, 0.3)
    crossed, direction = TripwireEngine.check_trajectory_crossing(
        p_prev=(0.2, 0.3),
        p_curr=(0.8, 0.3),
        line_start=line_start,
        line_end=line_end,
    )
    assert crossed is False
    assert direction == "UNKNOWN"


# ==============================================================================
# STAGE 5: Tripwire Biometric Handshake
# ==============================================================================
@pytest.mark.asyncio
async def test_stage5_tripwire_biometric_handshake(test_session: AsyncSession):
    """Verifies that known employees pass without alert while unrecognized subjects generate alerts."""
    # Case A: Verified Employee
    crossing_known, alert_known = await TripwireEngine.record_crossing(
        session=test_session,
        tripwire_id="TW-GATE-01",
        camera_id="CAM-DOCK-01",
        track_id="tr_known_1",
        direction="ENTRY",
        entity_type="PERSON",
        matched_employee={"decision": "MATCHED", "employee_id": "EMP-TRUCK-01"},
    )
    assert crossing_known.biometric_status == "VERIFIED_KNOWN"
    assert crossing_known.matched_employee_id == "EMP-TRUCK-01"
    assert alert_known is None

    # Case B: Unknown Intruder (isolated line traversal)
    TripwireEngine._recent_crossings.clear()
    crossing_unknown, alert_unknown = await TripwireEngine.record_crossing(
        session=test_session,
        tripwire_id="TW-GATE-02",
        camera_id="CAM-DOCK-01",
        track_id="tr_intruder_9",
        direction="ENTRY",
        entity_type="PERSON",
        matched_employee={"decision": "NO_MATCH"},
    )
    assert crossing_unknown.biometric_status == "UNKNOWN_INTRUDER"
    assert alert_unknown is not None
    assert alert_unknown.severity == "MEDIUM"
    assert "UNKNOWN INTRUDER" in alert_unknown.resolution_note



# ==============================================================================
# STAGE 6: Anti-Tailgating Multi-Person Crossing & Trailing Silhouette Concealment
# ==============================================================================
@pytest.mark.asyncio
async def test_stage6_anti_tailgating_and_concealment(test_session: AsyncSession):
    """Verifies rapid multi-person crossing (<1.2s) and silhouette concealment detection."""
    # Clear rolling buffer for clean isolation
    TripwireEngine._recent_crossings.clear()

    # 1. Multi-Person Tailgating:
    # First person crosses legally
    c1, a1 = await TripwireEngine.record_crossing(
        session=test_session,
        tripwire_id="TW-PERIM-01",
        camera_id="CAM-DOCK-01",
        track_id="tr_leader",
        direction="ENTRY",
        entity_type="PERSON",
        matched_employee={"decision": "MATCHED", "employee_id": "EMP-TRUCK-01"},
    )
    assert c1.is_tailgating is False

    # Second person immediately slips in (within 1.2s window)
    c2, a2 = await TripwireEngine.record_crossing(
        session=test_session,
        tripwire_id="TW-PERIM-01",
        camera_id="CAM-DOCK-01",
        track_id="tr_tailgater",
        direction="ENTRY",
        entity_type="PERSON",
        matched_employee={"decision": "NO_MATCH"},
    )
    assert c2.is_tailgating is True
    assert c2.tailgating_details["reason"] == "MULTI_PERSON_SIMULTANEOUS_CROSSING"
    assert a2 is not None
    assert a2.severity == "HIGH"
    assert "TAILGATING" in a2.resolution_note

    # 2. Silhouette Concealment Detection:
    leading_track = {
        "track_id": "trk_lead",
        "bbox": [100, 100, 80, 160],
        "confidence": 0.88,
        "velocity": (0.0, 1.0),
    }
    # Trailing person hidden behind leader: high IoU, suppressed confidence, aligned direction
    trailing_track = {
        "track_id": "trk_trail",
        "bbox": [110, 105, 75, 155],
        "confidence": 0.42,
        "velocity": (0.0, 0.95),
    }

    is_concealed, details = TripwireEngine.detect_concealment(leading_track, trailing_track)
    assert is_concealed is True
    assert details["reason"] == "SILHOUETTE_CONCEALMENT"
    assert details["leading_track_id"] == "trk_lead"

    # Non-concealed side-by-side un-occluded pair
    separate_track = {
        "track_id": "trk_separate",
        "bbox": [400, 100, 80, 160],
        "confidence": 0.85,
        "velocity": (0.0, 1.0),
    }
    is_concealed_false, _ = TripwireEngine.detect_concealment(leading_track, separate_track)
    assert is_concealed_false is False


# ==============================================================================
# STAGE 7: Camera Stream Gap Logging During Active Dispatch Session
# ==============================================================================
@pytest.mark.asyncio
async def test_stage7_stream_gap_logging(test_session: AsyncSession):
    """Verifies that camera offline gaps during an active dispatch session are tracked."""
    # 1. Start an active session
    session = await DispatchEngine.start_session(
        session=test_session,
        dock_lane_id="DOCK-01",
        manifest_id="MNF-2026-001",
        vehicle_identifier="MH-12-AB-9876",
        carrier_employee_id="EMP-TRUCK-01",
        manual_initial_count={"Cement Bag (50kg)": 50},
        manifest_expected={"Cement Bag (50kg)": 10},
    )

    assert session.status == "ACTIVE"
    assert session.tracking_interrupted_seconds == 0.0

    # 2. Simulate 3 consecutive 3.0-second camera stream dropouts
    await DispatchEngine.record_stream_gap(test_session, "DOCK-01", 3.0)
    await DispatchEngine.record_stream_gap(test_session, "DOCK-01", 3.0)
    await DispatchEngine.record_stream_gap(test_session, "DOCK-01", 3.0)

    # 3. Complete session with manual after count (40 remaining -> 10 removed)
    completed_session, alert = await DispatchEngine.complete_session(
        session=test_session,
        session_id=session.session_id,
        manual_override_after={"Cement Bag (50kg)": 40},
    )

    assert completed_session.status == "COMPLETED"
    assert completed_session.tracking_interrupted_seconds == 9.0
    assert completed_session.removed_delta["Cement Bag (50kg)"] == 10
    assert completed_session.discrepancy_type == "MATCH"
    assert alert is None


# ==============================================================================
# STAGE 8: Dispatch & Tripwire REST API Endpoints Integration
# ==============================================================================
@pytest.mark.asyncio
async def test_stage8_dispatch_and_tripwire_rest_api(client: AsyncClient):
    """Tests the REST APIs for starting, completing sessions, and configuring tripwires."""
    # 1. Get material classes
    resp_classes = await client.get("/api/dispatch/materials/classes")
    assert resp_classes.status_code == 200
    classes_data = resp_classes.json()
    assert "material_classes" in classes_data
    assert len(classes_data["material_classes"]) >= 4

    # 2. Start dispatch session
    resp_start = await client.post(
        "/api/dispatch/session/start",
        json={
            "dockLaneId": "DOCK-01",
            "manifestId": "MNF-REST-99",
            "vehicleIdentifier": "DL-01-XYZ-1122",
            "carrierEmployeeId": "EMP-TRUCK-01",
            "manifestExpected": {"Heavy Corrugated Master Carton": 15},
            "manualInitialCount": {"Heavy Corrugated Master Carton": 50},
        },
    )
    assert resp_start.status_code == 200
    start_data = resp_start.json()
    sess_id = start_data["sessionId"]
    assert start_data["status"] == "ACTIVE"

    # 3. Complete dispatch session with excess removal (removed 20 instead of 15 -> OVER_AUTHORIZED)
    resp_complete = await client.post(
        f"/api/dispatch/session/{sess_id}/complete",
        json={"manualAfterCount": {"Heavy Corrugated Master Carton": 30}},
    )
    assert resp_complete.status_code == 200
    comp_data = resp_complete.json()
    assert comp_data["discrepancyType"] == "OVER_AUTHORIZED"
    assert comp_data["discrepancyMagnitude"] == 5
    assert comp_data["alertGenerated"] is True

    # 4. Create Virtual Tripwire
    resp_tw_create = await client.post(
        "/api/tripwire/configs",
        json={
            "cameraId": "CAM-DOCK-01",
            "label": "Loading Dock 1 Perimeter Tripwire",
            "lineCoords": [[0.1, 0.5], [0.9, 0.5]],
            "directionMode": "ENTRY",
            "active": True,
        },
    )
    assert resp_tw_create.status_code in (200, 201)
    tw_data = resp_tw_create.json()
    assert tw_data["label"] == "Loading Dock 1 Perimeter Tripwire"


    # 5. List Virtual Tripwires
    resp_tw_list = await client.get("/api/tripwire/configs?cameraId=CAM-DOCK-01")
    assert resp_tw_list.status_code == 200
    assert len(resp_tw_list.json()) >= 1
