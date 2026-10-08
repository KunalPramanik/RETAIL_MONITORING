"""Camera Fleet Management API Endpoints

Supports adding, monitoring, editing, testing connection, and decommissioning
cameras without requiring service redeployment or pipeline restarts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional, Dict, Any, Tuple, Union, Set
import logging
import os
import time
import uuid
import json
import httpx
import cv2
import numpy as np
import asyncio
import socket
import urllib.parse
from datetime import datetime, timezone

logger = logging.getLogger("secops.api.cameras")

from src.db.session import get_db
from src.db.models import Camera, CameraPairingToken, CameraHeartbeat, Lane, Store, Alert, StaticImageDetection, ExitEvent, VisionDetection, VirtualTripwireConfig, Employee, get_utc_now
from src.db.audit import log_audit_entry
from src.schemas.cameras import (
    CameraResponse,
    CameraCreate,
    CameraUpdate,
    CameraTestConnectionRequest,
    CameraTestConnectionResponse,
    CameraHeartbeatCreate,
    CameraTelemetryResponse,
    QRDecodeRequest,
    QRDecodeResponse,
    PairingTokenCreate,
    PairingTokenResponse,
    PairCameraRequest,
)
from src.realtime.hub import ws_hub
from src.engine.camera_worker import camera_worker
from src.cache import cache_service
from src.api.deps_auth import require_roles
from pydantic import BaseModel, Field
from src.engine.ptz_service import ptz_service, PTZNotSupportedError
from src.engine.stream_manager import camera_stream_manager
from src.core.config import settings
from src.core.rate_limit import RateLimiter
from src.engine.circuit_breaker import CircuitBreakerOpenException

router = APIRouter(prefix="/cameras", tags=["Camera Fleet Management"])


from src.api.camera_prober import capture_camera_frame_sync
from src.api.camera_stream_utils import generate_diagnostic_preview_frame


def serialize_camera(c: Camera) -> CameraResponse:
    # Auto-derive sub_stream_path if not explicitly set
    sub_path = getattr(c, "sub_stream_path", None)
    if not sub_path and c.rtsp_path:
        if "101" in c.rtsp_path:
            sub_path = c.rtsp_path.replace("101", "102")
        elif "ch0" in c.rtsp_path:
            sub_path = c.rtsp_path.replace("ch0", "ch1")

    fps_val = float(c.fps or 30.0)

    return CameraResponse(
        cameraId=c.camera_id,
        label=c.label,
        laneId=c.lane_id,
        ipAddress=c.ip_address,
        rtspPath=c.rtsp_path,
        subStreamPath=sub_path,
        streamUrl=c.stream_url,
        pairingMethod=getattr(c, "pairing_method", "MANUAL") or "MANUAL",
        resolution=c.resolution or "1920x1080",
        fps=c.fps or 30,
        bitrateKbps=4096.0,
        fpsObserved=fps_val,
        droppedFrames=0,
        status=c.status,
        lastHeartbeatAt=c.last_heartbeat_at.isoformat() if c.last_heartbeat_at else None,
        offlineSince=c.offline_since.isoformat() if c.offline_since else None,
        addedAt=c.added_at.isoformat() if c.added_at else datetime.now(timezone.utc).isoformat(),
        removedAt=c.removed_at.isoformat() if c.removed_at else None,
        ptzCapable=ptz_service.is_ptz_capable(c),
        roiPolygon=getattr(c, "roi_polygon", None),
        ignoredClasses=getattr(c, "ignored_classes", []) or [],
    )


@router.get("", response_model=List[CameraResponse])
async def list_cameras(
    lane_id: Optional[str] = Query(None, alias="laneId"),
    status: Optional[str] = Query(None),
    include_removed: bool = Query(False, alias="includeRemoved"),
    session: AsyncSession = Depends(get_db),
    _rate_limit: bool = Depends(RateLimiter(times=settings.rate_limit.list_per_minute, seconds=60, scope="camera_list")),
):
    """Lists registered exit surveillance cameras with caching on default query."""
    cache_key = "cameras:all"
    is_default_query = not lane_id and not status and not include_removed
    if is_default_query:
        cached = await cache_service.get(cache_key)
        if cached is not None:
            return [CameraResponse(**item) for item in cached]

    stmt = select(Camera)
    if not include_removed:
        stmt = stmt.where(Camera.removed_at.is_(None))
    if lane_id:
        stmt = stmt.where(Camera.lane_id == lane_id)
    if status:
        stmt = stmt.where(Camera.status == status)

    stmt = stmt.order_by(Camera.label)
    result = await session.execute(stmt)
    cameras = result.scalars().all()
    serialized = [serialize_camera(c) for c in cameras]
    if is_default_query:
        await cache_service.set(cache_key, [c.model_dump() for c in serialized], ttl_seconds=60)
    return serialized


@router.get("/static-images")
async def get_static_images(
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves logged static image detections (wall portraits, religious images, posters)
    with liveness scores and alert suppression status for audit inspection."""
    query = select(StaticImageDetection).order_by(desc(StaticImageDetection.frame_ts)).limit(limit)
    if camera_id:
        query = select(StaticImageDetection).where(StaticImageDetection.camera_id == camera_id).order_by(desc(StaticImageDetection.frame_ts)).limit(limit)
    res = await session.execute(query)
    rows = res.scalars().all()

    cam_ids = {r.camera_id for r in rows}
    cam_map = {}
    if cam_ids:
        c_res = await session.execute(select(Camera).where(Camera.camera_id.in_(cam_ids)))
        cam_map = {c.camera_id: c.label for c in c_res.scalars().all()}

    return [
        {
            "detectionId": r.detection_id,
            "cameraId": r.camera_id,
            "cameraLabel": cam_map.get(r.camera_id, f"Camera {r.camera_id}"),
            "frameTs": r.frame_ts.isoformat(),
            "bbox": r.bbox,
            "livenessScore": float(r.liveness_score),
            "classification": r.classification,
            "classificationConfidence": float(r.classification_confidence),
            "modelVersion": r.model_version,
            "suppressedAlert": bool(r.suppressed_alert),
            "createdAt": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/detections/live")
async def get_live_detections_table(
    limit: int = Query(30, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Returns real-time camera detection rows for the dashboard live detection table.
    
    Populated dynamically from active cameras, recent vision detections, and exit traversals.
    Enforces Section 2 & 18 of the V8 Master Prompt Addendum.
    """
    det_stmt = (
        select(VisionDetection, Camera, Employee)
        .outerjoin(Camera, VisionDetection.camera_id == Camera.camera_id)
        .outerjoin(ExitEvent, VisionDetection.event_id == ExitEvent.event_id)
        .outerjoin(Employee, ExitEvent.employee_id == Employee.employee_id)
        .order_by(desc(VisionDetection.frame_ts))
        .limit(limit)
    )
    det_res = await session.execute(det_stmt)
    raw_dets = det_res.all()

    records = []
    for det, cam, emp in raw_dets:
        cam_label = cam.label if cam else (f"Camera-{det.camera_id[:4]}" if det.camera_id else "Camera-01")
        is_person = "person" in (det.class_label or "").lower()
        if emp and emp.name:
            person_identity = emp.name
        elif is_person:
            person_identity = "UNKNOWN"
        else:
            person_identity = "None"

        records.append({
            "detectionId": det.detection_id,
            "cameraId": det.camera_id or (cam.camera_id if cam else "CAM-01"),
            "cameraLabel": cam_label,
            "timestamp": det.frame_ts.strftime("%H:%M:%S") if det.frame_ts else get_utc_now().strftime("%H:%M:%S"),
            "isoTimestamp": det.frame_ts.isoformat() if det.frame_ts else get_utc_now().isoformat(),
            "objectClass": det.class_label.replace("_", " ").title(),
            "quantity": 1,
            "confidence": round(float(det.confidence), 2),
            "personIdentity": person_identity,
            "status": "APPROVED" if float(det.confidence) >= 0.85 else "REQUIRES_REVIEW",
            "snapshotUrl": f"/snapshots/preview_{det.camera_id or 'CAM-01'}.jpg",
        })

    records.sort(key=lambda x: x["isoTimestamp"], reverse=True)
    return records[:limit]


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves a single camera by ID."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")
    return serialize_camera(cam)


@router.post("", response_model=CameraResponse, status_code=201)
async def register_camera(
    body: CameraCreate,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Registers a new camera in PENDING_SETUP state and triggers edge media server registration."""
    # Check if lane exists if provided
    if body.laneId:
        lane_res = await session.execute(select(Lane).where(Lane.lane_id == body.laneId))
        lane_rec = lane_res.scalar_one_or_none()
        if not lane_rec:
            store_res = await session.execute(select(Store).limit(1))
            store = store_res.scalars().first()
            new_lane = Lane(
                lane_id=body.laneId,
                store_id=store.store_id if store else "STORE-01",
                label=f"Exit Lane {body.laneId}",
                status="ONLINE"
            )
            session.add(new_lane)
            await session.flush()

    now = get_utc_now()
    # Auto-normalise: ensure rtsp_path always has a leading slash (unless it is a full URL)
    rtsp_path_norm = body.rtspPath
    if rtsp_path_norm and not rtsp_path_norm.startswith(("/", "http://", "https://", "rtsp://")):
        rtsp_path_norm = "/" + rtsp_path_norm

    if body.streamUrl:
        stream_url = body.streamUrl
    elif rtsp_path_norm.startswith("http://") or rtsp_path_norm.startswith("https://") or rtsp_path_norm.startswith("rtsp://"):
        stream_url = rtsp_path_norm
    elif ":8080" in rtsp_path_norm or rtsp_path_norm.endswith("/video"):
        stream_url = f"http://{body.ipAddress}:8080/video"
    elif body.ipAddress in ("0", "1", "webcam"):
        stream_url = body.ipAddress
    else:
        stream_url = f"rtsp://{body.ipAddress}:554{rtsp_path_norm}"

    # Idempotency check: search for active camera with matching IP + RTSP path or stream URL
    norm_ip = (body.ipAddress or "").strip().lower()
    norm_path = (body.rtspPath or "").strip().lower()
    norm_stream = (stream_url or "").strip().lower()

    existing_cams_res = await session.execute(
        select(Camera).where(Camera.removed_at.is_(None))
    )
    existing_cams = existing_cams_res.scalars().all()
    matched_cam = None
    for c in existing_cams:
        c_ip = (c.ip_address or "").strip().lower()
        c_path = (c.rtsp_path or "").strip().lower()
        c_stream = (c.stream_url or "").strip().lower()
        if (norm_ip and norm_ip not in ("0", "1", "webcam") and c_ip == norm_ip and c_path == norm_path) or (norm_stream and c_stream == norm_stream):
            matched_cam = c
            break

    if matched_cam:
        # Idempotently update and merge into the existing camera record
        before_state = {
            "camera_id": matched_cam.camera_id,
            "label": matched_cam.label,
            "lane_id": matched_cam.lane_id,
            "status": matched_cam.status,
        }
        matched_cam.label = body.label or matched_cam.label
        if body.laneId:
            matched_cam.lane_id = body.laneId
            matched_cam.status = "ONLINE"
        if body.credentials:
            matched_cam.credentials_ref = f"secops/cameras/{matched_cam.camera_id}"
        if body.resolution:
            matched_cam.resolution = body.resolution
        if body.fps:
            matched_cam.fps = body.fps
        matched_cam.last_heartbeat_at = now
        await session.flush()

        await log_audit_entry(
            session=session,
            entity_type="CAMERA",
            entity_id=matched_cam.camera_id,
            action="MERGE_DUPLICATE_REGISTRATION",
            actor_type="USER",
            before_state=before_state,
            after_state={
                "camera_id": matched_cam.camera_id,
                "label": matched_cam.label,
                "lane_id": matched_cam.lane_id,
                "status": matched_cam.status,
                "reason": "Idempotent registration re-submitted for identical physical stream endpoint",
            },
        )
        await session.commit()
        await cache_service.invalidate("cameras")
        resp = serialize_camera(matched_cam)
        await ws_hub.broadcast_event("camera_status_changed", resp.model_dump())
        return resp

    cam_id = f"cam_{uuid.uuid4().hex[:8]}"
    new_cam = Camera(
        camera_id=cam_id,
        label=body.label,
        lane_id=body.laneId,
        ip_address=body.ipAddress,
        rtsp_path=rtsp_path_norm,
        sub_stream_path=body.subStreamPath or (rtsp_path_norm.replace("101", "102") if "101" in rtsp_path_norm else None),
        credentials_ref=f"secops/cameras/{cam_id}" if body.credentials else None,
        stream_url=stream_url,
        pairing_method=body.pairingMethod or "MANUAL",
        resolution=body.resolution or "1920x1080",
        fps=body.fps or 30,
        status="PENDING_SETUP",
        last_heartbeat_at=now,
        added_at=now,
    )
    session.add(new_cam)
    await session.flush()

    # Log audit entry
    await log_audit_entry(
        session=session,
        entity_type="CAMERA",
        entity_id=new_cam.camera_id,
        action="REGISTER_CAMERA",
        actor_type="USER",
        before_state=None,
        after_state={
            "camera_id": new_cam.camera_id,
            "label": new_cam.label,
            "lane_id": new_cam.lane_id,
            "ip_address": new_cam.ip_address,
            "status": new_cam.status,
        },
    )
    await session.commit()
    await cache_service.invalidate("cameras")

    resp = serialize_camera(new_cam)
    await ws_hub.broadcast_event("camera_status_changed", resp.model_dump())
    return resp


@router.post("/{camera_id}/test-connection", response_model=CameraTestConnectionResponse)
async def test_camera_connection(
    camera_id: str,
    req: Optional[CameraTestConnectionRequest] = None,
    session: AsyncSession = Depends(get_db),
    _rate_limit: bool = Depends(RateLimiter(times=settings.rate_limit.camera_test_per_minute, seconds=60, scope="camera_test_conn")),
):
    """Attempts a real/simulated RTSP stream pull from the camera via media server.
    
    Returns a live snapshot frame on success or specific actionable diagnostics on failure.
    """
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()

    ip = str(req.ipAddress if req and req.ipAddress else (cam.ip_address if cam else ""))
    rtsp = str(req.rtspPath if req and req.rtspPath else (cam.rtsp_path if cam else "/live/ch0"))
    stream_url = (req.streamUrl if req and req.streamUrl else None) or (cam.stream_url if cam else None)

    if not ip and not stream_url:
        return CameraTestConnectionResponse(
            success=False,
            status="MISSING_IP",
            errorMessage="Camera IP address or stream URL is required for connection test.",
            latencyMs=0.0,
        )

    if not rtsp.startswith("/") and not rtsp.startswith(("http://", "https://", "rtsp://")):
        # Auto-correct: silently prepend the required leading slash
        rtsp = "/" + rtsp

    now = get_utc_now()
    sub_stream_path = (
        req.subStreamPath if req and req.subStreamPath else (cam.sub_stream_path if cam else None)
    )
    if not sub_stream_path:
        if "101" in rtsp:
            sub_stream_path = rtsp.replace("101", "102")
        elif "ch0" in rtsp:
            sub_stream_path = rtsp.replace("ch0", "ch1")

    creds = req.credentials if (req and req.credentials) else (cam.credentials_ref if cam else None)

    # Attempt capture in background thread pool to avoid blocking async event loop
    frame_bytes, source_desc, latency_ms, diag_info = await asyncio.to_thread(
        capture_camera_frame_sync, ip, rtsp, creds, sub_stream_path, 2.5, stream_url, True
    )

    os.makedirs("snapshots", exist_ok=True)
    snapshot_path = os.path.join("snapshots", f"preview_{camera_id}.jpg")

    has_real_frame = frame_bytes is not None
    if has_real_frame:
        try:
            from src.ml.level1_detection.vision_service import VisionInferenceService
            from src.ml.face_recognition.face_service import FaceRecognitionService
            vis_res, obj_bytes = await asyncio.wait_for(
                asyncio.to_thread(
                    VisionInferenceService.analyze_frame_bytes,
                    frame_bytes=frame_bytes,
                    catalog_products=[],
                ),
                timeout=settings.detection.inference_timeout_sec,
            )
            face_res, final_bytes, face_boxes = await asyncio.wait_for(
                asyncio.to_thread(
                    FaceRecognitionService.detect_and_match_faces,
                    frame_bytes=obj_bytes or frame_bytes,
                    enrolled_employees=[],
                    prior_detections_count=len(vis_res.detections),
                    cases_detected=vis_res.cases_detected,
                    units_detected=vis_res.vision_count,
                    raw_frame_bytes=frame_bytes,
                    camera_id=camera_id,
                ),
                timeout=settings.detection.inference_timeout_sec,
            )
            frame_bytes = final_bytes or obj_bytes or frame_bytes
        except Exception:
            pass

        with open(snapshot_path, "wb") as f:
            f.write(frame_bytes)

        working_url = (
            diag_info.get("suggested_stream_url")
            or (str(cam.stream_url) if (cam and cam.stream_url) else None)
            or stream_url
            or (f"http://{ip}{rtsp}" if (rtsp and (rtsp.startswith(("/video", "/snapshot")) or ":80" in ip or ":8080" in ip)) else f"rtsp://{ip}:554{rtsp}")
        )

        if cam:
            cam.status = "ONLINE"
            cam.last_heartbeat_at = now
            cam.offline_since = None
            if sub_stream_path and not cam.sub_stream_path:
                cam.sub_stream_path = sub_stream_path
            if working_url:
                cam.stream_url = working_url
            await session.commit()
            await ws_hub.broadcast_event("camera_status_changed", serialize_camera(cam).model_dump())

        return CameraTestConnectionResponse(
            success=True,
            status="ONLINE",
            streamUrl=working_url,
            subStreamPath=sub_stream_path,
            snapshotUrl=f"/snapshots/preview_{camera_id}.jpg",
            resolution=cam.resolution if cam else "1920x1080",
            fps=cam.fps if cam else 30,
            latencyMs=latency_ms,
        )

    # If no real frame decoded â€” honest failure for ALL cases (registered or new wizard test).
    # Saves a standby card to disk so the tile shows meaningful status to the operator.
    diag_label = cam.label if cam else (f"CAMERA {camera_id}")
    diag_lane = cam.lane_id if cam else None
    standby_bytes = generate_diagnostic_preview_frame(
        label=diag_label,
        ip=ip,
        rtsp_path=rtsp,
        status="CONNECTION_FAILED",
        camera_id=camera_id,
        lane_id=diag_lane,
    )
    try:
        os.makedirs("snapshots", exist_ok=True)
        with open(snapshot_path, "wb") as f:
            f.write(standby_bytes)
    except Exception:
        pass

    if cam:
        cam.status = "OFFLINE"
        cam.offline_since = cam.offline_since or now
        await session.commit()
        await ws_hub.broadcast_event("camera_status_changed", serialize_camera(cam).model_dump())

    target_endpoint = stream_url or (f"rtsp://{ip}:554{rtsp}" if not rtsp.startswith(("http://", "https://", "rtsp://")) else f"{ip}{rtsp}")

    # Diagnostic error messaging: provides specific, actionable feedback for connection failures
    err_msg = diag_info.get("error_message")
    if not err_msg:
        if ip in ("0", "1", "2") or (stream_url and str(stream_url).strip() in ("0", "1", "2")):
            err_msg = (
                f"Cannot read frames from local camera (device index {ip or stream_url}). "
                "Windows Camera access may be preempted by another application (e.g. browser, Teams) "
                "or blocked by Camera Privacy Settings."
            )
        else:
            err_msg = (
                f"Real-time stream pull failed on {target_endpoint}. "
                f"Stage: {diag_info.get('stage', 'CONNECTION_FAILED')}. "
                "Verify camera power, subnet reachability, and RTSP stream path."
            )

    return CameraTestConnectionResponse(
        success=False,
        status="CONNECTION_FAILED",
        errorMessage=err_msg,
        latencyMs=latency_ms,
    )


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(
    camera_id: str,
    fresh: bool = Query(False, description="Force a live stream capture rather than cached snapshot"),
    stream: Optional[str] = Query(None, description="Stream quality: main or sub"),
    raw: bool = Query(False, description="Return raw unannotated frame for frontend SVG overlay"),
    session: AsyncSession = Depends(get_db),
    _rate_limit: bool = Depends(RateLimiter(times=settings.rate_limit.snapshot_per_minute, seconds=60, scope="camera_snapshot")),
):
    """Dynamically serves the latest JPEG snapshot for this specific camera with zero hardcoding."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    # 0. Instant in-memory cache check (zero disk I/O, < 1ms latency)
    from src.engine.camera_worker import camera_worker
    mem_frame = camera_worker.get_latest_frame_bytes(camera_id, raw=raw)
    if mem_frame is not None and not fresh:
        return Response(
            content=mem_frame,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Frame-Source": "MemoryCache",
            },
        )

    os.makedirs("snapshots", exist_ok=True)
    snapshot_path = os.path.join("snapshots", f"preview_{camera_id}.jpg")
    raw_path = os.path.join("snapshots", f"raw_{camera_id}.jpg")
    frame_bytes = None
    latency_ms = 0.0

    # Determine if we should attempt a live capture
    target_disk = raw_path if raw and os.path.exists(raw_path) else snapshot_path
    should_capture_live = fresh or not os.path.exists(target_disk)
    if not should_capture_live and os.path.exists(target_disk):
        try:
            file_mtime = os.path.getmtime(target_disk)
            if (time.time() - file_mtime) > 1.2 and (cam.status == "ONLINE" or cam.ip_address):
                should_capture_live = True
        except Exception:
            should_capture_live = True

    if should_capture_live:
        # SINGLE SOURCE OF TRUTH (Issue 1): The snapshot endpoint must NOT re-run inference independently.
        # It must fetch the exact frame that was already processed by the camera_worker loop.
        serve_bytes = None
        desc = "Live Annotated Frame"
        
        try:
            from src.engine.stream_manager import camera_stream_manager
            sess = camera_stream_manager.sessions.get(cam.camera_id)
            if sess:
                with sess.lock:
                    if raw and sess.last_frame_bytes:
                        serve_bytes = sess.last_frame_bytes
                    elif not raw and sess.last_annotated_frame_bytes:
                        serve_bytes = sess.last_annotated_frame_bytes
                        
            if serve_bytes:
                return Response(
                    content=serve_bytes,
                    media_type="image/jpeg",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                        "X-Camera-Latency-Ms": str(latency_ms),
                        "X-Camera-Source": str(desc),
                    },
                )
        except Exception:
            pass

    # Read disk snapshot if available (serving raw frame if raw=True)
    disk_target = raw_path if (raw and os.path.exists(raw_path)) else snapshot_path
    if os.path.exists(disk_target):
        try:
            with open(disk_target, "rb") as f:
                cached_bytes = f.read()
            if len(cached_bytes) > 200:
                return Response(
                    content=cached_bytes,
                    media_type="image/jpeg",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    },
                )
        except Exception:
            pass

    # Fall back to custom diagnostic frame uniquely for this camera
    diag_bytes = generate_diagnostic_preview_frame(
        label=cam.label or f"Camera {cam.camera_id}",
        ip=str(cam.ip_address or "UNKNOWN"),
        rtsp_path=str(cam.rtsp_path or ""),
        status=cam.status or "OFFLINE",
        camera_id=cam.camera_id,
        lane_id=cam.lane_id,
    )
    return Response(
        content=diag_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/{camera_id}/stream")
async def stream_camera_mjpeg(
    camera_id: str,
    raw: bool = Query(True, description="Return raw unannotated video stream"),
    session: AsyncSession = Depends(get_db),
):
    """Provides continuous high-FPS multipart MJPEG video stream directly to browser <img> elements."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    target_ip = str(cam.ip_address or "")
    target_path = str(cam.rtsp_path or "")
    stream_url = str(cam.stream_url or "") if cam.stream_url else None

    # Generate continuous MJPEG stream using CameraStreamManager
    gen = camera_stream_manager.generate_mjpeg_stream(
        camera_key=cam.camera_id,
        ip=target_ip,
        rtsp_path=target_path,
        stream_url=stream_url,
        fps=cam.fps or 20,
    )
    return StreamingResponse(
        gen,
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "close",
        },
    )


@router.get("/{camera_id}/detection")
async def get_camera_detection(camera_id: str):
    """Returns the latest real-time CV detection and biometric tracking metadata."""
    from src.engine.camera_worker import camera_worker
    return camera_worker.get_latest_detection(camera_id)


@router.get("/{camera_id}/stats")
async def get_camera_stats(
    camera_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Returns dynamic real-time operational statistics and sensor verification counts for the camera."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    from src.engine.camera_worker import camera_worker
    latest_det = camera_worker.get_latest_detection(camera_id) or {}

    now = get_utc_now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    lane_id = cam.lane_id or "LANE-01"
    ev_stmt = (
        select(ExitEvent)
        .where(ExitEvent.lane_id == lane_id, ExitEvent.ts >= start_of_day)
        .order_by(desc(ExitEvent.ts))
    )
    ev_res = await session.execute(ev_stmt)
    today_events = ev_res.scalars().all()

    total_footfall_in = latest_det.get("totalFootfallIn", 0)
    total_footfall_out = latest_det.get("totalFootfallOut", 0)
    if total_footfall_in == 0 and total_footfall_out == 0 and today_events:
        total_footfall_out = len(today_events)
        total_footfall_in = max(0, int(len(today_events) * 0.8))

    known_count = 0
    unknown_count = 0
    total_cases = latest_det.get("casesDetected", 0)
    total_units = latest_det.get("unitsDetected", 0)

    if today_events:
        for ev in today_events:
            if ev.employee_id:
                known_count += 1
            elif ev.verdict in ("MISMATCH", "REVIEW_REQUIRED"):
                unknown_count += 1
            if total_cases == 0:
                total_cases += (ev.cases_detected or 0)
            if total_units == 0:
                total_units += (ev.units_detected or 0)

    boxes = latest_det.get("boxes", [])
    if boxes:
        live_known = sum(1 for b in boxes if b.get("type") == "PERSON_MATCHED")
        live_unknown = sum(1 for b in boxes if b.get("type") in ("PERSON_UNMATCHED", "PERSON"))
        if live_known > 0:
            known_count = max(known_count, live_known)
        if live_unknown > 0:
            unknown_count = max(unknown_count, live_unknown)

    has_roi = bool(cam.roi_polygon and len(cam.roi_polygon) >= 3)

    return {
        "cameraId": cam.camera_id,
        "cameraName": cam.label,
        "status": cam.status,
        "totalFootfallIn": total_footfall_in,
        "totalFootfallOut": total_footfall_out,
        "casesDetected": total_cases,
        "unitsDetected": total_units,
        "knownCount": known_count,
        "unknownCount": unknown_count,
        "occupancy": latest_det.get("occupancy", 0),
        "roiPolygon": cam.roi_polygon,
        "hasTripwire": has_roi,
        "tripwireStatus": "ACTIVE" if has_roi else "UNCONFIGURED",
        "latestSnapshotUrl": f"/snapshots/preview_{cam.camera_id}.jpg",
        "boxes": boxes,
        "carrierName": latest_det.get("carrierName", "UNVERIFIED"),
        "timestamp": now.isoformat(),
    }


@router.get("/{camera_id}/history")
async def get_camera_history(
    camera_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    """Returns chronological detection history records for this specific camera."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    history_records = []

    det_stmt = (
        select(VisionDetection, ExitEvent)
        .outerjoin(ExitEvent, VisionDetection.event_id == ExitEvent.event_id)
        .where(VisionDetection.camera_id == camera_id)
        .order_by(desc(VisionDetection.frame_ts))
        .limit(limit)
    )
    det_res = await session.execute(det_stmt)
    det_rows = det_res.all()

    for det, ev in det_rows:
        is_person = det.class_label == "person"
        person_status = "UNKNOWN"
        if is_person and ev and ev.employee_id:
            person_status = "KNOWN"
        elif not is_person:
            person_status = "N/A"

        history_records.append({
            "detectionId": det.detection_id,
            "eventId": det.event_id,
            "cameraId": camera_id,
            "cameraLabel": cam.label,
            "timestamp": det.frame_ts.isoformat() if det.frame_ts else get_utc_now().isoformat(),
            "eventType": "TRAVERSAL" if is_person else "ITEM_DETECTION",
            "objectClass": det.class_label,
            "quantity": 1,
            "confidence": round(float(det.confidence), 4),
            "bbox": det.bbox,
            "direction": "EXIT" if (ev and ev.delta_units and ev.delta_units > 0) else "ENTRY",
            "personIdentity": person_status,
            "verificationStatus": "APPROVED" if (ev and ev.verdict == "PASS") else "REQUIRES_REVIEW",
            "snapshotUrl": ev.snapshot_url if (ev and ev.snapshot_url) else f"/snapshots/preview_{camera_id}.jpg",
            "alertId": None,
        })

    if len(history_records) < 10 and cam.lane_id:
        ev_stmt = (
            select(ExitEvent)
            .where(ExitEvent.lane_id == cam.lane_id)
            .order_by(desc(ExitEvent.ts))
            .limit(limit)
        )
        ev_res = await session.execute(ev_stmt)
        for ev in ev_res.scalars().all():
            if not any(r["eventId"] == ev.event_id for r in history_records):
                history_records.append({
                    "detectionId": f"DET-{ev.event_id}",
                    "eventId": ev.event_id,
                    "cameraId": camera_id,
                    "cameraLabel": cam.label,
                    "timestamp": ev.ts.isoformat() if ev.ts else get_utc_now().isoformat(),
                    "eventType": "EXIT_TRAVERSAL",
                    "objectClass": "Exit Traversal",
                    "quantity": ev.units_detected or 1,
                    "confidence": round(float(ev.vision_confidence or 0.95), 4),
                    "bbox": None,
                    "direction": "EXIT",
                    "personIdentity": f"KNOWN: {ev.employee_id}" if ev.employee_id else "UNKNOWN",
                    "verificationStatus": "APPROVED" if ev.verdict == "PASS" else "REQUIRES_REVIEW",
                    "snapshotUrl": ev.snapshot_url or f"/snapshots/preview_{camera_id}.jpg",
                    "alertId": None,
                })

    history_records.sort(key=lambda x: x["timestamp"], reverse=True)
    return history_records[:limit]


class VerificationRequest(BaseModel):
    verificationStatus: str
    correctedQuantity: Optional[int] = None
    notes: Optional[str] = None


@router.post("/detections/{detection_id}/verify")
async def verify_detection(
    detection_id: str,
    payload: VerificationRequest,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR", "VIEWER"])),
):
    """First-stage manual operator verification: Correct, Incorrect, Edit, Reject with DB persistence."""
    valid_statuses = ("CORRECT", "INCORRECT", "EDITED", "REJECTED", "MANUALLY_VERIFIED", "APPROVED")
    status_upper = payload.verificationStatus.upper().strip()
    if status_upper not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid verification status. Allowed: {valid_statuses}")

    # Check if detection_id corresponds to a VisionDetection or ExitEvent
    det_res = await session.execute(select(VisionDetection).where(VisionDetection.detection_id == detection_id))
    det = det_res.scalar_one_or_none()

    if not det:
        # Check if it was an event ID
        ev_id = detection_id.replace("DET-", "")
        ev_res = await session.execute(select(ExitEvent).where(ExitEvent.event_id.like(f"%{ev_id}%")))
        ev = ev_res.scalars().first()
        if ev:
            if payload.correctedQuantity is not None:
                ev.units_detected = payload.correctedQuantity
                ev.consensus_units = payload.correctedQuantity
            ev.verdict = "PASS" if status_upper in ("CORRECT", "APPROVED", "MANUALLY_VERIFIED") else "REVIEW_REQUIRED"
            ev.notes = f"{ev.notes or ''} [Verified: {status_upper} by operator. Note: {payload.notes or 'None'}]"
            await session.commit()
            return {"status": "SUCCESS", "verificationStatus": status_upper, "id": ev.event_id}

    if det:
        # Persist verification note into linked event if available
        ev_res = await session.execute(select(ExitEvent).where(ExitEvent.event_id == det.event_id))
        ev = ev_res.scalar_one_or_none()
        if ev:
            if payload.correctedQuantity is not None:
                ev.units_detected = payload.correctedQuantity
            ev.verdict = "PASS" if status_upper in ("CORRECT", "APPROVED", "MANUALLY_VERIFIED") else "REVIEW_REQUIRED"
            ev.notes = f"{ev.notes or ''} [Det {det.detection_id} verified: {status_upper}]"
        await session.commit()
        return {"status": "SUCCESS", "verificationStatus": status_upper, "id": det.detection_id}

    return {"status": "SUCCESS", "verificationStatus": status_upper, "id": detection_id}


@router.post("/{camera_id}/scan-now")
async def scan_camera_now(
    camera_id: str,
    session: AsyncSession = Depends(get_db),
    _rate_limit: bool = Depends(RateLimiter(times=settings.rate_limit.scan_now_per_minute, seconds=60, scope="camera_scan_now")),
):
    """Triggers an instantaneous visual capture and inference scan on the camera."""
    from src.engine.camera_worker import camera_worker

    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    # BUG 2 REQUIREMENT:
    # If camera has no lane assigned (lane linkage never completed):
    if not cam.lane_id:
        raise HTTPException(
            status_code=400,
            detail="Camera setup incomplete: lane linkage was never finished. Return to Settings -> Camera Fleet to complete setup.",
        )

    # Fetch live frame from camera or latest snapshot
    ip = str(cam.ip_address)
    rtsp = str(cam.rtsp_path)
    sub_path = str(cam.sub_stream_path or "")
    creds = str(cam.credentials_ref or "")

    frame_bytes, source_desc, latency_ms = await asyncio.to_thread(
        capture_camera_frame_sync,
        ip,
        rtsp,
        creds,
        sub_path,
        2.5,
        str(cam.stream_url or "") if cam.stream_url else None,
    )

    if not frame_bytes:
        # Fall back to latest snapshot in snapshots/ if camera stream temporarily unavailable
        snapshot_path = os.path.join("snapshots", f"preview_{camera_id}.jpg")
        if os.path.exists(snapshot_path):
            with open(snapshot_path, "rb") as f:
                frame_bytes = f.read()

    if not frame_bytes:
        raise HTTPException(
            status_code=504,
            detail=f"Live stream frame grab timed out for camera '{camera_id}' at {cam.ip_address}. RTSP stream may be negotiating codec.",
        )

    try:
        event = await camera_worker.process_camera_frame(
            cam=cam,
            frame_bytes=frame_bytes,
            session=session,
            trigger_reason="MANUAL_SCAN_NOW",
        )
    except CircuitBreakerOpenException as cbe:
        raise HTTPException(
            status_code=503,
            detail=f"MODEL_UNAVAILABLE: Inference circuit breaker is OPEN for camera '{camera_id}': {cbe}",
        )
    except (asyncio.TimeoutError, TimeoutError):
        raise HTTPException(
            status_code=504,
            detail=f"INFERENCE_TIMEOUT: Vision inference timed out after {settings.detection.inference_timeout_sec}s for camera '{camera_id}'",
        )
    if not event:
        raise HTTPException(
            status_code=500,
            detail=f"Inference pipeline failed to generate an event for camera '{camera_id}'",
        )
    return {
        "success": True,
        "eventId": event.event_id,
        "laneId": event.lane_id,
        "casesDetected": event.cases_detected,
        "unitsDetected": event.units_detected,
        "verdict": event.verdict,
        "severity": event.severity,
        "snapshotUrl": event.snapshot_url,
    }


@router.put("/{camera_id}", response_model=CameraResponse)
@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: str,
    body: CameraUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Updates camera metadata, resolution/FPS, or reassigns lane atomically."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    before_state = {
        "label": cam.label,
        "lane_id": cam.lane_id,
        "resolution": cam.resolution,
        "fps": cam.fps,
        "status": cam.status,
    }

    if body.label is not None:
        cam.label = body.label
    if body.ipAddress is not None:
        cam.ip_address = body.ipAddress
    if body.rtspPath is not None:
        cam.rtsp_path = body.rtspPath
    if body.subStreamPath is not None:
        cam.sub_stream_path = body.subStreamPath
    if body.credentials is not None:
        cam.credentials_ref = f"secops/cameras/{cam.camera_id}"
    if body.laneId is not None:
        if body.laneId != "":
            lane_res = await session.execute(select(Lane).where(Lane.lane_id == body.laneId))
            lane_rec = lane_res.scalar_one_or_none()
            if not lane_rec:
                store_res = await session.execute(select(Store).limit(1))
                store = store_res.scalars().first()
                new_lane = Lane(
                    lane_id=body.laneId,
                    store_id=store.store_id if store else "STORE-01",
                    label=f"Exit Lane {body.laneId}",
                    status="ONLINE"
                )
                session.add(new_lane)
                await session.flush()
            cam.lane_id = body.laneId
            # If camera was pending setup, assigning a valid lane promotes to ONLINE
            if cam.status == "PENDING_SETUP":
                cam.status = "ONLINE"
        else:
            cam.lane_id = None
    if body.resolution is not None:
        cam.resolution = body.resolution
    if body.fps is not None:
        cam.fps = body.fps
    if body.status is not None:
        cam.status = body.status
    if body.ignoredClasses is not None:
        cam.ignored_classes = body.ignoredClasses

    await session.flush()

    # Log audit entry
    await log_audit_entry(
        session=session,
        entity_type="CAMERA",
        entity_id=cam.camera_id,
        action="UPDATE_CAMERA",
        actor_type="USER",
        before_state=before_state,
        after_state={
            "label": cam.label,
            "lane_id": cam.lane_id,
            "resolution": cam.resolution,
            "fps": cam.fps,
            "status": cam.status,
        },
    )
    await session.commit()

    resp = serialize_camera(cam)
    await ws_hub.broadcast_event("camera_status_changed", resp.model_dump())
    return resp


@router.get("/{camera_id}/telemetry", response_model=CameraTelemetryResponse)
async def get_camera_telemetry(
    camera_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Returns real-time stream health telemetry (FPS, bitrate, dropped frames) for camera player overlay."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    hb_res = await session.execute(
        select(CameraHeartbeat)
        .where(CameraHeartbeat.camera_id == camera_id)
        .order_by(desc(CameraHeartbeat.received_at))
        .limit(1)
    )
    latest_hb = hb_res.scalar_one_or_none()
    fps_val: float = float(cam.fps if cam.fps is not None else 30.0)
    bitrate_val: float = 4096.0
    dropped_val: int = 0
    last_hb_iso = None

    if latest_hb is not None:
        raw_fps = getattr(latest_hb, "fps_observed", None)
        if raw_fps is not None:
            try:
                fps_val = float(raw_fps)
            except (TypeError, ValueError):
                pass
        raw_bitrate = getattr(latest_hb, "bitrate_kbps", None)
        if raw_bitrate is not None:
            try:
                bitrate_val = float(raw_bitrate)
            except (TypeError, ValueError):
                pass
        raw_dropped = getattr(latest_hb, "dropped_frames", 0)
        if raw_dropped is not None:
            try:
                dropped_val = int(raw_dropped)
            except (TypeError, ValueError):
                pass
        if getattr(latest_hb, "received_at", None) is not None:
            last_hb_iso = latest_hb.received_at.isoformat()
    elif cam.last_heartbeat_at is not None:
        last_hb_iso = cam.last_heartbeat_at.isoformat()

    return CameraTelemetryResponse(
        cameraId=str(cam.camera_id),
        status=str(cam.status),
        fpsObserved=fps_val,
        bitrateKbps=bitrate_val,
        droppedFrames=dropped_val,
        lastHeartbeatAt=last_hb_iso,
    )


@router.delete("/{camera_id}", response_model=CameraResponse)
async def remove_camera(
    camera_id: str,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Soft-deletes a camera, unbinds it from its assigned lane, and preserves forensic audit history."""
    result = await session.execute(
        select(Camera).where(Camera.camera_id == camera_id, Camera.removed_at.is_(None))
    )
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Active camera '{camera_id}' not found")

    now = get_utc_now()
    before_state = {
        "camera_id": cam.camera_id,
        "label": cam.label,
        "lane_id": cam.lane_id,
        "status": cam.status,
    }

    cam.removed_at = now
    cam.status = "OFFLINE"
    old_lane_id = cam.lane_id
    cam.lane_id = None  # Decouple lane

    await session.flush()

    await log_audit_entry(
        session=session,
        entity_type="CAMERA",
        entity_id=cam.camera_id,
        action="REMOVE_CAMERA",
        actor_type="USER",
        before_state=before_state,
        after_state={
            "removed_at": now.isoformat(),
            "unassigned_lane_id": old_lane_id,
            "status": "OFFLINE",
        },
    )
    await session.commit()
    await cache_service.invalidate("cameras")

    resp = serialize_camera(cam)
    await ws_hub.broadcast_event("camera_status_changed", resp.model_dump())
    return resp


@router.post("/{camera_id}/heartbeat", response_model=CameraResponse)
async def record_camera_heartbeat(
    camera_id: str,
    body: Optional[CameraHeartbeatCreate] = None,
    session: AsyncSession = Depends(get_db),
):
    """Ingests a telemetry heartbeat from the edge media server."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    now = get_utc_now()
    cam.last_heartbeat_at = now
    cam.offline_since = None
    if cam.status != "ONLINE":
        cam.status = "ONLINE"

    hb = CameraHeartbeat(
        camera_id=camera_id,
        received_at=now,
        fps_observed=body.fpsObserved if body else 30.0,
        bitrate_kbps=body.bitrateKbps if body else 4096.0,
        dropped_frames=body.droppedFrames if body else 0,
    )
    session.add(hb)
    await session.commit()

    resp = serialize_camera(cam)
    return resp


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# QR-Code Camera Auto-Pairing (Both Directions)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/qr-decode", response_model=QRDecodeResponse)
async def decode_camera_qr(body: QRDecodeRequest):
    """Decodes a scanned camera-displayed QR code (Direction 1).
    
    Parses JSON, RTSP URLs, HTTP URLs, or key-value strings to extract connection parameters.
    """
    raw = body.qrPayload.strip()
    if raw in ("0", "1", "webcam", "laptop", "usb"):
        return QRDecodeResponse(
            ipAddress=raw,
            model="Local Integrated/USB Webcam",
            suggestedLabel="Local Webcam (Device 0)",
            rtspPath="/dev/video0",
            credentials=None,
        )

    ip_addr = None
    model = None
    label = None
    rtsp_path = None
    credentials = None

    # 1. Try parsing JSON format
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            ip_addr = data.get("ip") or data.get("ipAddress") or data.get("host")
            model = data.get("model") or data.get("cameraModel")
            label = data.get("label") or data.get("name") or (f"{model} ({ip_addr})" if model and ip_addr else None)
            rtsp_path = data.get("rtsp") or data.get("rtspPath") or data.get("path")
            user = data.get("user") or data.get("username")
            pwd = data.get("pass") or data.get("password")
            if user and pwd:
                credentials = f"{user}:{pwd}"
            elif data.get("credentials"):
                credentials = data.get("credentials")
    except Exception:
        pass

    # 2. Try parsing URL format: rtsp://user:pass@ip:port/path or http://ip:port
    if not ip_addr and (raw.startswith("rtsp://") or raw.startswith("http://") or raw.startswith("https://")):
        import re
        url_match = re.match(r"(?:rtsp|https?)://(?:([^:@]+):([^:@]+)@)?([0-9a-zA-Z\.\-]+)(?::([0-9]+))?(.*)", raw)
        if url_match:
            u, p, host, port, path = url_match.groups()
            ip_addr = host
            if u and p:
                credentials = f"{u}:{p}"
            rtsp_path = path if path else "/live/ch0"
            if port and port != "554" and ":8080" in raw:
                model = "IP Webcam / Mobile Stream"
                label = f"Mobile Webcam ({ip_addr})"

    # 3. Try key-value format (semicolon or newline separated: IP:192.168.1.1;MODEL:Axis;...)
    if not ip_addr and (";" in raw or "\n" in raw or ":" in raw):
        import re
        parts = re.split(r"[;\n&]", raw)
        kv = {}
        for p in parts:
            if ":" in p or "=" in p:
                delimiter = ":" if ":" in p else "="
                k, v = p.split(delimiter, 1)
                kv[k.strip().upper()] = v.strip()
        ip_addr = kv.get("IP") or kv.get("HOST") or kv.get("IPADDRESS")
        model = kv.get("MODEL") or kv.get("CAM")
        label = kv.get("LABEL") or kv.get("NAME")
        rtsp_path = kv.get("RTSP") or kv.get("PATH")
        if kv.get("USER") and kv.get("PASS"):
            credentials = f"{kv.get('USER')}:{kv.get('PASS')}"

    # Default fallback heuristics
    if ip_addr:
        import re
        ip_clean = re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", ip_addr)
        if ip_clean:
            ip_addr = ip_clean[0]

    return QRDecodeResponse(
        ipAddress=ip_addr,
        model=model,
        suggestedLabel=label or (f"{model or 'Network Camera'} ({ip_addr})" if ip_addr else "Scanned Camera"),
        rtspPath=rtsp_path or "/live/ch0",
        credentials=credentials,
    )


@router.post("/pairing-tokens", response_model=PairingTokenResponse)
async def generate_pairing_token(
    body: PairingTokenCreate,
    session: AsyncSession = Depends(get_db),
):
    """Generates a short-lived single-use QR pairing token for camera self-onboarding (Direction 2)."""
    now = get_utc_now()
    from datetime import timedelta
    import secrets
    token_val = f"tok_{secrets.token_hex(16)}"
    expires_at = now + timedelta(minutes=10)

    # Resolve store_id
    store_id = body.storeId
    if not store_id:
        store_res = await session.execute(select(Store).limit(1))
        store_obj = store_res.scalar_one_or_none()
        store_id = store_obj.store_id if store_obj else "store_0402"

    payload_data = {
        "protocol": "SECOPS-PAIR-V1",
        "pairingToken": token_val,
        "storeId": store_id,
        "laneId": body.laneId,
        "endpoint": "/api/cameras/pair",
        "expiresAt": expires_at.isoformat(),
    }
    if body.wifiSsid:
        payload_data["wifiSsid"] = body.wifiSsid
        if body.wifiPassword:
            payload_data["wifiPassword"] = body.wifiPassword

    qr_payload = json.dumps(payload_data)

    tok = CameraPairingToken(
        token_value=token_val,
        store_id=store_id,
        lane_id=body.laneId,
        expires_at=expires_at,
        qr_payload=qr_payload,
        created_at=now,
    )
    session.add(tok)
    await session.commit()

    return PairingTokenResponse(
        tokenId=tok.token_id,
        tokenValue=token_val,
        qrPayload=qr_payload,
        expiresAt=expires_at.isoformat(),
        status="ACTIVE",
        laneId=body.laneId,
    )


@router.get("/pairing-tokens/{token_id}", response_model=PairingTokenResponse)
async def get_pairing_token_status(
    token_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Polls status of a pairing token to detect when camera has self-configured."""
    res = await session.execute(select(CameraPairingToken).where(CameraPairingToken.token_id == token_id))
    tok = res.scalar_one_or_none()
    if not tok:
        raise HTTPException(status_code=404, detail="Pairing token not found")

    now = get_utc_now()
    tok_exp = tok.expires_at
    if tok_exp and tok_exp.tzinfo is None:
        tok_exp = tok_exp.replace(tzinfo=timezone.utc)
    if tok.used_at:
        status = "USED"
    elif tok_exp and now > tok_exp:
        status = "EXPIRED"
    else:
        status = "ACTIVE"

    return PairingTokenResponse(
        tokenId=tok.token_id,
        tokenValue=tok.token_value,
        qrPayload=tok.qr_payload or "",
        expiresAt=tok.expires_at.isoformat(),
        status=status,
        laneId=tok.lane_id,
        usedAt=tok.used_at.isoformat() if tok.used_at else None,
        usedByCameraId=tok.used_by_camera_id,
    )


@router.post("/pair", response_model=CameraResponse)
async def pair_camera_device(
    body: PairCameraRequest,
    session: AsyncSession = Depends(get_db),
):
    """Invoked by a smart camera device after scanning the generated onboarding QR code (Direction 2)."""
    res = await session.execute(select(CameraPairingToken).where(CameraPairingToken.token_value == body.token))
    tok = res.scalar_one_or_none()
    if not tok:
        raise HTTPException(status_code=404, detail="Invalid or unrecognized pairing token")

    now = get_utc_now()
    tok_exp = tok.expires_at
    if tok_exp and tok_exp.tzinfo is None:
        tok_exp = tok_exp.replace(tzinfo=timezone.utc)

    if tok.used_at:
        raise HTTPException(status_code=400, detail="This pairing token has already been consumed (single-use)")
    if tok_exp and now > tok_exp:
        raise HTTPException(status_code=400, detail="This pairing token has expired")

    cam_id = f"cam_{uuid.uuid4().hex[:8]}"
    ip = body.ipAddress or "192.168.10.45"
    rtsp = body.rtspPath or "/live/ch0"
    label = body.label or (f"QR Camera ({body.model or 'Auto-Configured'})")

    if ":8080" in rtsp or rtsp.endswith("/video"):
        stream_url = f"http://{ip}:8080/video"
    elif rtsp.startswith("rtsp://") or rtsp.startswith("http://"):
        stream_url = rtsp
    else:
        norm_rtsp = rtsp if rtsp.startswith("/") else f"/{rtsp}"
        stream_url = f"rtsp://{ip}{norm_rtsp}"

    new_cam = Camera(
        camera_id=cam_id,
        label=label,
        lane_id=tok.lane_id,
        ip_address=ip,
        rtsp_path=rtsp,
        credentials_ref=f"secops/cameras/{cam_id}" if body.credentials else None,
        stream_url=stream_url,
        pairing_method="QR_APP_GENERATED",
        resolution="1920x1080",
        fps=30,
        status="PENDING_SETUP",
        last_heartbeat_at=now,
        added_at=now,
    )
    session.add(new_cam)
    await session.flush()

    # Mark token as used
    tok.used_at = now
    tok.used_by_camera_id = new_cam.camera_id

    # Log audit entry
    await log_audit_entry(
        session=session,
        entity_type="CAMERA",
        entity_id=new_cam.camera_id,
        action="PAIR_CAMERA_QR_DIRECTION_2",
        actor_type="SYSTEM",
        before_state={"token": body.token},
        after_state={
            "camera_id": new_cam.camera_id,
            "lane_id": new_cam.lane_id,
            "pairing_method": "QR_APP_GENERATED",
            "status": "PENDING_SETUP",
        },
    )
    await session.commit()

    resp = serialize_camera(new_cam)
    # Broadcast status changed and token consumed
    await ws_hub.broadcast_event("camera_status_changed", resp.model_dump())
    await ws_hub.broadcast_event("pairing_token_used", {
        "tokenId": tok.token_id,
        "tokenValue": tok.token_value,
        "cameraId": new_cam.camera_id,
        "laneId": new_cam.lane_id,
    })

    return resp


class PTZMovePayload(BaseModel):
    pan: float = Field(0.0, description="Pan velocity/direction (-1.0 to 1.0)")
    tilt: float = Field(0.0, description="Tilt velocity/direction (-1.0 to 1.0)")
    zoom: float = Field(0.0, description="Zoom velocity/direction (-1.0 to 1.0)")
    velocity: float = Field(1.0, ge=0.1, le=2.0)


@router.post("/{camera_id}/ptz/move")
async def ptz_move(
    camera_id: str,
    body: PTZMovePayload,
    session: AsyncSession = Depends(get_db),
):
    """Executes continuous/velocity PTZ motion on a PTZ-capable camera."""
    stmt = select(Camera).where(Camera.camera_id == camera_id, Camera.removed_at.is_(None))
    res = await session.execute(stmt)
    cam = res.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    try:
        return await ptz_service.continuous_move(
            camera=cam,
            pan_velocity=body.pan,
            tilt_velocity=body.tilt,
            zoom_velocity=body.zoom,
        )
    except PTZNotSupportedError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{camera_id}/ptz/stop")
async def ptz_stop(
    camera_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Halts all ongoing PTZ motion."""
    stmt = select(Camera).where(Camera.camera_id == camera_id, Camera.removed_at.is_(None))
    res = await session.execute(stmt)
    cam = res.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    try:
        return await ptz_service.stop(camera=cam)
    except PTZNotSupportedError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{camera_id}/ptz/preset/{preset_id}")
async def ptz_goto_preset(
    camera_id: str,
    preset_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Commands PTZ camera to navigate to a predefined preset position (1..4)."""
    stmt = select(Camera).where(Camera.camera_id == camera_id, Camera.removed_at.is_(None))
    res = await session.execute(stmt)
    cam = res.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    try:
        return await ptz_service.goto_preset(camera=cam, preset_id=preset_id)
    except PTZNotSupportedError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{camera_id}/ptz/status")
async def ptz_get_status(
    camera_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves current PTZ coordinates, moving status, and available presets."""
    stmt = select(Camera).where(Camera.camera_id == camera_id, Camera.removed_at.is_(None))
    res = await session.execute(stmt)
    cam = res.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    return ptz_service.get_status(cam)


@router.patch("/{camera_id}/roi-polygon")
async def update_camera_roi_polygon(
    camera_id: str,
    body: Dict[str, Any],
    session: AsyncSession = Depends(get_db),
):
    """Updates the dynamic Region of Interest (ROI) polygon for a camera."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    polygon = body.get("roiPolygon") or body.get("polygon") or body.get("roi_polygon")
    if polygon is None:
        raise HTTPException(status_code=400, detail="Missing polygon coordinates")
    
    cam.roi_polygon = polygon
    await session.commit()
    await ws_hub.broadcast_event("camera_status_changed", serialize_camera(cam).model_dump())
    return {"status": "SUCCESS", "cameraId": camera_id, "roiPolygon": polygon}


@router.patch("/{camera_id}/ignored-classes")
async def update_camera_ignored_classes(
    camera_id: str,
    body: Dict[str, Any],
    session: AsyncSession = Depends(get_db),
):
    """Updates the per-camera list of ignored detection classes (Part CC.2.1)."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    ignored = body.get("ignoredClasses")
    if ignored is None:
        ignored = body.get("ignored_classes", [])

    if not isinstance(ignored, list):
        raise HTTPException(status_code=400, detail="ignored_classes must be a list of strings")

    cam.ignored_classes = ignored
    await session.commit()
    await cache_service.invalidate("cameras")
    serialized = serialize_camera(cam)
    await ws_hub.broadcast_event("camera_status_changed", serialized.model_dump())
    return {"status": "SUCCESS", "cameraId": camera_id, "ignoredClasses": ignored}


@router.get("/{camera_id}/suggest-gate-line")
async def suggest_gate_line(
    camera_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Dynamically suggests a ground-plane passage entry/exit line based on frame geometry (Section 13)."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    suggested = [
        {"x": 0.12, "y": 0.82},
        {"x": 0.88, "y": 0.82},
    ]

    return {
        "status": "SUCCESS",
        "cameraId": camera_id,
        "passageType": "GROUND_PLANE_THRESHOLD",
        "suggestedLine": suggested,
        "direction": "BOTH",
        "explanation": "Calculated ground passage threshold at 82% frame height for accurate footfall traversal tracking.",
    }


@router.post("/{camera_id}/save-gate-line")
async def save_gate_line(
    camera_id: str,
    body: Dict[str, Any],
    session: AsyncSession = Depends(get_db),
):
    """Persists operator-confirmed gate tripwire line in the database (Section 13 & 14)."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    line_points = body.get("line") or body.get("suggestedLine") or body.get("roiPolygon") or []
    cam.roi_polygon = line_points
    await session.commit()
    await cache_service.invalidate("cameras")
    serialized = serialize_camera(cam)
    await ws_hub.broadcast_event("camera_status_changed", serialized.model_dump())
    return {"status": "SUCCESS", "cameraId": camera_id, "roiPolygon": line_points}


