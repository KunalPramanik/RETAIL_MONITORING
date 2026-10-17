"""Employee Badge Registry & Carrier History Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional, Any, Dict, Tuple
from datetime import datetime, timezone, timedelta
import logging
import uuid

from src.db.session import get_db
from src.db.models import (
    Employee,
    ExitEvent,
    ExitEventLineItem,
    Lane,
    Product,
    TripwireCrossingEvent,
    get_utc_now,
)
from src.db.audit import log_audit_entry
from src.schemas.employees import (
    EmployeeResponse,
    EmployeeCreate,
    EmployeeHistoryResponse,
    EmployeeHistoryItem,
    EmployeePhotoResponse,
    EmployeeMovementSummaryResponse,
    EmployeeMovementRecord,
    MaterialMovementItem,
)
from src.ml.face_recognition.face_service import FaceRecognitionService

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
    code = emp.employee_code if getattr(emp, "employee_code", None) else f"EMP-{str(emp.employee_id)[:6].upper()}"
    return EmployeeResponse(
        employeeId=str(emp.employee_id),
        employeeCode=code,
        name=str(emp.name),
        role=str(emp.role),
        rfidBadgeId=str(emp.rfid_badge_id),
        shiftId=str(emp.shift_id) if emp.shift_id else None,
        activeFlag=bool(emp.active_flag),
        mismatchCount30d=mismatch_count,
        hasFaceEnrolled=has_face,
        hasPhoto=has_face,
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
    rfid = (body.rfidBadgeId or "").strip()
    if not rfid:
        rfid = f"RFID-{uuid.uuid4().hex[:8].upper()}"
    else:
        existing = await session.execute(
            select(Employee).where(Employee.rfid_badge_id == rfid)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Badge ID '{rfid}' already assigned")

    # Generate atomic next employee code EMP-XXXXXX
    codes_res = await session.execute(
        select(Employee.employee_code).where(Employee.employee_code.isnot(None))
    )
    existing_codes = codes_res.scalars().all()
    max_num = 0
    for c in existing_codes:
        if c and c.startswith("EMP-"):
            try:
                num = int(c.split("-")[1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
    
    if max_num == 0:
        count_res = await session.execute(select(func.count(Employee.employee_id)))
        cnt = count_res.scalar_one_or_none() or 0
        next_num = cnt + 1
    else:
        next_num = max_num + 1

    candidate_code = f"EMP-{next_num:06d}"
    while True:
        dup = await session.execute(select(Employee).where(Employee.employee_code == candidate_code))
        if not dup.scalar_one_or_none():
            break
        next_num += 1
        candidate_code = f"EMP-{next_num:06d}"

    emp = Employee(
        employee_code=candidate_code,
        name=body.name,
        role=body.role,
        rfid_badge_id=rfid,
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
    from src.core.config import settings
    if not settings.biometric.enabled:
        raise HTTPException(
            status_code=403,
            detail="Biometric face enrollment is disabled by default (SECOPS_BIOMETRIC_ENABLED=false). Legal review and license authorization required.",
        )

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


@router.post("/{employee_id}/face-360", response_model=EmployeePhotoResponse, status_code=200)
async def upload_employee_360_faces(
    employee_id: str,
    files: List[UploadFile] = File(...),
    session: AsyncSession = Depends(get_db),
):
    from src.core.config import settings
    if not settings.biometric.enabled:
        raise HTTPException(
            status_code=403,
            detail="Biometric face enrollment is disabled by default (SECOPS_BIOMETRIC_ENABLED=false). Legal review and license authorization required.",
        )

    result = await session.execute(select(Employee).where(Employee.employee_id == employee_id))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found")

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Please upload at least one face angle photo for 360 enrollment.")

    image_bytes_list = []
    for f in files:
        b = await f.read()
        if len(b) >= 100:
            image_bytes_list.append(b)

    if not image_bytes_list:
        raise HTTPException(status_code=400, detail="Uploaded photo files are empty or unreadable.")

    embedding = FaceRecognitionService.extract_360_face_embedding(image_bytes_list)
    if not embedding:
        raise HTTPException(
            status_code=422,
            detail="No detectable faces found across the uploaded 360 images. Please ensure subject's face is clearly visible."
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
        action="ENROLL_360_FACE_PHOTOS",
        actor_type="USER",
        before_state={"has_face_enrolled": old_had_face},
        after_state={"has_face_enrolled": True, "angles_processed": len(image_bytes_list), "embedding_dimension": len(embedding)},
    )
    await session.commit()

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
        message=f"360-degree multi-angle biometric profile successfully enrolled for {emp.name} ({len(image_bytes_list)} angles processed).",
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
    from src.core.encryption import erase_biometric_embedding
    erase_biometric_embedding(emp)
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


@router.get("/{employee_id}/movement", response_model=EmployeeMovementSummaryResponse)
async def get_employee_movement(
    employee_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves multi-camera movement tracking history (entry/exit counts and materials handled) for an employee."""
    is_unknown = employee_id.lower() in ("unknown", "unverified")

    if is_unknown:
        emp_name = "Unknown Personnel"
        events_filter = ExitEvent.employee_id.is_(None)
        tw_filter = TripwireCrossingEvent.matched_employee_id.is_(None)
    else:
        result = await session.execute(select(Employee).where(Employee.employee_id == employee_id))
        emp = result.scalar_one_or_none()
        if not emp:
            raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found")
        emp_name = emp.name
        events_filter = (ExitEvent.employee_id == employee_id)
        tw_filter = (TripwireCrossingEvent.matched_employee_id == employee_id)

    # Fetch lanes for human-readable labels
    lanes_res = await session.execute(select(Lane))
    lanes_map = {l.lane_id: l.label for l in lanes_res.scalars().all()}

    # Fetch exit events
    events_res = await session.execute(
        select(ExitEvent).where(events_filter).order_by(desc(ExitEvent.ts)).limit(100)
    )
    events = events_res.scalars().all()

    # Pre-fetch line items and products for these events
    event_ids = [e.event_id for e in events]
    line_items_by_event: Dict[str, List[Tuple[ExitEventLineItem, Product]]] = {}
    if event_ids:
        li_res = await session.execute(
            select(ExitEventLineItem, Product)
            .join(Product, ExitEventLineItem.product_id == Product.product_id)
            .where(ExitEventLineItem.event_id.in_(event_ids))
        )
        for li, prod in li_res.all():
            line_items_by_event.setdefault(li.event_id, []).append((li, prod))

    # Also fetch tripwire crossings
    tw_res = await session.execute(
        select(TripwireCrossingEvent).where(tw_filter).order_by(desc(TripwireCrossingEvent.timestamp)).limit(50)
    )
    crossings = tw_res.scalars().all()

    total_entries = 0
    total_exits = 0
    materials_summary: Dict[str, Dict[str, int]] = {}
    movement_records: List[EmployeeMovementRecord] = []

    for ev in events:
        notes_str = str(ev.notes or "").upper()
        if "ENTRY" in notes_str or "INBOUND" in notes_str:
            direction = "ENTRY"
            total_entries += 1
        else:
            direction = "EXIT"
            total_exits += 1

        cam_label = lanes_map.get(ev.lane_id, f"Lane {ev.lane_id}")
        carried: List[MaterialMovementItem] = []

        # From line items
        ev_items = line_items_by_event.get(ev.event_id, [])
        for li, prod in ev_items:
            qty = li.cases_qty if li.cases_qty > 0 else li.units_qty
            carried.append(MaterialMovementItem(
                materialName=prod.name,
                skuCode=prod.sku_code,
                quantity=qty,
                direction=direction,
            ))
            mat_stat = materials_summary.setdefault(prod.name, {"in": 0, "out": 0, "net": 0})
            if direction == "ENTRY":
                mat_stat["in"] += qty
                mat_stat["net"] += qty
            else:
                mat_stat["out"] += qty
                mat_stat["net"] -= qty

        # Fallback if line items empty but cases/units detected
        if not carried and (ev.cases_detected > 0 or ev.units_detected > 0):
            qty = ev.cases_detected if ev.cases_detected > 0 else ev.units_detected
            carried.append(MaterialMovementItem(
                materialName="General Inventory Cargo",
                skuCode="CARGO-GEN",
                quantity=qty,
                direction=direction,
            ))
            mat_stat = materials_summary.setdefault("General Inventory Cargo", {"in": 0, "out": 0, "net": 0})
            if direction == "ENTRY":
                mat_stat["in"] += qty
                mat_stat["net"] += qty
            else:
                mat_stat["out"] += qty
                mat_stat["net"] -= qty

        movement_records.append(EmployeeMovementRecord(
            eventId=str(ev.event_id),
            timestamp=ev.ts.isoformat() if ev.ts else "",
            laneId=str(ev.lane_id),
            cameraName=cam_label,
            direction=direction,
            personIdentity=emp_name,
            isKnown=not is_unknown,
            materialsCarried=carried,
            casesDetected=int(ev.cases_detected or 0),
            unitsDetected=int(ev.units_detected or 0),
            snapshotUrl=ev.snapshot_url,
        ))

    # Add tripwire crossings if any
    for cr in crossings:
        direction = cr.direction if cr.direction in ("ENTRY", "EXIT") else "TRAVERSAL"
        if direction == "ENTRY":
            total_entries += 1
        elif direction == "EXIT":
            total_exits += 1

        cam_label = lanes_map.get(cr.camera_id, f"Gate {cr.camera_id}")
        movement_records.append(EmployeeMovementRecord(
            eventId=str(cr.crossing_id),
            timestamp=cr.timestamp.isoformat() if cr.timestamp else "",
            laneId=str(cr.camera_id),
            cameraName=cam_label,
            direction=direction,
            personIdentity=emp_name,
            isKnown=not is_unknown,
            materialsCarried=[],
            casesDetected=0,
            unitsDetected=0,
            snapshotUrl=cr.snapshot_url,
        ))

    # Sort all movements chronologically descending
    movement_records.sort(key=lambda r: r.timestamp, reverse=True)
    last_seen_cam = movement_records[0].cameraName if movement_records else None
    last_seen_ts = movement_records[0].timestamp if movement_records else None

    return EmployeeMovementSummaryResponse(
        employeeId=employee_id,
        name=emp_name,
        totalEntries=total_entries,
        totalExits=total_exits,
        totalTraversals=len(movement_records),
        lastSeenCamera=last_seen_cam,
        lastSeenTimestamp=last_seen_ts,
        materialsHandledSummary=materials_summary,
        movements=movement_records,
    )


