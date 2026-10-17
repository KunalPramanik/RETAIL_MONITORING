"""System Maintenance & Health Monitoring API Endpoints

Provides granular V8 observability metrics for streams, models, and databases.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from src.engine.stream_manager import CameraStreamManager
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/health", tags=["V8 System Observability"])

@router.get("/cameras")
async def get_camera_health(
    user=Depends(require_roles(["SUPER_ADMIN", "ADMIN", "MAINTENANCE", "VIEWER"]))
):
    """Retrieve dynamic health metrics for all active camera sessions."""
    health_report = {}
    manager = CameraStreamManager.get_instance()
    
    with manager.lock:
        sessions = list(manager.sessions.values())
        
    for session in sessions:
        health_report[session.camera_key] = {
            "status": session.compute_health_status(),
            "fps_observed": round(session.fps_observed, 2),
            "resolution": session.resolution,
            "codec": getattr(session, "codec", "UNKNOWN"),
            "reconnect_count": getattr(session, "reconnect_count", 0),
            "decode_failure_count": getattr(session, "decode_failure_count", 0),
            "is_connected": session.is_connected,
            "has_real_frame": session.has_real_frame
        }
        
    return {"status": "success", "cameras": health_report}

@router.get("")
async def get_system_health():
    """General health check endpoint running authentic SELECT 1 on database."""
    from src.core.config import settings
    from src.db.session import AsyncSessionLocal
    from src.db.models import Camera
    from sqlalchemy import select, text
    from fastapi.responses import JSONResponse
    from src.ml.level1_detection.vision_service import VisionInferenceService
    from src.ml.face_recognition.face_service import FaceRecognitionService
    from src.ml.acceleration import HardwareAccelerator
    from src.engine.camera_worker import camera_worker

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            res = await session.execute(
                select(Camera.status).where(Camera.removed_at.is_(None))
            )
            statuses = res.scalars().all()
            online_count = sum(1 for s in statuses if s == "ONLINE")
            degraded_count = sum(1 for s in statuses if s == "DEGRADED")
            offline_count = sum(1 for s in statuses if s == "OFFLINE")
            total_count = len(statuses)
    except Exception as db_err:
        return JSONResponse(
            status_code=503,
            content={
                "status": "UNHEALTHY",
                "service": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "database": "DISCONNECTED",
                "error": str(db_err),
            },
        )

    hw_prof = HardwareAccelerator.get_hardware_profile()
    yolox_loaded = VisionInferenceService._session is not None
    face_loaded = FaceRecognitionService._app is not None
    worker_running = getattr(camera_worker, "is_running", False)
    poll_sec = getattr(camera_worker, "poll_interval_sec", 0.5)

    return {
        "status": "HEALTHY",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "CONNECTED",
        "cameraFleet": {
            "online": online_count,
            "degraded": degraded_count,
            "offline": offline_count,
            "total": total_count,
        },
        "inferenceRuntime": {
            "yolox_loaded": yolox_loaded,
            "face_model_loaded": face_loaded,
            "provider": hw_prof.selected_provider,
        },
        "worker": {
            "camera_worker_running": worker_running,
            "poll_interval_sec": poll_sec,
        },
    }
