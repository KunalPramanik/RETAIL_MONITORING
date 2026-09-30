"""Access Control & Vehicle ANPR API Endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from src.db.session import get_db
from src.db.models import AccessControlEvent, VehicleDetection
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/integrations", tags=["V8 External Integrations"])

class AccessEventCreate(BaseModel):
    door_id: str
    employee_id: Optional[str] = None
    credential_type: str = Field(..., description="RFID_BADGE, FACE, PIN, BLUETOOTH")
    access_status: str = Field(..., description="GRANTED, DENIED, ANTI_PASSBACK_VIOLATION")
    denial_reason: Optional[str] = None

class VehicleEventCreate(BaseModel):
    camera_id: str
    license_plate: Optional[str] = None
    plate_confidence: Optional[float] = None
    vehicle_class: str = Field(..., description="CAR, TRUCK, VAN, MOTORCYCLE")
    color: Optional[str] = None
    direction: Optional[str] = None
    watchlist_hit: bool = False

@router.post("/access-control", response_model=dict)
async def register_access_event(
    req: AccessEventCreate,
    session: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["SUPER_ADMIN", "SECURITY_SUPERVISOR"]))
):
    """Ingest a physical door/turnstile access control event."""
    event = AccessControlEvent(**req.dict())
    session.add(event)
    await session.commit()
    return {"status": "success", "access_id": event.access_id}

@router.post("/anpr", response_model=dict)
async def register_vehicle_event(
    req: VehicleEventCreate,
    session: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["SUPER_ADMIN", "SECURITY_SUPERVISOR"]))
):
    """Ingest a vehicle detection / ANPR event from the edge pipeline."""
    # V8 Anti-Hallucination: Reject fake plates
    if req.license_plate and req.plate_confidence and req.plate_confidence < 0.85:
        # Confidence too low to trust the string, record vehicle but wipe plate
        req.license_plate = None
        req.plate_confidence = None

    event = VehicleDetection(**req.dict())
    session.add(event)
    await session.commit()
    return {"status": "success", "detection_id": event.detection_id}
