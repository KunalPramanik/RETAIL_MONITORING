"""FastAPI Application Main Entrypoint

Smart Retail Exit Monitoring & Inventory Intelligence Platform (SEC-OPS 2.0).
Provides RESTful APIs, real-time WebSocket streams, telemetry metrics, and edge pipelines.
"""

import os
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, Optional
import json
import time
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import asyncio
from datetime import datetime, timezone, timedelta

from src.core.config import settings
from src.db.session import init_db, close_db, AsyncSessionLocal
from src.db.models import Camera, Alert, ThresholdConfig, Lane, get_utc_now
from src.db.init_config import init_baseline_configuration
from src.api.router import api_router
from src.realtime.hub import ws_hub
from src.observability.metrics import metrics
from src.observability.logging import configure_logging, correlation_id_ctx
from src.engine.camera_worker import camera_worker
from src.engine.alarm import AlarmCoordinator
from src.engine.discovery_service import discovery_service
from src.hardware.usb_detector import usb_service

configure_logging()
logger = logging.getLogger("secops.main")

_is_shutting_down = False


async def reconcile_duplicate_cameras(session: AsyncSession) -> int:
    """Startup reconciliation for any pre-existing duplicate camera endpoints.
    
    Detects existing active camera rows sharing identical normalized endpoints,
    retains the primary (earliest added_at), soft-deletes duplicates (removed_at = now()),
    and writes an immutable audit_log entry explaining the merge.
    """
    stmt = select(Camera).where(Camera.removed_at.is_(None)).order_by(Camera.added_at.asc())
    res = await session.execute(stmt)
    active_cams = res.scalars().all()

    seen_endpoints: Dict[str, Camera] = {}
    reconciled_count = 0
    now = get_utc_now()

    for cam in active_cams:
        norm_ip = (cam.ip_address or "").strip().lower()
        norm_path = (cam.rtsp_path or "").strip().lower()
        norm_stream = (cam.stream_url or "").strip().lower()

        key = norm_stream if norm_stream else f"{norm_ip}:{norm_path}"
        if not key or key == ":":
            continue

        if key in seen_endpoints:
            primary = seen_endpoints[key]
            cam.removed_at = now
            reconciled_count += 1
            logger.warning(
                "Duplicate camera detected and reconciled: camera_id=%s merged into primary camera_id=%s (endpoint=%s)",
                cam.camera_id,
                primary.camera_id,
                key,
            )
            try:
                from src.api.cameras import log_audit_entry
                await log_audit_entry(
                    session=session,
                    entity_type="CAMERA",
                    entity_id=cam.camera_id,
                    action="STARTUP_RECONCILE_DUPLICATE",
                    actor_type="SYSTEM",
                    before_state={
                        "camera_id": cam.camera_id,
                        "label": cam.label,
                        "status": cam.status,
                        "endpoint": key,
                    },
                    after_state={
                        "camera_id": cam.camera_id,
                        "removed_at": now.isoformat(),
                        "merged_into_camera_id": primary.camera_id,
                        "reason": "Startup reconciliation soft-deleted duplicate camera row for identical endpoint",
                    },
                )
            except Exception as audit_err:
                logger.debug("Audit log entry for duplicate reconciliation skipped: %s", audit_err)
        else:
            seen_endpoints[key] = cam

    if reconciled_count > 0:
        await session.commit()
        logger.info("Startup duplicate camera reconciliation complete: %d duplicate(s) soft-deleted.", reconciled_count)

    return reconciled_count


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle hooks."""
    global _is_shutting_down
    _is_shutting_down = False

    logger.info("Initializing SEC-OPS backend services and database schema...")
    await init_db()
    # DB initialized via Alembic Migrations in Production

    # Initialize baseline configuration (Store, ThresholdConfig) with clean operational defaults
    async with AsyncSessionLocal() as session:
        await init_baseline_configuration(session)
        # Reconcile duplicate camera endpoints on startup
        await reconcile_duplicate_cameras(session)
    logger.info("Database schema initialized with clean baseline configuration.")

    # Start background tasks
    await ws_hub.start()
    heartbeat_task = asyncio.create_task(periodic_ws_heartbeat())
    camera_monitor_task = asyncio.create_task(periodic_camera_monitor())
    camera_worker.start()
    discovery_service.start()
    usb_service.start()

    yield

    _is_shutting_down = True
    logger.info("Shutting down SEC-OPS background tasks...")

    # Gracefully stop worker and cancel background loops
    heartbeat_task.cancel()
    camera_monitor_task.cancel()
    await camera_worker.stop()
    await discovery_service.stop()
    await usb_service.stop()
    await ws_hub.stop()

    await asyncio.gather(heartbeat_task, camera_monitor_task, return_exceptions=True)

    # Cleanly dispose database connection pool
    await close_db()
    logger.info("SEC-OPS platform shutdown cleanly.")


async def get_active_edge_nodes_count() -> int:
    """Calculates active edge ingestion nodes dynamically from camera health records within freshness limit."""
    try:
        now = get_utc_now()
        freshness_cutoff = now - timedelta(seconds=60)
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(Camera).where(
                    and_(
                        Camera.removed_at.is_(None),
                        Camera.status == "ONLINE",
                        Camera.last_heartbeat_at.isnot(None),
                        Camera.last_heartbeat_at >= freshness_cutoff,
                    )
                )
            )
            fresh_cams = len(res.scalars().all())
            active_worker_cams = len(getattr(camera_worker, "_last_frames", {}))
            return max(fresh_cams, active_worker_cams)
    except Exception:
        return len(getattr(camera_worker, "_last_frames", {}))


async def periodic_ws_heartbeat():
    """Background task sending periodic heartbeat pings to connected control consoles."""
    while not _is_shutting_down:
        try:
            await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL_SEC)
            if _is_shutting_down:
                break
            nodes_online = await get_active_edge_nodes_count()
            await ws_hub.broadcast_event("heartbeat", {"status": "HEALTHY", "edgeNodesOnline": nodes_online})
        except asyncio.CancelledError:
            break
        except Exception as e:
            if _is_shutting_down:
                break
            logger.error(f"Error during WebSocket heartbeat: {e}")


async def periodic_camera_monitor():
    """Background fleet monitor checking camera heartbeat timeouts and dispatching CAMERA_OFFLINE alerts."""
    while not _is_shutting_down:
        try:
            await asyncio.sleep(10)
            if _is_shutting_down:
                break
            async with AsyncSessionLocal() as session:
                cfg_res = await session.execute(select(ThresholdConfig).limit(1))
                cfg = cfg_res.scalar_one_or_none()
                offline_after_sec = float(cfg.camera_offline_alert_after_sec) if cfg and cfg.camera_offline_alert_after_sec is not None else 60.0

                now = get_utc_now()
                cutoff = now - timedelta(seconds=offline_after_sec)

                # Find ONLINE or DEGRADED cameras with expired heartbeats or missing heartbeat past registration
                stmt = select(Camera).where(
                    and_(
                        Camera.removed_at.is_(None),
                        Camera.status.in_(["ONLINE", "DEGRADED"]),
                        or_(
                            and_(
                                Camera.last_heartbeat_at.isnot(None),
                                Camera.last_heartbeat_at < cutoff,
                            ),
                            and_(
                                Camera.last_heartbeat_at.is_(None),
                                Camera.created_at < cutoff,
                            ),
                        ),
                    )
                )
                res = await session.execute(stmt)
                stale_cameras = res.scalars().all()

                for cam in stale_cameras:
                    cam.status = "OFFLINE"
                    cam.offline_since = now

                    # Check if an OPEN CAMERA_OFFLINE alert already exists for this camera
                    alert_check = await session.execute(
                        select(Alert).where(
                            Alert.camera_id == cam.camera_id,
                            Alert.alert_type == "CAMERA_OFFLINE",
                            Alert.status == "OPEN",
                        )
                    )
                    if not alert_check.scalar_one_or_none():
                        new_alert = Alert(
                            alert_id=f"ALT-{uuid.uuid4().hex[:6].upper()}",
                            camera_id=cam.camera_id,
                            alert_type="CAMERA_OFFLINE",
                            severity="HIGH",
                            delta_units=0,
                            status="OPEN",
                            created_at=now,
                        )
                        session.add(new_alert)
                        await session.flush()

                        logger.warning(f"CAMERA_OFFLINE Alert generated for camera {cam.camera_id} ({cam.label})")
                        await ws_hub.broadcast_event("new_alert", {
                            "alertId": new_alert.alert_id,
                            "cameraId": cam.camera_id,
                            "alertType": "CAMERA_OFFLINE",
                            "severity": "HIGH",
                            "deltaUnits": 0,
                            "status": "OPEN",
                            "createdAt": now.isoformat(),
                        })

                    await ws_hub.broadcast_event("camera_status_changed", {
                        "cameraId": cam.camera_id,
                        "label": cam.label,
                        "laneId": cam.lane_id,
                        "status": "OFFLINE",
                        "lastHeartbeatAt": cam.last_heartbeat_at.isoformat() if cam.last_heartbeat_at else None,
                        "offlineSince": now.isoformat(),
                    })

                if stale_cameras:
                    await session.commit()

                # Periodic Alarm Dispatch Retry Loop
                try:
                    await AlarmCoordinator.retry_failed_dispatches(session)
                except Exception as retry_err:
                    logger.debug(f"Alarm retry pass error: {retry_err}")

                # Silent Lane Watchdog Check (>15 min silence on ONLINE lanes or uninitialized past cutoff)
                try:
                    lane_cutoff = now - timedelta(minutes=15)
                    silent_stmt = select(Lane).where(
                        and_(
                            Lane.status == "ONLINE",
                            or_(
                                and_(
                                    Lane.last_heartbeat_at.isnot(None),
                                    Lane.last_heartbeat_at < lane_cutoff,
                                ),
                                and_(
                                    Lane.last_heartbeat_at.is_(None),
                                    Lane.created_at < lane_cutoff,
                                ),
                            ),
                        )
                    )
                    silent_res = await session.execute(silent_stmt)
                    silent_lanes = silent_res.scalars().all()
                    metrics.silent_lanes_total = len(silent_lanes)
                    if silent_lanes:
                        for sl in silent_lanes:
                            sl.status = "OFFLINE"
                            sl.offline_since = now
                            logger.warning(
                                f"LANE_SILENT: Exit Lane {sl.lane_id} ({sl.label}) heartbeat timed out (>15 min silent) â€” transitioned to OFFLINE."
                            )
                            await ws_hub.broadcast_event(
                                "lane_status_changed",
                                {
                                    "laneId": sl.lane_id,
                                    "status": "OFFLINE",
                                    "offlineSince": now.isoformat(),
                                    "label": sl.label,
                                },
                            )
                        await session.commit()
                except Exception as lane_err:
                    logger.debug(f"Silent lane check pass error: {lane_err}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            if _is_shutting_down:
                break
            err_msg = str(e).lower()
            if "no active connection" in err_msg or "closed" in err_msg:
                break
            logger.error(f"Error during periodic camera monitoring: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Control-room backend, database & ML inference platform for retail loss prevention.",
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Injects or extracts end-to-end correlation ID for full request-event chain traceability."""
    corr_id = request.headers.get("X-Correlation-ID") or f"corr_{uuid.uuid4().hex[:12]}"
    token = correlation_id_ctx.set(corr_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
    finally:
        correlation_id_ctx.reset(token)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST API
app.include_router(api_router)

# Mount Static Uploads for hard-copy bill documents & CCTV evidence
uploads_dir = os.path.join(os.getcwd(), "uploads")
os.makedirs(os.path.join(uploads_dir, "invoices"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Mount Static Snapshots for live CCTV camera frames & event evidence
snapshots_dir = os.path.join(os.getcwd(), "snapshots")
os.makedirs(snapshots_dir, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=snapshots_dir), name="snapshots")


# Real-time WebSocket Gateway
@app.websocket("/ws/live")
async def websocket_live_gateway(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """Real-time WebSocket connection endpoint for control room consoles."""
    # Optional token verification if token provided or mandatory if configured
    if settings.websocket.require_token_auth or token is not None:
        if not token:
            await websocket.close(code=4001, reason="Authentication token required")
            return
        try:
            from jose import jwt
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except Exception as auth_err:
            logger.warning(f"WebSocket token authentication rejected: {auth_err}")
            await websocket.close(code=4003, reason="Invalid or expired token")
            return

    await ws_hub.connect(websocket)
    heartbeat_task = asyncio.create_task(ws_hub.heartbeat_pinger(websocket))
    try:
        while True:
            # Idle timeout watchdog: terminate connection if no client frames received
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.websocket.heartbeat_timeout_sec,
                )
            except asyncio.TimeoutError:
                logger.info("WebSocket idle timeout exceeded without heartbeat. Terminating dead connection.")
                break

            # Handle client-initiated ping / pong
            if data == "ping":
                await websocket.send_text("pong")
            else:
                try:
                    parsed = json.loads(data)
                    if parsed.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket client connection closed: {e}")
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        ws_hub.disconnect(websocket)


# Prometheus Metrics
@app.get("/metrics", tags=["Observability"])
async def get_metrics():
    """Exposes Prometheus formatted telemetry metrics."""
    return Response(content=metrics.generate_prometheus_text(), media_type="text/plain")


# Health Check
@app.get("/health", tags=["Observability"])
async def get_health():
    """Standard health check endpoint reporting live system status."""
    nodes_online = await get_active_edge_nodes_count()
    return {
        "status": "HEALTHY",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "CONNECTED",
        "edgeNodesOnline": nodes_online,
        "edgeCluster": f"{nodes_online}_NODES_ONLINE",
    }
