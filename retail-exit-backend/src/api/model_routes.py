"""Model Registry, Shadow Deployment, and Retraining API Endpoints

Provides REST APIs for:
1. Model Registry: listing, registration, Step 5 promotion gates, and safe rollback (Part E.6).
2. Shadow Deployment: candidate model routing and real-time comparison telemetry.
3. Dynamic Class Configuration: zero-code class registration (Step 2).
4. Continuous Active Learning: candidate review and accuracy drift monitoring (Step 6).
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import os

from src.ml.model_registry import ModelRegistry, ModelMetrics
from src.ml.shadow_service import shadow_service
from src.ml.active_learning import active_learning_service, CANDIDATES_DIR
from src.ml.model_config import get_vision_config, reload_vision_config
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/ml", tags=["ML Model Lifecycle & Retraining"])


# ── Pydantic Request Models ──

class ModelMetricsInput(BaseModel):
    map_50: float = 0.0
    case_unit_recall: float = 0.0
    empty_scene_fp_rate: float = 0.0
    pairwise_precision: float = 0.0
    latency_ms: float = 0.0
    eval_dataset_size: int = 0
    evaluated_at: Optional[str] = None


class RegisterModelRequest(BaseModel):
    model_version: str = Field(...)
    model_name: str = Field(...)
    weights_path: str = Field(...)
    base_model: Optional[str] = "megvii-yolox-tiny"
    dataset_version: Optional[str] = "retail-v1.0"
    metrics: Optional[ModelMetricsInput] = None
    notes: Optional[str] = ""


class PromoteModelRequest(BaseModel):
    model_version: str = Field(...)
    bypass_gate: bool = False


class RollbackModelRequest(BaseModel):
    model_version: str = Field(...)


class ShadowConfigRequest(BaseModel):
    model_version: Optional[str] = None
    traffic_pct: float = Field(20.0, ge=0.0, le=100.0)


class RegisterClassRequest(BaseModel):
    class_id: int
    label: str
    category: str = Field("single_item")  # 'single_item', 'case', 'vehicle'


class CurateAnnotationRequest(BaseModel):
    candidate_id: str
    verified_boxes: List[Dict[str, Any]]
    notes: Optional[str] = ""


# ── Model Registry Endpoints ──

@router.get("/models")
async def list_models(_role: str = Depends(require_roles(["ADMIN", "SUPERVISOR", "VIEWER"]))):
    """Returns all registered vision models, active production, and shadow status."""
    registry = ModelRegistry.get_instance()
    return {
        "active_production_version": registry.active_production_version,
        "active_shadow_version": registry.active_shadow_version,
        "shadow_traffic_pct": registry.shadow_traffic_pct,
        "models": registry.list_models(),
    }


@router.post("/models/register")
async def register_model(
    req: RegisterModelRequest,
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Registers a newly trained model checkpoint as a candidate."""
    registry = ModelRegistry.get_instance()
    metrics = ModelMetrics(**req.metrics.model_dump()) if req.metrics else None
    mv = registry.register_model(
        model_version=req.model_version,
        model_name=req.model_name,
        weights_path=req.weights_path,
        base_model=req.base_model,
        dataset_version=req.dataset_version,
        metrics=metrics,
        notes=req.notes or "",
    )
    return {"success": True, "model": mv.model_version, "status": mv.status}


@router.post("/models/promote")
async def promote_model(
    req: PromoteModelRequest,
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Promotes a candidate model to production, enforcing Step 5 accuracy gates."""
    registry = ModelRegistry.get_instance()
    success, message = registry.promote_to_production(req.model_version, bypass_gate=req.bypass_gate)
    if not success:
        raise HTTPException(status_code=422, detail=message)
    return {"success": True, "message": message, "active_production_version": registry.active_production_version}


@router.post("/models/rollback")
async def rollback_model(
    req: RollbackModelRequest,
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Rolls back the active production model to a previously archived checkpoint."""
    registry = ModelRegistry.get_instance()
    success, message = registry.rollback_to(req.model_version)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "active_production_version": registry.active_production_version}


# ── Shadow Deployment Endpoints ──

@router.post("/models/shadow")
async def configure_shadow_mode(
    req: ShadowConfigRequest,
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Enables or disables candidate model shadow deployment (Part E.6)."""
    registry = ModelRegistry.get_instance()
    success, message = registry.set_shadow_mode(req.model_version, traffic_pct=req.traffic_pct)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {
        "success": True,
        "message": message,
        "active_shadow_version": registry.active_shadow_version,
        "shadow_traffic_pct": registry.shadow_traffic_pct,
    }


@router.get("/shadow/telemetry")
async def get_shadow_telemetry(_role: str = Depends(require_roles(["ADMIN", "SUPERVISOR", "VIEWER"]))):
    """Returns real-time side-by-side comparison logs between production and shadow models."""
    return {
        "active_shadow_version": ModelRegistry.get_instance().active_shadow_version,
        "telemetry": shadow_service.get_telemetry(),
    }


# ── Dynamic Class Configuration Endpoints ──

@router.get("/classes")
async def get_classes_config(_role: str = Depends(require_roles(["ADMIN", "SUPERVISOR", "VIEWER"]))):
    """Returns active class dictionary, category sets, and detection thresholds."""
    cfg = get_vision_config()
    return {
        "class_labels": cfg.class_labels,
        "case_classes": sorted(list(cfg.case_classes)),
        "vehicle_classes": sorted(list(cfg.vehicle_classes)),
        "single_item_classes": sorted(list(cfg.single_item_classes)),
        "thresholds": {
            "confidence_floor": cfg.confidence_floor,
            "person_conf_threshold": cfg.person_conf_threshold,
            "case_conf_threshold": cfg.case_conf_threshold,
            "vehicle_conf_threshold": cfg.vehicle_conf_threshold,
            "item_conf_threshold": cfg.item_conf_threshold,
            "nms_iou_threshold": cfg.nms_iou_threshold,
        },
        "pairwise_precision_groups": cfg.pairwise_precision_groups,
    }


@router.post("/classes")
async def register_dynamic_class(
    req: RegisterClassRequest,
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Dynamically registers or updates a class without hardcoded code modifications."""
    cfg = get_vision_config()
    cfg.register_class(class_id=req.class_id, label=req.label, category=req.category)
    cfg.save_to_file()
    return {
        "success": True,
        "class_id": req.class_id,
        "label": req.label,
        "category": req.category,
    }


# ── Continuous Active Learning Endpoints ──

@router.get("/active-learning/candidates")
async def list_active_learning_candidates(_role: str = Depends(require_roles(["ADMIN", "SUPERVISOR", "VIEWER"]))):
    """Lists pending low-confidence and flagged frames queued for human review."""
    candidates = active_learning_service.list_pending_candidates()
    return {"count": len(candidates), "candidates": candidates}


@router.get("/active-learning/image/{filename}")
async def get_candidate_image(filename: str):
    """Streams candidate image for human review interface."""
    safe_name = os.path.basename(filename)
    path = os.path.join(CANDIDATES_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/active-learning/curate")
async def curate_candidate(
    req: CurateAnnotationRequest,
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Submits verified bounding box labels to convert candidate into verified training sample."""
    success, msg = active_learning_service.submit_annotation(
        candidate_id=req.candidate_id,
        verified_boxes=req.verified_boxes,
        notes=req.notes or "",
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.get("/drift")
async def check_drift(_role: str = Depends(require_roles(["ADMIN", "SUPERVISOR", "VIEWER"]))):
    """Evaluates rolling detection confidence to detect real-world accuracy drift."""
    return active_learning_service.check_accuracy_drift()

