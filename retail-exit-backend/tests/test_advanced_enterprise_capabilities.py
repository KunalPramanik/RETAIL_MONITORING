"""Tests for Advanced Enterprise Capabilities

Validates:
1. 3D Volumetric & Pallet Density Engine (Hollow Stack & Chimney Anomaly Detection)
2. Cross-Camera Spatiotemporal Journey & Material Diversion Engine
3. Worker Ergonomics & Industrial Safety Intelligence (OSHA / ISO 45001)
4. Tri-Sensor Manifest Fusion Engine (Vision + Barcode/RFID + Dynamic Weight Scale)
5. Instant Mobile Security Dispatcher & Webhook Generator
6. Continuous Model Auto-Curation & Shadow Benchmark Evaluator
7. Hardware Acceleration Engine Profiler & Provider Selector
8. FastAPI Endpoints for Advanced Enterprise Capabilities
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from src.main import app
from src.ml.volumetric_service import (
    VolumetricPalletAnalyzer,
    VolumetricAnalysisResult,
    STANDARD_MATERIAL_SPECS,
)
from src.engine.journey_engine import CrossCameraJourneyEngine
from src.ml.ergonomic_safety import ErgonomicSafetyAnalyzer
from src.engine.sensor_fusion import TriSensorFusionEngine, TriSensorInput
from src.realtime.mobile_dispatcher import MobileSecurityDispatcher
from src.ml.model_autocurator import ModelAutoCurator, BenchmarkMetrics
from src.ml.acceleration import HardwareAccelerator


# ─────────────────────────────────────────────────────────────────────────────
# 1. Volumetric & Pallet Density Analysis
# ─────────────────────────────────────────────────────────────────────────────

def test_volumetric_solid_pallet_normal():
    """Tests normal solid pallet calculation for cement bags."""
    # 20x20 grid representing 1.0m x 1.0m pallet area (scale = 0.05m/pixel)
    # Ground plane at 2.5m, pallet top surface at 1.5m (height = 1.0m)
    depth_grid = np.full((20, 20), 1.50, dtype=np.float32)

    res = VolumetricPalletAnalyzer.analyze_depth_surface(
        depth_map_meters=depth_grid,
        pixel_to_meter_scale=0.05,
        material_id="cement_bag",
        visual_detected_units=25,
        ground_plane_height_m=2.50,
    )

    assert res.dimensions_m["width"] == 1.0
    assert res.dimensions_m["length"] == 1.0
    assert res.dimensions_m["height"] == 1.0
    assert res.bounding_volume_m3 == 1.0
    assert res.occupied_solid_volume_m3 == 1.0
    assert res.packing_density == 1.0
    assert res.is_hollow_anomaly is False
    assert res.estimated_units_from_volume > 0


def test_volumetric_chimney_stacking_detection():
    """Tests detection of chimney stacking where outer perimeter is tall but center is hollow."""
    # 20x20 grid. Outer border has height = 1.0m (depth = 1.5m from 2.5m ground).
    # Inner 10x10 core is sunken/empty (depth = 2.4m, height = 0.1m).
    depth_grid = np.full((20, 20), 1.50, dtype=np.float32)
    depth_grid[5:15, 5:15] = 2.40  # Hollow center

    res = VolumetricPalletAnalyzer.analyze_depth_surface(
        depth_map_meters=depth_grid,
        pixel_to_meter_scale=0.05,
        material_id="cement_bag",
        visual_detected_units=30,
        ground_plane_height_m=2.50,
    )

    assert res.is_hollow_anomaly is True
    assert res.anomaly_reason is not None and "CHIMNEY_STACKING_DETECTED" in res.anomaly_reason
    assert res.dimensions_m["height"] == 1.0


def test_volumetric_internal_voids_detected():
    """Tests detection when exterior camera counts more units than physical volume can hold."""
    # Very thin layer pallet: height = 0.15m, 1.0m x 1.0m -> volume = 0.15 m3
    # 1 cement bag is ~0.039 m3, so 0.15 m3 can hold at most ~5 bags
    # But visual count claims 40 bags!
    depth_grid = np.full((20, 20), 2.35, dtype=np.float32)

    res = VolumetricPalletAnalyzer.analyze_depth_surface(
        depth_map_meters=depth_grid,
        pixel_to_meter_scale=0.05,
        material_id="cement_bag",
        visual_detected_units=40,
        ground_plane_height_m=2.50,
    )

    assert res.is_hollow_anomaly is True
    assert res.anomaly_reason is not None and "INTERNAL_VOIDS_DETECTED" in res.anomaly_reason


# ─────────────────────────────────────────────────────────────────────────────
# 2. Cross-Camera Spatiotemporal Journey & Diversion Engine
# ─────────────────────────────────────────────────────────────────────────────

def test_journey_normal_transit():
    """Tests normal subject journey across zones without diversion."""
    CrossCameraJourneyEngine.clear_all()
    t0 = datetime.now(timezone.utc)

    # 1. Entry Lobby
    CrossCameraJourneyEngine.record_waypoint(
        camera_id="cam_entry",
        zone_id="ENTRY_LOBBY",
        zone_name="Entry Gate",
        person_name="Rahul Sharma",
        face_confidence=0.88,
        items_in_possession={},
        timestamp=t0,
    )

    # 2. Storage Aisle: picks 4 cartons
    CrossCameraJourneyEngine.record_waypoint(
        camera_id="cam_aisle_3",
        zone_id="AISLE_3",
        zone_name="Hardware Aisle",
        person_name="Rahul Sharma",
        face_confidence=0.85,
        items_in_possession={"carton_box": 4},
        timestamp=t0 + timedelta(seconds=30),
    )

    # 3. Staging Bay: stages 4 cartons
    CrossCameraJourneyEngine.record_waypoint(
        camera_id="cam_bay_1",
        zone_id="LOADING_DOCK",
        zone_name="Dock Bay 1",
        person_name="Rahul Sharma",
        face_confidence=0.89,
        items_in_possession={"carton_box": 4},
        timestamp=t0 + timedelta(seconds=60),
    )

    trajectory = CrossCameraJourneyEngine.evaluate_journey("Rahul Sharma", mark_completed=True)
    assert trajectory is not None
    assert trajectory.person_name == "Rahul Sharma"
    assert trajectory.identity_status == "VERIFIED_EMPLOYEE"
    assert trajectory.has_diversion_anomaly is False
    assert trajectory.journey_status == "COMPLETED"
    assert len(trajectory.waypoints) == 3


def test_journey_in_facility_diversion_flag():
    """Tests detection of items picked in aisle but missing at exit."""
    CrossCameraJourneyEngine.clear_all()
    t0 = datetime.now(timezone.utc)

    # 1. Aisle: picks 10 cement bags
    CrossCameraJourneyEngine.record_waypoint(
        camera_id="cam_aisle_1",
        zone_id="AISLE_STORAGE",
        zone_name="Cement Storage",
        person_name="Vikram Singh",
        face_confidence=0.92,
        items_in_possession={"cement_bag": 10},
        timestamp=t0,
    )

    # 2. Exit Gate: arrives with only 6 cement bags (4 missing)
    CrossCameraJourneyEngine.record_waypoint(
        camera_id="cam_exit",
        zone_id="EXIT_GATE",
        zone_name="Main Exit Gate",
        person_name="Vikram Singh",
        face_confidence=0.90,
        items_in_possession={"cement_bag": 6},
        timestamp=t0 + timedelta(seconds=45),
    )

    trajectory = CrossCameraJourneyEngine.evaluate_journey("Vikram Singh")
    assert trajectory is not None
    assert trajectory.has_diversion_anomaly is True
    assert trajectory.journey_status == "FLAGGED_DIVERSION"
    assert trajectory.diversion_details is not None
    assert trajectory.diversion_details["diverted_items"]["cement_bag"] == 4


def test_journey_zero_speculation_identity():
    """Tests that low-confidence (<0.65) sightings are strictly anonymized as UNKNOWN_PERSON."""
    CrossCameraJourneyEngine.clear_all()
    wp = CrossCameraJourneyEngine.record_waypoint(
        camera_id="cam_door",
        zone_id="EXIT_GATE",
        zone_name="Exit",
        person_name="Rahul Sharma",
        face_confidence=0.52,  # Low confidence
        items_in_possession={"phone": 1},
    )
    assert wp.carrier_identity == "UNKNOWN_PERSON"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Worker Ergonomics & Industrial Safety Intelligence
# ─────────────────────────────────────────────────────────────────────────────

def test_ergonomics_upright_posture():
    """Tests spine flexion kinematics on upright standing posture."""
    keypoints = {
        "neck": (320, 100),
        "mid_hip": (320, 300),  # Vertical dx=0, dy=200
        "left_hip": (300, 300),
        "left_knee": (300, 450),
        "left_ankle": (300, 600),
    }
    angle = ErgonomicSafetyAnalyzer.calculate_spine_flexion(keypoints)
    assert angle == 0.0

    frame = np.full((720, 1280, 3), 128, dtype=np.uint8)
    res = ErgonomicSafetyAnalyzer.evaluate_ergonomic_safety(
        frame_bgr=frame,
        person_bbox=[250, 80, 150, 550],
        keypoints=keypoints,
        material_weight_kg=5.0,
        material_tier="SINGLE_UNIT",
        nearby_persons_count=1,
        enforce_ppe=False,
    )
    assert res.is_hazardous_bend is False
    assert res.lift_technique == "UPRIGHT_STANDING"
    assert res.team_lift_compliant is True


def test_ergonomics_hazardous_back_bend():
    """Tests hazardous spine flexion (> 45 deg) with straight legs."""
    # Torso angled forward: neck is far forward in x
    keypoints = {
        "neck": (450, 200),
        "mid_hip": (320, 300),  # dx = 130, dy = 100 -> angle = atan(130/100) = ~52.4 deg
        "left_hip": (320, 300),
        "left_knee": (320, 450),
        "left_ankle": (320, 600),
    }
    angle = ErgonomicSafetyAnalyzer.calculate_spine_flexion(keypoints)
    assert angle > 45.0

    frame = np.full((720, 1280, 3), 128, dtype=np.uint8)
    res = ErgonomicSafetyAnalyzer.evaluate_ergonomic_safety(
        frame_bgr=frame,
        person_bbox=[250, 150, 250, 480],
        keypoints=keypoints,
        material_weight_kg=15.0,
        material_tier="PACKAGED_BOX",
        nearby_persons_count=1,
        enforce_ppe=False,
    )
    assert res.is_hazardous_bend is True
    assert res.lift_technique == "BACK_FLEXION_HAZARDOUS"
    assert any("HAZARDOUS_SPINE_FLEXION" in v for v in res.violations)


def test_ergonomics_team_lift_enforcement():
    """Tests team lift requirement for bulk materials (> 25kg)."""
    keypoints = {"neck": (320, 100), "mid_hip": (320, 300)}
    frame = np.full((720, 1280, 3), 128, dtype=np.uint8)

    # Solo lift of 50kg cement bag -> Violation
    solo_res = ErgonomicSafetyAnalyzer.evaluate_ergonomic_safety(
        frame_bgr=frame,
        person_bbox=[250, 80, 150, 550],
        keypoints=keypoints,
        material_weight_kg=50.0,
        material_tier="BULK_MATERIAL",
        nearby_persons_count=1,
        enforce_ppe=False,
    )
    assert solo_res.team_lift_compliant is False
    assert any("TEAM_LIFT_VIOLATION" in v for v in solo_res.violations)

    # Team lift of 50kg cement bag with 2 workers -> Compliant
    team_res = ErgonomicSafetyAnalyzer.evaluate_ergonomic_safety(
        frame_bgr=frame,
        person_bbox=[250, 80, 150, 550],
        keypoints=keypoints,
        material_weight_kg=50.0,
        material_tier="BULK_MATERIAL",
        nearby_persons_count=2,
        enforce_ppe=False,
    )
    assert team_res.team_lift_compliant is True


# ─────────────────────────────────────────────────────────────────────────────
# 4. Tri-Sensor Manifest Fusion Engine
# ─────────────────────────────────────────────────────────────────────────────

def test_tri_sensor_full_match():
    """Tests full concordance across Vision, RFID, and Scale against Manifest."""
    inp = TriSensorInput(
        vision_counts={"carton_box": 50},
        scanned_barcodes=[f"BC_{i:03d}" for i in range(25)],
        scanned_rfid_tags=[f"RFID_{i:03d}" for i in range(25, 50)],
        gross_scale_weight_kg=520.0,
        tare_weight_kg=20.0,          # Net weight = 500.0 kg (50 boxes @ 10kg = 500kg)
        manifest_expected={"carton_box": 50},
        material_unit_weights_kg={"carton_box": 10.0},
    )
    res = TriSensorFusionEngine.reconcile(inp)
    assert res.status == "MATCH"
    assert res.is_authorized is True
    assert res.variance_units == 0
    assert res.net_measured_weight_kg == 500.0
    assert res.channel_concordance["vision_vs_manifest"] is True
    assert res.channel_concordance["weight_vs_manifest"] is True


def test_tri_sensor_over_carry_alert():
    """Tests over-carry detection when visual camera counts excess units."""
    inp = TriSensorInput(
        vision_counts={"cement_bag": 45},
        scanned_barcodes=[],
        scanned_rfid_tags=[],
        gross_scale_weight_kg=2250.0,
        tare_weight_kg=0.0,
        manifest_expected={"cement_bag": 40},
        material_unit_weights_kg={"cement_bag": 50.0},
    )
    res = TriSensorFusionEngine.reconcile(inp)
    assert res.status == "OVER_CARRY"
    assert res.is_authorized is False
    assert res.variance_units == 5
    assert res.discrepancy_severity in ("HIGH", "CRITICAL")
    assert "LOCK_GATE" in res.recommended_action


def test_tri_sensor_hollow_weight_anomaly():
    """Tests hollow dummy carton detection when count matches but weight is significantly light."""
    inp = TriSensorInput(
        vision_counts={"carton_box": 50},
        scanned_barcodes=[f"BC_{i:03d}" for i in range(50)],
        scanned_rfid_tags=[],
        gross_scale_weight_kg=300.0,   # Expected 500kg, but only 300kg (-40% delta)
        tare_weight_kg=0.0,
        manifest_expected={"carton_box": 50},
        material_unit_weights_kg={"carton_box": 10.0},
    )
    res = TriSensorFusionEngine.reconcile(inp)
    assert res.status == "WEIGHT_ANOMALY"
    assert res.is_authorized is False
    assert res.discrepancy_attribution is not None and "HOLLOW_CARTON_SUSPICION" in res.discrepancy_attribution


# ─────────────────────────────────────────────────────────────────────────────
# 5. Instant Mobile Security Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def test_mobile_alert_card_hmac_and_zero_speculation():
    """Tests mobile alert card formatting, HMAC verification, and zero-speculation identity."""
    card = MobileSecurityDispatcher.create_alert_card(
        alert_id="alt_test_001",
        alert_type="OVER_CARRY",
        severity="CRITICAL",
        location_name="Loading Bay 3",
        camera_id="cam_dock_03",
        carrier_name="Amit Patel",
        carrier_confidence=0.55,  # Unverified (< 0.65)
        discrepancy_delta=3,
        material_name="cement_bag",
    )

    assert card.carrier_name == "UNKNOWN_PERSON"
    assert card.carrier_status == "UNKNOWN_PERSON"
    assert len(card.hmac_signature) == 64

    # Format Telegram
    tg_text = MobileSecurityDispatcher.format_telegram_markdown(card)
    assert "UNKNOWN_PERSON" in tg_text
    assert "LOCK EXIT GATE" in tg_text

    # Format WhatsApp
    wa_payload = MobileSecurityDispatcher.format_whatsapp_payload(card, "+919876543210")
    assert wa_payload["to"] == "+919876543210"
    assert "LOCK_alt_test_001" in wa_payload["interactive"]["action"]["buttons"][0]["reply"]["id"]


# ─────────────────────────────────────────────────────────────────────────────
# 6. Continuous Model Auto-Curation & Shadow Evaluator
# ─────────────────────────────────────────────────────────────────────────────

def test_autocurator_approved_candidate():
    """Tests approval of a candidate model exceeding +1.5% mAP with 0 hard negative errors."""
    cand = BenchmarkMetrics(
        map_50=0.915,       # +3.0% over baseline 0.885
        map_50_95=0.720,
        precision=0.930,
        recall=0.890,
        hard_negative_false_positives=0,
        inference_latency_ms=19.0,  # ~2.7% increase
    )
    decision = ModelAutoCurator.evaluate_candidate("v6.2-epoch10", cand)
    assert decision.approved_for_production is True
    assert decision.status == "APPROVED_HOTSWAP"
    assert decision.delta_map_50 == 0.030
    assert decision.hard_negatives_passed is True


def test_autocurator_rejects_hard_negative_errors():
    """Tests rejection of candidate that produces false positive detections on hard negatives."""
    cand = BenchmarkMetrics(
        map_50=0.920,
        map_50_95=0.725,
        precision=0.935,
        recall=0.895,
        hard_negative_false_positives=2,  # VIOLATION: 2 false positives on blank wall
        inference_latency_ms=18.5,
    )
    decision = ModelAutoCurator.evaluate_candidate("v6.2-bad-negatives", cand)
    assert decision.approved_for_production is False
    assert decision.status == "REJECTED_FALSE_POSITIVES"
    assert any("HARD_NEGATIVE_FAILURE" in r for r in decision.rejection_reasons)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Hardware Acceleration Engine Profiler
# ─────────────────────────────────────────────────────────────────────────────

def test_hardware_accelerator_profile():
    """Tests hardware profile discovery and benchmarking execution."""
    profile = HardwareAccelerator.get_hardware_profile()
    assert profile.selected_provider in profile.available_providers
    assert profile.intra_op_threads >= 1
    assert profile.estimated_throughput_fps > 0.0

    benchmark = HardwareAccelerator.benchmark_synthetic_pipeline(iterations=5, warmup=1)
    assert benchmark.mean_latency_ms > 0.0
    assert benchmark.achievable_fps > 0.0
    assert benchmark.iterations_run == 5


# ─────────────────────────────────────────────────────────────────────────────
# 8. FastAPI V2 Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_v2_volumetric_endpoint():
    """Tests POST /api/v2/volumetric/analyze."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        grid = [[1.50 for _ in range(10)] for _ in range(10)]
        res = await client.post(
            "/api/v2/volumetric/analyze",
            json={
                "material_id": "carton_box",
                "depth_grid": grid,
                "pixel_to_meter_scale": 0.05,
                "visual_detected_units": 10,
                "ground_plane_height_m": 2.50,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "dimensions_m" in data
        assert "packing_density" in data
        assert data["is_hollow_anomaly"] is False


@pytest.mark.asyncio
async def test_api_v2_fusion_endpoint():
    """Tests POST /api/v2/fusion/reconcile."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v2/fusion/reconcile",
            json={
                "vision_counts": {"carton_box": 30},
                "scanned_barcodes": [f"BOX_{i}" for i in range(30)],
                "scanned_rfid_tags": [],
                "gross_scale_weight_kg": 300.0,
                "tare_weight_kg": 0.0,
                "manifest_expected": {"carton_box": 30},
                "material_unit_weights_kg": {"carton_box": 10.0},
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "MATCH"
        assert data["is_authorized"] is True


@pytest.mark.asyncio
async def test_api_v2_acceleration_profile_endpoint():
    """Tests GET /api/v2/acceleration/profile."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v2/acceleration/profile")
        assert res.status_code == 200
        data = res.json()
        assert "profile" in data
        assert "benchmark" in data
        assert data["benchmark"]["achievable_fps"] > 0
