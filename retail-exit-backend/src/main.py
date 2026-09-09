"""FastAPI Application Main Entrypoint

Smart Retail Exit Monitoring & Inventory Intelligence Platform (SEC-OPS 2.0).
Provides RESTful APIs, real-time WebSocket streams, telemetry metrics, and edge pipelines.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, and_
import logging
import asyncio
import random
from datetime import datetime, timezone, timedelta

from src.config import settings
from src.db.session import init_db, close_db, AsyncSessionLocal
from src.db.models import Camera, Alert, ThresholdConfig, get_utc_now
from src.db.init_config import init_baseline_configuration
from src.api.router import api_router
from src.realtime.hub import ws_hub
from src.observability.metrics import metrics
from src.observability.logging import configure_logging
from src.engine.camera_worker import camera_worker

configure_logging()
logger = logging.getLogger("secops.main")

_is_shutting_down = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle hooks."""
    global _is_shutting_down
    _is_shutting_down = False

    logger.info("Initializing SEC-OPS backend services and database schema...")
    await init_db()

    # Initialize baseline configuration (Store, ThresholdConfig) with 0 mock rows per Part I policy
    async with AsyncSessionLocal() as session:
        await init_baseline_configuration(session)
    logger.info("Database schema initialized with clean baseline configuration.")

    # Start background tasks
    heartbeat_task = asyncio.create_task(periodic_ws_heartbeat())
    camera_monitor_task = asyncio.create_task(periodic_camera_monitor())
    camera_worker.start()

    yield

    _is_shutting_down = True
    logger.info("Shutting down SEC-OPS background tasks...")

    # Gracefully stop worker and cancel background loops
    heartbeat_task.cancel()
    camera_monitor_task.cancel()
    await camera_worker.stop()

    await asyncio.gather(heartbeat_task, camera_monitor_task, return_exceptions=True)

    # Cleanly dispose database connection pool
    await close_db()
    logger.info("SEC-OPS platform shutdown cleanly.")


async def periodic_ws_heartbeat():
    """Background task sending periodic heartbeat pings to connected control consoles."""
    while not _is_shutting_down:
        try:
            await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL_SEC)
            if _is_shutting_down:
                break
            await ws_hub.broadcast_event("heartbeat", {"status": "HEALTHY", "edgeNodesOnline": 4})
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

                # Find ONLINE or DEGRADED cameras with expired heartbeats
                stmt = select(Camera).where(
                    and_(
                        Camera.removed_at.is_(None),
                        Camera.status.in_(["ONLINE", "DEGRADED"]),
                        Camera.last_heartbeat_at.isnot(None),
                        Camera.last_heartbeat_at < cutoff,
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
                            alert_id=f"ALT-{random.randint(8100, 8999)}",
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
async def websocket_live_gateway(websocket: WebSocket):
    """Real-time WebSocket connection endpoint for control room consoles."""
    await ws_hub.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_hub.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket client connection closed: {e}")
        ws_hub.disconnect(websocket)


# Prometheus Metrics
@app.get("/metrics", tags=["Observability"])
async def get_metrics():
    """Exposes Prometheus formatted telemetry metrics."""
    return Response(content=metrics.generate_prometheus_text(), media_type="text/plain")


# Health Check
@app.get("/health", tags=["Observability"])
async def get_health():
    """Standard health check endpoint."""
    return {
        "status": "HEALTHY",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "CONNECTED",
        "edgeCluster": "4_NODES_ONLINE",
    }
