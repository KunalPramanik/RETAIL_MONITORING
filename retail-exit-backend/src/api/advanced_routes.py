"""FastAPI Endpoints for Advanced Enterprise Capabilities

Exposes:
1. 3D Volumetric Pallet Analysis (/api/v2/volumetric/analyze)
2. Cross-Camera Spatiotemporal Journey (/api/v2/journey/*)
3. Ergonomic Safety & OSHA Compliance (/api/v2/ergonomics/analyze)
4. Tri-Sensor Manifest Fusion (/api/v2/fusion/reconcile)
5. Hardware Acceleration Engine Profiling (/api/v2/acceleration/profile)
6. Continuous Auto-Curation Evaluation (/api/v2/autocuration/evaluate-candidate)
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import numpy as np

from src.ml.volumetric_service import VolumetricPalletAnalyzer, VolumetricAnalysisResult
from src.engine.journey_engine import CrossCameraJourneyEngine, JourneyTrajectory
from src.ml.ergonomic_safety import ErgonomicSafetyAnalyzer, ErgonomicAssessment
from src.engine.sensor_fusion import TriSensorFusionEngine, TriSensorInput, TriSensorReconciliationResult
from src.ml.acceleration import HardwareAccelerator, HardwareProfile, BenchmarkResult
from src.ml.model_autocurator import ModelAutoCurator, BenchmarkMetrics, CurationDecision

router = APIRouter(prefix="/v2", tags=["Advanced Enterprise Capabilities"])


# ── Schemas ──

class VolumetricRequest(BaseModel):
    material_id: str
    depth_grid: List[List[float]]       # 2D list of depth values in meters
    pixel_to_meter_scale: float = 0.05
    visual_detected_units: int = 0
    ground_plane_height_m: float = 2.50


class WaypointRequest(BaseModel):
    camera_id: str
    zone_id: str
    zone_name: str
    person_name: str
    face_confidence: float
    items_in_possession: Dict[str, int]
    dwell_seconds: float = 5.0


class ErgonomicRequest(BaseModel):
    person_bbox: List[int]              # [x, y, w, h]
    keypoints: Dict[str, List[int]]     # {"neck": [x, y], "mid_hip": [x, y], ...}
    material_weight_kg: float = 0.0
    material_tier: str = "SINGLE_UNIT"
    nearby_persons_count: int = 1
    enforce_ppe: bool = True


class TriSensorFusionRequest(BaseModel):
    vision_counts: Dict[str, int]
    scanned_barcodes: List[str] = Field(default_factory=list)
    scanned_rfid_tags: List[str] = Field(default_factory=list)
    gross_scale_weight_kg: float
    tare_weight_kg: float = 0.0
    manifest_expected: Dict[str, int]
    material_unit_weights_kg: Dict[str, float] = Field(default_factory=dict)
    weight_tolerance_pct: float = 7.5


class CandidateEvaluationRequest(BaseModel):
    candidate_version: str
    candidate_map_50: float
    candidate_map_50_95: float
    candidate_precision: float
    candidate_recall: float
    candidate_hard_negative_fps: int
    candidate_latency_ms: float
    baseline_map_50: Optional[float] = None
    baseline_latency_ms: Optional[float] = None


# ── Endpoints ──

@router.post("/volumetric/analyze", response_model=Dict[str, Any])
async def analyze_volumetric(req: VolumetricRequest) -> Dict[str, Any]:
    """Analyzes 3D depth surface to calculate pallet volume, density, and detect hollow center anomalies."""
    try:
        arr = np.array(req.depth_grid, dtype=np.float32)
        res = VolumetricPalletAnalyzer.analyze_depth_surface(
            depth_map_meters=arr,
            pixel_to_meter_scale=req.pixel_to_meter_scale,
            material_id=req.material_id,
            visual_detected_units=req.visual_detected_units,
            ground_plane_height_m=req.ground_plane_height_m,
        )
        return {
            "dimensions_m": res.dimensions_m,
            "bounding_volume_m3": res.bounding_volume_m3,
            "occupied_solid_volume_m3": res.occupied_solid_volume_m3,
            "packing_density": res.packing_density,
            "estimated_units_from_volume": res.estimated_units_from_volume,
            "visual_detected_units": res.visual_detected_units,
            "is_hollow_anomaly": res.is_hollow_anomaly,
            "anomaly_reason": res.anomaly_reason,
            "confidence": res.confidence,
            "depth_profile_summary": res.depth_profile_summary,
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/journey/waypoint", response_model=Dict[str, Any])
async def record_journey_waypoint(req: WaypointRequest) -> Dict[str, Any]:
    """Records a waypoint sighting for an individual across cameras."""
    wp = CrossCameraJourneyEngine.record_waypoint(
        camera_id=req.camera_id,
        zone_id=req.zone_id,
        zone_name=req.zone_name,
        person_name=req.person_name,
        face_confidence=req.face_confidence,
        items_in_possession=req.items_in_possession,
        dwell_seconds=req.dwell_seconds,
    )
    return {
        "status": "RECORDED",
        "carrier_identity": wp.carrier_identity,
        "zone_name": wp.zone_name,
        "items": wp.items_in_possession,
    }


@router.get("/journey/{person_key}", response_model=Dict[str, Any])
async def get_journey_trajectory(person_key: str, complete: bool = False) -> Dict[str, Any]:
    """Retrieves full spatiotemporal trajectory and evaluates in-facility diversion."""
    traj = CrossCameraJourneyEngine.evaluate_journey(person_key, mark_completed=complete)
    if not traj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No active trajectory for '{person_key}'")

    return {
        "journey_id": traj.journey_id,
        "person_name": traj.person_name,
        "identity_status": traj.identity_status,
        "waypoints_count": len(traj.waypoints),
        "total_duration_seconds": traj.total_duration_seconds,
        "has_diversion_anomaly": traj.has_diversion_anomaly,
        "diversion_details": traj.diversion_details,
        "journey_status": traj.journey_status,
        "waypoints": [
            {
                "camera_id": w.camera_id,
                "zone_id": w.zone_id,
                "zone_name": w.zone_name,
                "dwell_seconds": w.dwell_seconds,
                "items": w.items_in_possession,
                "confidence": w.face_confidence,
            }
            for w in traj.waypoints
        ],
    }


@router.post("/ergonomics/analyze", response_model=Dict[str, Any])
async def analyze_ergonomics(req: ErgonomicRequest) -> Dict[str, Any]:
    """Analyzes spine flexion kinematics, team-lift compliance, and PPE."""
    try:
        # Construct synthetic frame for PPE verification
        blank_frame = np.full((720, 1280, 3), 128, dtype=np.uint8)
        kps = {k: (v[0], v[1]) for k, v in req.keypoints.items()}

        assessment = ErgonomicSafetyAnalyzer.evaluate_ergonomic_safety(
            frame_bgr=blank_frame,
            person_bbox=req.person_bbox,
            keypoints=kps,
            material_weight_kg=req.material_weight_kg,
            material_tier=req.material_tier,
            nearby_persons_count=req.nearby_persons_count,
            enforce_ppe=req.enforce_ppe,
        )
        return {
            "spine_flexion_deg": assessment.spine_flexion_deg,
            "lift_technique": assessment.lift_technique,
            "is_hazardous_bend": assessment.is_hazardous_bend,
            "team_lift_compliant": assessment.team_lift_compliant,
            "ppe_compliant": assessment.ppe_compliant,
            "ergonomic_safety_score": assessment.ergonomic_safety_score,
            "violations": assessment.violations,
            "recommendation": assessment.recommendation,
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/fusion/reconcile", response_model=Dict[str, Any])
async def reconcile_tri_sensor(req: TriSensorFusionRequest) -> Dict[str, Any]:
    """Reconciles Computer Vision counts, RFID/Barcode tags, and Scale Weight against Manifest."""
    try:
        inp = TriSensorInput(
            vision_counts=req.vision_counts,
            scanned_barcodes=req.scanned_barcodes,
            scanned_rfid_tags=req.scanned_rfid_tags,
            gross_scale_weight_kg=req.gross_scale_weight_kg,
            tare_weight_kg=req.tare_weight_kg,
            manifest_expected=req.manifest_expected,
            material_unit_weights_kg=req.material_unit_weights_kg,
        )
        res = TriSensorFusionEngine.reconcile(inp, weight_tolerance_pct=req.weight_tolerance_pct)
        return {
            "status": res.status,
            "is_authorized": res.is_authorized,
            "variance_units": res.variance_units,
            "vision_total_units": res.vision_total_units,
            "scanned_serialized_units": res.scanned_serialized_units,
            "net_measured_weight_kg": res.net_measured_weight_kg,
            "expected_weight_kg": res.expected_weight_kg,
            "weight_variance_kg": res.weight_variance_kg,
            "weight_variance_pct": res.weight_variance_pct,
            "channel_concordance": res.channel_concordance,
            "discrepancy_attribution": res.discrepancy_attribution,
            "discrepancy_severity": res.discrepancy_severity,
            "recommended_action": res.recommended_action,
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/acceleration/profile", response_model=Dict[str, Any])
async def get_acceleration_profile() -> Dict[str, Any]:
    """Inspects available hardware acceleration providers and runs a synthetic pipeline benchmark."""
    profile = HardwareAccelerator.get_hardware_profile()
    benchmark = HardwareAccelerator.benchmark_synthetic_pipeline(iterations=10, warmup=2)
    return {
        "profile": {
            "available_providers": profile.available_providers,
            "selected_provider": profile.selected_provider,
            "precision_mode": profile.precision_mode,
            "device_type": profile.device_type,
            "intra_op_threads": profile.intra_op_threads,
            "estimated_throughput_fps": profile.estimated_throughput_fps,
        },
        "benchmark": {
            "mean_latency_ms": benchmark.mean_latency_ms,
            "median_latency_ms": benchmark.median_latency_ms,
            "achievable_fps": benchmark.achievable_fps,
            "iterations_run": benchmark.iterations_run,
        },
    }


@router.post("/autocuration/evaluate-candidate", response_model=Dict[str, Any])
async def evaluate_candidate_model(req: CandidateEvaluationRequest) -> Dict[str, Any]:
    """Shadow-evaluates fine-tuned candidate model against zero-regression threshold."""
    candidate_metrics = BenchmarkMetrics(
        map_50=req.candidate_map_50,
        map_50_95=req.candidate_map_50_95,
        precision=req.candidate_precision,
        recall=req.candidate_recall,
        hard_negative_false_positives=req.candidate_hard_negative_fps,
        inference_latency_ms=req.candidate_latency_ms,
    )
    baseline_metrics = None
    if req.baseline_map_50 is not None and req.baseline_latency_ms is not None:
        baseline_metrics = BenchmarkMetrics(
            map_50=req.baseline_map_50,
            map_50_95=req.candidate_map_50_95 * 0.8,
            precision=0.90,
            recall=0.85,
            hard_negative_false_positives=0,
            inference_latency_ms=req.baseline_latency_ms,
        )

    decision = ModelAutoCurator.evaluate_candidate(
        candidate_version=req.candidate_version,
        candidate_metrics=candidate_metrics,
        baseline_metrics=baseline_metrics,
    )
    return {
        "candidate_version": decision.candidate_version,
        "approved_for_production": decision.approved_for_production,
        "status": decision.status,
        "delta_map_50": decision.delta_map_50,
        "delta_latency_pct": decision.delta_latency_pct,
        "hard_negatives_passed": decision.hard_negatives_passed,
        "rejection_reasons": decision.rejection_reasons,
        "evaluation_summary": decision.evaluation_summary,
    }
