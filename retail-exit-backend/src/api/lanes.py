"""Sensor Lane & Hardware Registry Endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Any
import random

from src.db.session import get_db
from src.db.models import Lane, Store, Camera, get_utc_now
from src.db.audit import log_audit_entry
from src.schemas.lanes import SensorLaneSchema, LaneCreate
from src.realtime.hub import ws_hub
from src.cache import cache_service
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/lanes", tags=["Lanes"])

# Dynamic lane lock state (managed via toggle endpoints)
lane_lock_state: dict[str, bool] = {}


def serialize_lane(l: Any, cam: Any = None) -> SensorLaneSchema:
    lane_id_str = str(l.lane_id)
    lane_num = lane_id_str.split("-")[-1] if "-" in lane_id_str else lane_id_str[-2:]
    cam_ip = str(cam.ip_address) if (cam and getattr(cam, "ip_address", None)) else ""
    cam_fps = float(str(cam.fps)) if (cam and getattr(cam, "fps", None)) else (30.0 if cam else 0.0)
    has_rfid = bool(getattr(l, "rfid_antenna_id", None))
    rfid_dbm = 30.0 if has_rfid else 0.0
    last_hb = getattr(l, "last_heartbeat_at", None)
    last_ping = last_hb.isoformat() if last_hb is not None else ""

    return SensorLaneSchema(
        laneId=lane_id_str,
        name=f"Exit Lane {lane_num}",
        location=str(l.label),
        status=str(l.status),
        cameraIp=cam_ip,
        cameraFps=cam_fps,
        rfidGatePowerDbm=rfid_dbm,
        scaleTareKg=0.0,
        lastPing=last_ping,
    )


@router.get("", response_model=List[SensorLaneSchema])
async def list_lanes(session: AsyncSession = Depends(get_db)):
    """Lists all registered sensor lanes and dynamically linked edge hardware with cached reads."""
    cache_key = "lanes:all"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return [SensorLaneSchema(**item) for item in cached]

    stmt = select(Lane).order_by(Lane.lane_id)
    result = await session.execute(stmt)
    lanes = result.scalars().all()

    # Query active cameras mapped to lanes
    cams_res = await session.execute(select(Camera).where(Camera.removed_at.is_(None)))
    cams_by_lane = {str(c.lane_id): c for c in cams_res.scalars().all() if c.lane_id}

    serialized = [serialize_lane(l, cams_by_lane.get(str(l.lane_id))) for l in lanes]
    await cache_service.set(cache_key, [item.model_dump() for item in serialized], ttl_seconds=120)
    return serialized


@router.post("", response_model=SensorLaneSchema, status_code=201)
async def create_lane(
    body: LaneCreate,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Creates a new physical exit portal lane inline."""
    lane_id = body.laneId or f"LANE-{random.randint(5, 99):02d}"
    
    # Check if lane ID already exists
    existing = await session.execute(select(Lane).where(Lane.lane_id == lane_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Lane '{lane_id}' already exists")

    now = get_utc_now()
    new_lane = Lane(
        lane_id=lane_id,
        label=body.label,
        store_id=body.storeId or "store_0402",
        rfid_antenna_id=body.rfidAntennaId or f"ANT-{lane_id}-01",
        weight_sensor_id=body.weightSensorId or f"SCALE-{lane_id}-A",
        turnstile_ctrl_id=body.turnstileCtrlId or f"LOCK-{lane_id}-M",
        status="ONLINE",
        last_heartbeat_at=now,
    )
    session.add(new_lane)
    await session.flush()

    await log_audit_entry(
        session=session,
        entity_type="LANE",
        entity_id=str(new_lane.lane_id),
        action="CREATE_LANE",
        actor_type="USER",
        before_state=None,
        after_state={"lane_id": str(new_lane.lane_id), "label": str(new_lane.label), "status": str(new_lane.status)},
    )
    await session.commit()
    await cache_service.invalidate("lanes")

    return serialize_lane(new_lane, None)


@router.post("/{lane_id}/turnstile/toggle")
async def toggle_lane_turnstile(
    lane_id: str,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Toggles electromagnetic turnstile interlock lock status."""
    is_locked = lane_lock_state.get(lane_id, False)
    new_locked = not is_locked
    lane_lock_state[lane_id] = new_locked

    await ws_hub.broadcast_event(
        "turnstile_lock_changed",
        {"laneId": lane_id, "isLocked": new_locked},
    )
    return {"laneId": lane_id, "isLocked": new_locked, "status": "COMMAND_ACKED"}
