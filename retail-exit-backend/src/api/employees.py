"""Employee Badge Registry & Carrier History Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional, Any
from datetime import datetime, timezone, timedelta
import logging

from src.db.session import get_db
from src.db.models import Employee, ExitEvent, get_utc_now
from src.db.audit import log_audit_entry
from src.schemas.employees import (
    EmployeeResponse,
    EmployeeCreate,
    EmployeeHistoryResponse,
    EmployeeHistoryItem,
    EmployeePhotoResponse,
)
from src.ml.face_service import FaceRecognitionService

logger = logging.getLogger("secops.api.employees")
router = APIRouter(prefix="/employees", tags=["Employees"])


def normalize_dt(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_within_window(dt: Optional[datetime], window: datetime) -> bool:
    ndt = normalize_dt(dt)
    return ndt is not None and ndt >= window


def serialize_employee(emp: Any, mismatch_count: int = 0) -> EmployeeResponse:
    """Serializes an Employee ORM instance to a typed EmployeeResponse."""
    has_face = bool(emp.face_embedding is not None and len(emp.face_embedding) > 0)
    emb_ts = emp.embedding_updated_at.isoformat() if getattr(emp, "embedding_updated_at", None) else None
    return EmployeeResponse(
        employeeId=str(emp.employee_id),
        name=str(emp.name),
        role=str(emp.role),
        rfidBadgeId=str(emp.rfid_badge_id),
        shiftId=str(emp.shift_id) if emp.shift_id else None,
        activeFlag=bool(emp.active_flag),
        mismatchCount30d=mismatch_count,
        hasFaceEnrolled=has_face,
        embeddingUpdatedAt=emb_ts,
    )


def serialize_history_item(e: Any) -> EmployeeHistoryItem:
    """Serializes an ExitEvent ORM instance to a typed EmployeeHistoryItem."""
    return EmployeeHistoryItem(
        eventId=str(e.event_id),
        timestamp=e.ts.isoformat() if e.ts else "",
        laneId=str(e.lane_id),
        casesDetected=int(e.cases_detected),
        consensusUnits=int(e.consensus_units),
        declaredUnits=int(e.declared_units) if e.declared_units is not None else None,
        deltaUnits=int(e.delta_units) if e.delta_units is not None else None,
        verdict=str(e.verdict),
        severity=str(e.severity) if e.severity else "NONE",
        notes=str(e.notes) if e.notes else None,
    )


@router.get("", response_model=List[EmployeeResponse])
async def list_employees(
    query: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Lists warehouse personnel with real-time 30-day mismatch counts."""
    result = await session.execute(select(Employee).order_by(Employee.name))
    employees = result.scalars().all()

    now = get_utc_now()
    window_30d = now - timedelta(days=30)

    # Compute 30d mismatches for each employee
    response = []
    for emp in employees:
        events_res = await session.execute(
            select(ExitEvent)
            .where(
                ExitEvent.employee_id == emp.employee_id,
                ExitEvent.verdict == "MISMATCH",
            )
        )
        all_mismatch_events = events_res.scalars().all()
        mismatch_count = sum(
            1 for e in all_mismatch_events
            if is_within_window(e.ts, window_30d)
        )

        if query:
            q = query.lower()
            if not (
                q in str(emp.name).lower()
                or q in str(emp.role).lower()
                or q in str(emp.rfid_badge_id).lower()
            ):
                continue

        response.append(serialize_employee(emp, mismatch_count))
    return response


@router.post("", response_model=EmployeeResponse, status_code=201)
async def create_employee(
    body: EmployeeCreate,
    session: AsyncSession = Depends(get_db),
):
    """Registers a new warehouse employee with RFID badge assignment."""
    existing = await session.execute(
        select(Employee).where(Employee.rfid_badge_id == body.rfidBadgeId)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Badge ID '{body.rfidBadgeId}' already assigned")

    emp = Employee(
        name=body.name,
        role=body.role,
        rfid_badge_id=body.rfidBadgeId,
        shift_id=body.shiftId,
        active_flag=body.activeFlag,
    )
    session.add(emp)
    await session.flush()

    await log_audit_entry(
        session=session,
        entity_type="EMPLOYEE",
        entity_id=str(emp.employee_id),
        action="REGISTER_EMPLOYEE",
        actor_type="USER",
        before_state=None,
        after_state=body.model_dump(),
    )
    await session.commit()

    return serialize_employee(emp, 0)


@router.get("/{employee_id}/history", response_model=EmployeeHistoryResponse)
async def get_employee_history(
    employee_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves full exit traversal audit trail and repeat offender standing."""
    result = await session.execute(select(Employee).where(Employee.employee_id == employee_id))
    emp = result.scalar_one_or_none()

    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found")

    now = get_utc_now()
    window_30d = now - timedelta(days=30)

    events_res = await session.execute(
        select(ExitEvent)
        .where(ExitEvent.employee_id == employee_id)
        .order_by(desc(ExitEvent.ts))
    )
    events = events_res.scalars().all()

    mismatches_30d = sum(
        1 for e in events
        if str(e.verdict) == "MISMATCH" and is_within_window(e.ts, window_30d)
    )

    event_items = [serialize_history_item(e) for e in events]
    emp_resp = serialize_employee(emp, mismatches_30d)

    return EmployeeHistoryResponse(
        employee=emp_resp,
        totalTraversals=len(events),
        mismatches30d=mismatches_30d,
        repeatOffenderRisk=mismatches_30d >= 3,
        events=event_items,
    )


@router.post("/{employee_id}/photo", response_model=EmployeePhotoResponse, status_code=200)
async def upload_employee_photo(
    employee_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
):
    """Enrolls an employee's face photo for biometric Known/Unknown person authentication."""
    result = await session.execute(select(Employee).where(Employee.employee_id == employee_id))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found")

    content_type = (file.content_type or "").lower()
    filename = (file.filename or "").lower()
    valid_ext = any(filename.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"])
    if not (content_type.startswith("image/") or valid_ext):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a JPEG, PNG, or WebP image.")

    image_bytes = await file.read()
    if len(image_bytes) < 100:
        raise HTTPException(status_code=400, detail="Uploaded photo is empty or corrupted.")

    # Extract 512-d ArcFace embedding
    embedding = FaceRecognitionService.extract_face_embedding(image_bytes)
    if not embedding:
        raise HTTPException(
            status_code=422,
            detail="No detectable face found in uploaded photo. Please ensure the subject is facing the camera under adequate lighting with clear visibility."
        )

    old_had_face = bool(emp.face_embedding is not None and len(emp.face_embedding) > 0)
    emp.face_embedding = embedding
    emp.embedding_updated_at = get_utc_now()
    session.add(emp)
    await session.flush()

    await log_audit_entry(
        session=session,
        entity_type="EMPLOYEE",
        entity_id=str(emp.employee_id),
        action="ENROLL_FACE_PHOTO",
        actor_type="USER",
        before_state={"has_face_enrolled": old_had_face},
        after_state={"has_face_enrolled": True, "embedding_dimension": len(embedding)},
    )
    await session.commit()

    # Invalidate cached roster in camera worker so live camera feeds immediately recognize this employee
    try:
        from src.engine.camera_worker import camera_worker
        camera_worker._cached_roster = []
        camera_worker._cached_roster_ts = 0.0
    except Exception as e:
        logger.debug("Could not invalidate camera worker roster cache: %s", e)

    return EmployeePhotoResponse(
        employeeId=str(emp.employee_id),
        name=str(emp.name),
        hasFaceEnrolled=True,
        embeddingDimension=len(embedding),
        message=f"Biometric face profile successfully enrolled for {emp.name}. Live cameras will now authenticate this person as Known.",
    )


@router.delete("/{employee_id}/photo", status_code=200)
async def delete_employee_photo(
    employee_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Removes an employee's enrolled face profile."""
    result = await session.execute(select(Employee).where(Employee.employee_id == employee_id))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found")

    had_face = bool(emp.face_embedding is not None and len(emp.face_embedding) > 0)
    emp.face_embedding = None
    emp.embedding_updated_at = None
    session.add(emp)
    await session.flush()

    await log_audit_entry(
        session=session,
        entity_type="EMPLOYEE",
        entity_id=str(emp.employee_id),
        action="DELETE_FACE_PHOTO",
        actor_type="USER",
        before_state={"has_face_enrolled": had_face},
        after_state={"has_face_enrolled": False},
    )
    await session.commit()

    # Invalidate cached roster in camera worker
    try:
        from src.engine.camera_worker import camera_worker
        camera_worker._cached_roster = []
        camera_worker._cached_roster_ts = 0.0
    except Exception as e:
        logger.debug("Could not invalidate camera worker roster cache: %s", e)

    return {"success": True, "message": f"Biometric face profile removed for {emp.name}."}


