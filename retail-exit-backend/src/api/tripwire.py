"""Virtual Tripwire & Perimeter Access REST API

Configures directional virtual line boundaries and queries crossing / tailgating telemetry.
"""

from typing import List, Dict, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.db.session import get_db
from src.db.models import VirtualTripwireConfig, TripwireCrossingEvent, Camera
from src.engine.tripwire_engine import TripwireEngine

router = APIRouter(prefix="/tripwire", tags=["Virtual Tripwire"])


class VirtualTripwireCreateRequest(BaseModel):
    cameraId: str = Field(..., description="ID of surveillance camera hosting this tripwire")
    label: str = Field(..., description="Descriptive label e.g. 'Dock 4 Perimeter'")
    lineCoords: List[List[float]] = Field(
        ...,
        description="Normalized coordinates [[x1, y1], [x2, y2]] between 0.0 and 1.0"
    )
    directionMode: str = Field("BIDIRECTIONAL", description="'BIDIRECTIONAL', 'ENTRY_ONLY', or 'EXIT_ONLY'")
    active: bool = Field(True)


class VirtualTripwireResponse(BaseModel):
    tripwireId: str
    cameraId: str
    label: str
    lineCoords: List[List[float]]
    directionMode: str
    active: bool
    createdAt: str
    updatedAt: str


class TripwireCrossingResponse(BaseModel):
    crossingId: str
    tripwireId: str
    cameraId: str
    trackId: str
    timestamp: str
    direction: str
    entityType: str
    biometricStatus: str
    matchedEmployeeId: Optional[str] = None
    isTailgating: bool
    tailgatingDetails: Optional[Dict[str, Any]] = None
    snapshotUrl: Optional[str] = None


def _serialize_config(t: VirtualTripwireConfig) -> VirtualTripwireResponse:
    return VirtualTripwireResponse(
        tripwireId=t.tripwire_id,
        cameraId=t.camera_id,
        label=t.label,
        lineCoords=t.line_coords,
        directionMode=t.direction_mode,
        active=t.active,
        createdAt=t.created_at.isoformat() if t.created_at else "",
        updatedAt=t.updated_at.isoformat() if t.updated_at else "",
    )


def _serialize_crossing(c: TripwireCrossingEvent) -> TripwireCrossingResponse:
    return TripwireCrossingResponse(
        crossingId=c.crossing_id,
        tripwireId=c.tripwire_id,
        cameraId=c.camera_id,
        trackId=c.track_id,
        timestamp=c.timestamp.isoformat() if c.timestamp else "",
        direction=c.direction,
        entityType=c.entity_type,
        biometricStatus=c.biometric_status,
        matchedEmployeeId=c.matched_employee_id,
        isTailgating=c.is_tailgating,
        tailgatingDetails=c.tailgating_details,
        snapshotUrl=c.snapshot_url,
    )


@router.get("/configs", response_model=List[VirtualTripwireResponse])
async def list_tripwires(
    camera_id: Optional[str] = Query(None, alias="cameraId"),
    session: AsyncSession = Depends(get_db),
):
    """Lists configured virtual tripwires, optionally filtered by camera."""
    query = select(VirtualTripwireConfig)
    if camera_id:
        query = query.where(VirtualTripwireConfig.camera_id == camera_id)
    res = await session.execute(query)
    rows = res.scalars().all()
    return [_serialize_config(r) for r in rows]


@router.post("/configs", response_model=VirtualTripwireResponse, status_code=201)
async def create_tripwire(
    body: VirtualTripwireCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """Creates a new virtual tripwire boundary for a camera."""
    # Verify camera exists
    cam_res = await session.execute(select(Camera).where(Camera.camera_id == body.cameraId))
    cam = cam_res.scalar_one_or_none()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{body.cameraId}' not found")

    if len(body.lineCoords) != 2:
        raise HTTPException(status_code=400, detail="lineCoords must contain exactly two [x, y] points")

    tripwire = VirtualTripwireConfig(
        camera_id=body.cameraId,
        label=body.label,
        line_coords=body.lineCoords,
        direction_mode=body.directionMode,
        active=body.active,
    )
    session.add(tripwire)
    await session.commit()
    await session.refresh(tripwire)
    return _serialize_config(tripwire)


@router.delete("/configs/{tripwire_id}", status_code=204)
async def delete_tripwire(
    tripwire_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Deletes a virtual tripwire boundary."""
    res = await session.execute(select(VirtualTripwireConfig).where(VirtualTripwireConfig.tripwire_id == tripwire_id))
    t = res.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail=f"Tripwire '{tripwire_id}' not found")

    await session.delete(t)
    await session.commit()
    return None


@router.get("/crossings", response_model=List[TripwireCrossingResponse])
async def list_crossings(
    tripwire_id: Optional[str] = Query(None, alias="tripwireId"),
    camera_id: Optional[str] = Query(None, alias="cameraId"),
    tailgating_only: bool = Query(False, alias="tailgatingOnly"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    """Queries historical tripwire crossing events."""
    query = select(TripwireCrossingEvent).order_by(desc(TripwireCrossingEvent.timestamp)).limit(limit)
    if tripwire_id:
        query = query.where(TripwireCrossingEvent.tripwire_id == tripwire_id)
    if camera_id:
        query = query.where(TripwireCrossingEvent.camera_id == camera_id)
    if tailgating_only:
        query = query.where(TripwireCrossingEvent.is_tailgating == True)

    res = await session.execute(query)
    rows = res.scalars().all()
    return [_serialize_crossing(r) for r in rows]
