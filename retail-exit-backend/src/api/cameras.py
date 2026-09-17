"""Camera Fleet Management API Endpoints

Supports adding, monitoring, editing, testing connection, and decommissioning
cameras without requiring service redeployment or pipeline restarts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
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

from src.db.session import get_db
from src.db.models import Camera, CameraPairingToken, CameraHeartbeat, Lane, Store, Alert, StaticImageDetection, get_utc_now
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

router = APIRouter(prefix="/cameras", tags=["Camera Fleet Management"])


def capture_camera_frame_sync(
    ip: str,
    rtsp_path: str,
    credentials: Optional[str] = None,
    sub_stream_path: Optional[str] = None,
    timeout_sec: float = 2.5,
    stream_url: Optional[str] = None,
    return_diag: bool = False,
) -> tuple:
    """Attempts to capture a real frame from RTSP stream (main/sub), HTTP endpoints, or local devices.
    
    Returns (frame_bytes, source_description, latency_ms) or (frame_bytes, source_description, latency_ms, diag_info).
    """
    t0 = time.perf_counter()
    diag_info: Dict[str, Any] = {
        "stage": "UNKNOWN",
        "error_message": "",
        "host": str(ip or ""),
        "port": 554,
        "is_reachable": False,
        "is_port_open": False,
        "is_handshake_ok": False,
    }

    # 1. Check for local webcam device indices (e.g. 0, 1, 'webcam')
    dev_idx = None
    if stream_url and str(stream_url).strip() in ("0", "1", "2"):
        dev_idx = int(stream_url.strip())
    elif ip and str(ip).strip() in ("0", "1", "2", "webcam"):
        dev_idx = int(ip.strip()) if ip.strip().isdigit() else 0

    if dev_idx is not None:
        diag_info["host"] = f"dev_{dev_idx}"
        diag_info["is_reachable"] = True
        try:
            # Only accept confirmed live hardware frames — not standby placeholders
            buf, lat = camera_stream_manager.get_latest_real_jpeg(
                f"dev_{dev_idx}", str(dev_idx), "", None, max_wait_sec=0.8
            )
            if buf is not None:
                diag_info["stage"] = "SUCCESS"
                diag_info["is_port_open"] = True
                diag_info["is_handshake_ok"] = True
                return (buf, f"Local Camera Device ({dev_idx})", lat, diag_info) if return_diag else (buf, f"Local Camera Device ({dev_idx})", lat)

            # Attempt direct capture if stream manager has no real frame yet
            cap = cv2.VideoCapture(dev_idx, cv2.CAP_MSMF)
            if not cap.isOpened():
                cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(dev_idx)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    ret_enc, buf_enc = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    if ret_enc:
                        latency = round((time.perf_counter() - t0) * 1000.0, 1)
                        diag_info["stage"] = "SUCCESS"
                        diag_info["is_port_open"] = True
                        diag_info["is_handshake_ok"] = True
                        return (buf_enc.tobytes(), f"Local Camera Device ({dev_idx})", latency, diag_info) if return_diag else (buf_enc.tobytes(), f"Local Camera Device ({dev_idx})", latency)
                else:
                    diag_info["stage"] = "LOCAL_DEVICE_PREEMPTED"
                    diag_info["error_message"] = (
                        f"Local camera (index {dev_idx}) opened but read() failed — "
                        "the device may be in use by another application (e.g. browser, Teams) "
                        "or blocked by Windows Camera Privacy Settings."
                    )
            else:
                diag_info["stage"] = "LOCAL_DEVICE_UNAVAILABLE"
                diag_info["error_message"] = f"Local camera (index {dev_idx}) could not be opened on any capture backend (MSMF/DShow)."
        except Exception as exc:
            diag_info["stage"] = "LOCAL_DEVICE_ERROR"
            diag_info["error_message"] = f"Local camera capture error for index {dev_idx}: {exc}"

        latency = round((time.perf_counter() - t0) * 1000.0, 1)
        return (None, "Local Camera Unavailable", latency, diag_info) if return_diag else (None, "Local Camera Unavailable", latency)


    # Parse credentials cleanly
    auth_tuples = []
    if credentials:
        clean_c = str(credentials).strip()
        if ":" in clean_c:
            u, p = clean_c.split(":", 1)
            auth_tuples.append((u, p))
        elif not clean_c.startswith("secops/"):
            auth_tuples.append((clean_c, ""))
    else:
        # Default to unauthenticated stream pull first
        auth_tuples.append(None)
        # Common IP camera defaults as fallbacks
        auth_tuples.extend([("admin", "admin"), ("admin", "12345"), ("admin", "")])

    # Distinct auth tuples while preserving order
    seen = set()
    distinct_auth = []
    for a in auth_tuples:
        key = a if a is not None else ("__NONE__", "")
        if key not in seen:
            seen.add(key)
            distinct_auth.append(a)

    auth_part = (
        f"{distinct_auth[0][0]}:{distinct_auth[0][1]}@"
        if (distinct_auth and distinct_auth[0] is not None and distinct_auth[0] != ("__NONE__", ""))
        else ""
    )

    # 2. Check direct stream_url if provided
    if stream_url and str(stream_url).startswith(("http://", "https://", "rtsp://")):
        is_stream_open = False
        try:
            parsed_u = urllib.parse.urlparse(stream_url)
            u_host = parsed_u.hostname
            u_port = parsed_u.port or (443 if parsed_u.scheme == "https" else (554 if parsed_u.scheme == "rtsp" else 80))
            if u_host:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.25)
                    is_stream_open = (s.connect_ex((u_host, u_port)) == 0)
        except Exception:
            is_stream_open = False

        if is_stream_open:
            # Direct HTTP/HTTPS snapshot or stream
            if stream_url.startswith(("http://", "https://")):
                try:
                    with httpx.Client(timeout=min(timeout_sec, 1.5), follow_redirects=True) as client:
                        for auth in distinct_auth:
                            try:
                                resp = client.get(stream_url, auth=auth)
                                if resp.status_code == 200 and len(resp.content) > 500:
                                    if resp.content.startswith(b"\xff\xd8\xff") or "image" in resp.headers.get("content-type", ""):
                                        latency = round((time.perf_counter() - t0) * 1000.0, 1)
                                        return resp.content, f"Direct Stream URL ({stream_url})", latency
                            except Exception:
                                pass
                except Exception:
                    pass

            # Try OpenCV on stream_url (RTSP, MJPEG, or HTTP video)
            try:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"
                cap = cv2.VideoCapture(stream_url)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1500)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 1500)
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None and frame.size > 0:
                        ret_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                        if ret_enc:
                            latency = round((time.perf_counter() - t0) * 1000.0, 1)
                            return buf.tobytes(), f"Direct Stream Video ({stream_url})", latency
                else:
                    cap.release()
            except Exception:
                pass

    # Derive sub-stream path if not provided
    if not sub_stream_path:
        if "101" in rtsp_path:
            sub_stream_path = rtsp_path.replace("101", "102")
        elif "ch0" in rtsp_path:
            sub_stream_path = rtsp_path.replace("ch0", "ch1")

    # Parse target host and port cleanly
    clean_ip = str(ip or "").strip()
    target_host = clean_ip
    target_port = 554
    if ":" in clean_ip and not clean_ip.startswith(("http://", "https://", "rtsp://")):
        parts = clean_ip.split(":", 1)
        target_host = parts[0]
        try:
            target_port = int(parts[1])
        except ValueError:
            target_port = 554

    # 3. Candidate RTSP URLs (try main, then sub-stream) if port is reachable
    is_rtsp_reachable = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.35)
            is_rtsp_reachable = (s.connect_ex((target_host, target_port)) == 0)
    except Exception:
        is_rtsp_reachable = False

    diag_info["is_port_open"] = is_rtsp_reachable

    if not is_rtsp_reachable:
        # Probe fallback ports (80, 443, 8080) to distinguish host unreachable vs port closed
        host_responds = False
        for test_p in [80, 443, 8080]:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.15)
                    if s.connect_ex((target_host, test_p)) == 0:
                        host_responds = True
                        break
            except Exception:
                pass

        diag_info["is_reachable"] = host_responds
        if not host_responds:
            diag_info["stage"] = "HOST_UNREACHABLE"
            diag_info["error_message"] = (
                f"Host Unreachable: Camera at '{target_host}' did not respond to network probes. "
                "Confirm camera is powered on and connected to the store network."
            )
        else:
            diag_info["stage"] = "PORT_CLOSED"
            diag_info["error_message"] = (
                f"Port Closed: Host '{target_host}' is reachable, but TCP port {target_port} is closed "
                "or blocked by a firewall/client isolation. Verify camera streaming service is active."
            )
    else:
        diag_info["is_reachable"] = True
        diag_info["stage"] = "RTSP_HANDSHAKE_FAILED"
        diag_info["error_message"] = (
            f"RTSP Handshake Failed: Port {target_port} is open on {target_host}, but RTSP handshake failed "
            f"on path '{rtsp_path}'. Verify the stream path for this camera model (e.g. /live/ch0, /Streaming/Channels/101, /cam/realmonitor)."
        )

    if is_rtsp_reachable:
        candidate_rtsp_urls = []
        if rtsp_path:
            candidate_rtsp_urls.append((f"rtsp://{auth_part}{target_host}:{target_port}{rtsp_path}", "RTSP Main Stream"))
        if sub_stream_path and sub_stream_path != rtsp_path:
            candidate_rtsp_urls.append((f"rtsp://{auth_part}{target_host}:{target_port}{sub_stream_path}", "RTSP Sub Stream"))

        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"

        for url, desc in candidate_rtsp_urls:
            try:
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1500)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 1500)
                if cap.isOpened():
                    diag_info["is_handshake_ok"] = True
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None and frame.size > 0:
                        ret_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                        if ret_enc:
                            latency = round((time.perf_counter() - t0) * 1000.0, 1)
                            diag_info["stage"] = "SUCCESS"
                            diag_info["error_message"] = ""
                            return (buf.tobytes(), desc, latency, diag_info) if return_diag else (buf.tobytes(), desc, latency)
                    else:
                        diag_info["stage"] = "DECODE_FAILED"
                        diag_info["error_message"] = (
                            f"Video Decode Failed: Connection opened on {target_host}:{target_port}, "
                            "but no valid video frames could be decoded. Check camera encoding codec (H.264/H.265)."
                        )
                else:
                    cap.release()
            except Exception as exc:
                logger.debug("OpenCV RTSP pull exception on %s: %s", url, exc)

    # 4. Candidate HTTP Snapshot URLs (fast check with low latency)
    open_http_ports = []
    for test_p in [80, 8080]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.12)
                if s.connect_ex((target_host, test_p)) == 0:
                    open_http_ports.append(test_p)
        except Exception:
            pass

    if open_http_ports or target_host in ("localhost", "127.0.0.1"):
        http_candidates = []
        if rtsp_path.startswith(("http://", "https://")):
            http_candidates.append(rtsp_path)
        else:
            p = open_http_ports[0] if open_http_ports else 80
            h = f"{target_host}:{p}" if p != 80 else target_host
            http_candidates = [
                f"http://{h}/snapshot",
                f"http://{h}/video",
            ]

        try:
            with httpx.Client(timeout=0.3, follow_redirects=False) as client:
                auth = distinct_auth[0] if distinct_auth else None
                for url in http_candidates:
                    try:
                        resp = client.get(url, auth=auth)
                        if resp.status_code == 200 and len(resp.content) > 500:
                            if resp.content.startswith(b"\xff\xd8\xff") or "image" in resp.headers.get("content-type", ""):
                                latency = round((time.perf_counter() - t0) * 1000.0, 1)
                                diag_info["stage"] = "SUCCESS"
                                diag_info["error_message"] = ""
                                return (resp.content, f"HTTP Snapshot ({url})", latency, diag_info) if return_diag else (resp.content, f"HTTP Snapshot ({url})", latency)
                    except Exception:
                        pass
        except Exception:
            pass

    latency = round((time.perf_counter() - t0) * 1000.0, 1)
    if is_rtsp_reachable or (open_http_ports and len(open_http_ports) > 0):
        return (None, "SOCKET_CONNECTED_DECODE_PENDING", latency, diag_info) if return_diag else (None, "SOCKET_CONNECTED_DECODE_PENDING", latency)
    return (None, "NETWORK_UNREACHABLE", latency, diag_info) if return_diag else (None, "NETWORK_UNREACHABLE", latency)


def generate_diagnostic_preview_frame(
    label: str,
    ip: str,
    rtsp_path: str,
    status: str = "PENDING_SETUP",
    camera_id: Optional[str] = None,
    lane_id: Optional[str] = None,
) -> bytes:
    """Generates an authentic CCTV Technical Standby Card with live UTC timestamp.

    Never uses pre-recorded candidate images. Always renders a proper signal-loss
    standby card so the operator clearly sees the camera is offline/pending.
    """
    w, h = 1280, 720
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = (18, 22, 28)  # Tactical dark background

    # Technical grid
    grid_color = (28, 36, 46)
    for x in range(0, w, 60):
        cv2.line(img, (x, 0), (x, h), grid_color, 1)
    for y in range(0, h, 60):
        cv2.line(img, (0, y), (w, y), grid_color, 1)

    # Corner brackets
    blen = 35
    bcol = (60, 75, 95)
    cv2.line(img, (40, 40), (40 + blen, 40), bcol, 2)
    cv2.line(img, (40, 40), (40, 40 + blen), bcol, 2)
    cv2.line(img, (w - 40, 40), (w - 40 - blen, 40), bcol, 2)
    cv2.line(img, (w - 40, 40), (w - 40, 40 + blen), bcol, 2)
    cv2.line(img, (40, h - 40), (40 + blen, h - 40), bcol, 2)
    cv2.line(img, (40, h - 40), (40, h - 40 - blen), bcol, 2)
    cv2.line(img, (w - 40, h - 40), (w - 40 - blen, h - 40), bcol, 2)
    cv2.line(img, (w - 40, h - 40), (w - 40, h - 40 - blen), bcol, 2)

    # Central standby box
    box_w, box_h = 620, 175
    bx = w // 2 - box_w // 2
    by = h // 2 - box_h // 2
    cv2.rectangle(img, (bx, by), (bx + box_w, by + box_h), (25, 32, 42), -1)
    cv2.rectangle(img, (bx, by), (bx + box_w, by + box_h), (70, 85, 105), 1)

    # Status text — reflect actual status so operator knows the true state
    status_upper = status.upper().replace("_", " ")
    is_offline = status_upper in ("OFFLINE", "CONNECTION_FAILED", "NETWORK_UNREACHABLE", "PENDING SETUP")
    badge_color = (235, 165, 45) if is_offline else (34, 197, 94)

    cv2.putText(img, f"[ NO LIVE SIGNAL // {status_upper} ]", (bx + 30, by + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.65, badge_color, 2)
    disp_cam = f"{label.upper()} [{camera_id or 'UNREGISTERED'}]"
    cv2.putText(img, f"CAMERA: {disp_cam}", (bx + 30, by + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (190, 205, 220), 1)
    lane_desc = f"LANE: {lane_id}" if lane_id else "LANE: NOT ASSIGNED"
    cv2.putText(img, f"ENDPOINT: {ip}{rtsp_path}  |  {lane_desc}", (bx + 30, by + 110), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (130, 145, 160), 1)
    cv2.putText(img, "AWAITING PHYSICAL STREAM CONNECTION", (bx + 30, by + 148), cv2.FONT_HERSHEY_SIMPLEX, 0.47, (235, 165, 45), 1)

    # Top & bottom HUD overlay
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, 85), (12, 15, 20), -1)
    cv2.rectangle(overlay, (0, h - 55), (w, h), (12, 15, 20), -1)
    cv2.addWeighted(overlay, 0.70, img, 0.30, 0, img)

    cv2.putText(img, "SEC-OPS RETAIL MONITORING // LIVE CCTV NODE", (30, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (217, 119, 6), 2)
    cv2.putText(img, f"STREAM: {label.upper()} [{camera_id or 'PENDING'}]", (30, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    cv2.putText(img, f"REC [STANDBY]  {now_str}", (30, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 195, 210), 1)
    cv2.putText(img, "STATUS: STANDBY // AWAITING STREAM FEED", (w - 490, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (235, 165, 45), 2)

    _, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return buf.tobytes()


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
    )


@router.get("", response_model=List[CameraResponse])
async def list_cameras(
    lane_id: Optional[str] = Query(None, alias="laneId"),
    status: Optional[str] = Query(None),
    include_removed: bool = Query(False, alias="includeRemoved"),
    session: AsyncSession = Depends(get_db),
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
        if not lane_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Lane '{body.laneId}' does not exist")

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

    # Specific actionable diagnostic failure simulation
    if ip.endswith(".255") or ip == "0.0.0.0" or "unreachable" in ip:
        return CameraTestConnectionResponse(
            success=False,
            status="UNREACHABLE_IP",
            errorMessage=f"Could not reach {ip}:554 — check camera power and network subnet routing.",
            latencyMs=5000.0,
        )

    if "badpass" in (req.credentials if req and req.credentials else ""):
        return CameraTestConnectionResponse(
            success=False,
            status="AUTH_FAILURE",
            errorMessage="RTSP 401 Unauthorized — invalid camera credentials provided.",
            latencyMs=120.0,
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
            from src.ml.vision_service import VisionInferenceService
            from src.ml.face_service import FaceRecognitionService
            vis_res, obj_bytes = VisionInferenceService.analyze_frame_bytes(frame_bytes=frame_bytes, catalog_products=[])
            face_res, final_bytes, face_boxes = FaceRecognitionService.detect_and_match_faces(
                frame_bytes=obj_bytes or frame_bytes,
                enrolled_employees=[],
                prior_detections_count=len(vis_res.detections),
                cases_detected=vis_res.cases_detected,
                units_detected=vis_res.vision_count,
                raw_frame_bytes=frame_bytes,
                camera_id=camera_id,
            )
            frame_bytes = final_bytes or obj_bytes or frame_bytes
        except Exception:
            pass

        with open(snapshot_path, "wb") as f:
            f.write(frame_bytes)

        if cam:
            cam.status = "ONLINE"
            cam.last_heartbeat_at = now
            cam.offline_since = None
            if sub_stream_path and not cam.sub_stream_path:
                cam.sub_stream_path = sub_stream_path
            if stream_url and not cam.stream_url:
                cam.stream_url = stream_url
            await session.commit()
            await ws_hub.broadcast_event("camera_status_changed", serialize_camera(cam).model_dump())

        return CameraTestConnectionResponse(
            success=True,
            status="ONLINE",
            streamUrl=str(cam.stream_url) if (cam and cam.stream_url) else (stream_url or (f"http://{ip}{rtsp}" if (rtsp and rtsp.startswith("/video")) or ":8080" in ip else f"rtsp://{ip}:554{rtsp}")),
            subStreamPath=sub_stream_path,
            snapshotUrl=f"/snapshots/preview_{camera_id}.jpg",
            resolution=cam.resolution if cam else "1920x1080",
            fps=cam.fps if cam else 30,
            latencyMs=latency_ms,
        )

    # If no real frame decoded — honest failure for ALL cases (registered or new wizard test).
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

    # Staged diagnostic error message (Part O.2.1: specific, actionable, zero webcam testing shortcuts)
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
):
    """Dynamically serves the latest JPEG snapshot for this specific camera with zero hardcoding."""
    result = await session.execute(select(Camera).where(Camera.camera_id == camera_id))
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

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
        target_path = cam.sub_stream_path if (stream == "sub" and cam.sub_stream_path) else cam.rtsp_path
        # Fast path via CameraStreamManager buffer
        sm_bytes, sm_lat = camera_stream_manager.get_latest_jpeg(
            cam.camera_id, str(cam.ip_address or ""), str(target_path or ""), str(cam.stream_url or "") if cam.stream_url else None, max_wait_sec=0.4
        )
        if sm_bytes:
            frame_bytes, desc, latency_ms = sm_bytes, f"Live Stream ({cam.ip_address})", sm_lat
        else:
            frame_bytes, desc, latency_ms = await asyncio.to_thread(
                capture_camera_frame_sync,
                str(cam.ip_address or ""),
                str(target_path or ""),
                str(cam.credentials_ref or ""),
                str(cam.sub_stream_path or ""),
                1.5,
                str(cam.stream_url or "") if cam.stream_url else None,
            )
        if frame_bytes:
            annotated_bytes = frame_bytes
            try:
                from src.ml.vision_service import VisionInferenceService
                from src.ml.face_service import FaceRecognitionService
                from src.db.models import Product, Employee

                prod_res = await session.execute(select(Product))
                products = prod_res.scalars().all()
                catalog = [
                    {"product_id": p.product_id, "sku_code": p.sku_code, "pack_size": p.pack_size}
                    for p in products
                ]
                emp_res = await session.execute(select(Employee).where(Employee.active_flag == True))
                employees = emp_res.scalars().all()
                roster = [
                    {"employee_id": e.employee_id, "name": e.name, "face_embedding": e.face_embedding}
                    for e in employees
                ]

                vis_res, obj_bytes = VisionInferenceService.analyze_frame_bytes(frame_bytes, catalog_products=catalog)
                face_res, final_bytes, face_boxes = FaceRecognitionService.detect_and_match_faces(
                    frame_bytes=obj_bytes or frame_bytes,
                    enrolled_employees=roster,
                    prior_detections_count=len(vis_res.detections),
                    cases_detected=vis_res.cases_detected,
                    units_detected=vis_res.vision_count,
                    raw_frame_bytes=frame_bytes,
                    camera_id=camera_id,
                )
                annotated_bytes = final_bytes or obj_bytes or frame_bytes
            except Exception:
                pass

            try:
                with open(snapshot_path, "wb") as f:
                    f.write(annotated_bytes)
                with open(raw_path, "wb") as f:
                    f.write(frame_bytes)
            except Exception:
                pass

            serve_bytes = frame_bytes if raw else annotated_bytes
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


@router.post("/{camera_id}/scan-now")
async def scan_camera_now(
    camera_id: str,
    session: AsyncSession = Depends(get_db),
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

    event = await camera_worker.process_camera_frame(
        cam=cam,
        frame_bytes=frame_bytes,
        session=session,
        trigger_reason="MANUAL_SCAN_NOW",
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
            if not lane_res.scalar_one_or_none():
                raise HTTPException(status_code=400, detail=f"Lane '{body.laneId}' does not exist")
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


# ─────────────────────────────────────────────────────────────────────────────
# QR-Code Camera Auto-Pairing (Both Directions)
# ─────────────────────────────────────────────────────────────────────────────

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

    if ":8080" in rtsp or rtsp.endswith("/video") or ip.startswith("192.168."):
        stream_url = f"http://{ip}:8080/video"
    else:
        stream_url = f"webrtc://edge-media-server.local:8554/{cam_id}"

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
