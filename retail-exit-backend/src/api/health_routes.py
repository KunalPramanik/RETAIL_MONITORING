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
    """General health check endpoint for frontend status checks."""
    from src.core.config import settings
    return {"status": "HEALTHY", "version": settings.APP_VERSION, "service": settings.APP_NAME}
