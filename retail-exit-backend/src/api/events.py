"""Exit Events Query Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional

from src.db.session import get_db
from datetime import timedelta
from src.db.models import ExitEvent, ExitEventLineItem, Employee, Invoice, Product, PersonAppearanceSummary, Lane, get_utc_now
from src.schemas.events import (
    ExitEventResponse,
    ExitEventDetailResponse,
    EventLineItemSchema,
    EmployeeVerificationDetail,
    AppearanceSummaryResponse,
)

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=List[ExitEventResponse])
async def list_events(
    lane_id: Optional[str] = Query(None, alias="laneId"),
    verdict: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Lists historical exit events with optional multi-facet filtering."""
    query = (
        select(ExitEvent)
        .options(selectinload(ExitEvent.line_items))
        .order_by(desc(ExitEvent.ts))
    )

    if lane_id and lane_id != "ALL":
        query = query.where(ExitEvent.lane_id == lane_id)
    if verdict and verdict != "ALL":
        query = query.where(ExitEvent.verdict == verdict)
    if severity and severity != "ALL":
        query = query.where(ExitEvent.severity == severity)

    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    events = result.scalars().all()

    response = []
    for ev in events:
        line_items_data = [
            EventLineItemSchema(
                productId=li.product_id,
                casesQty=li.cases_qty,
                unitsQty=li.units_qty,
            )
            for li in ev.line_items
        ]
        response.append(
            ExitEventResponse(
                eventId=ev.event_id,
                timestamp=ev.ts.isoformat(),
                laneId=ev.lane_id,
                employeeId=ev.employee_id,
                casesDetected=ev.cases_detected,
                unitsDetected=ev.units_detected,
                visionCount=ev.vision_count,
                rfidCount=ev.rfid_count,
                weightKg=float(ev.weight_kg) if ev.weight_kg is not None else 0.0,
                consensusUnits=ev.consensus_units,
                consensusMethod=ev.consensus_method,
                invoiceId=ev.invoice_id,
                declaredUnits=ev.declared_units,
                deltaUnits=ev.delta_units,
                verdict=ev.verdict,
                severity=ev.severity,
                lineItems=line_items_data,
                snapshotUrl=ev.snapshot_url,
                clipUrl=ev.clip_url,
                notes=ev.notes,
            )
        )
    return response


@router.get("/movement-monitor")
async def get_movement_monitor(
    limit: int = Query(25, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Returns individual item movement progress vs authorization bill items.
    
    Enforces Section 7, 8, 9, 11, 18 of the V8 Master Prompt Addendum.
    Tracks Person, Bill ID, Product, Authorized Quantity, Actual Taken, Progress, and Status.
    """
    stmt = (
        select(ExitEvent)
        .options(
            selectinload(ExitEvent.line_items).selectinload(ExitEventLineItem.product),
            selectinload(ExitEvent.invoice),
            selectinload(ExitEvent.employee),
            selectinload(ExitEvent.lane),
        )
        .order_by(desc(ExitEvent.ts))
        .limit(limit)
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    monitor_records = []
    for ev in events:
        person_name = ev.employee.name if ev.employee else (
            ev.notes.split("Person:")[1].split()[0] if ev.notes and "Person:" in ev.notes else "Authorized Handler"
        )
        bill_num = ev.invoice.invoice_number if ev.invoice else (f"INV-{ev.event_id[:6].upper()}")

        prod_name = "Industrial Goods"
        sku_code = "MAT-GEN"
        auth_qty = ev.declared_units or (ev.units_detected + abs(ev.delta_units) if ev.delta_units else ev.units_detected or 20)
        actual_qty = ev.units_detected or ev.consensus_units or 0

        if ev.line_items and len(ev.line_items) > 0:
            first_item = ev.line_items[0]
            if first_item.product:
                prod_name = first_item.product.name
                sku_code = first_item.product.sku_code
                if not auth_qty:
                    auth_qty = first_item.units_qty

        remaining_qty = max(0, auth_qty - actual_qty)
        progress_pct = round((actual_qty / max(1, auth_qty)) * 100, 1)

        # Determine status per Section 11 of Addendum
        if ev.verdict == "PASS" or (actual_qty == auth_qty and auth_qty > 0):
            status = "CORRECT"
        elif ev.verdict == "MISMATCH":
            status = "WRONG_ITEM"
        elif actual_qty > auth_qty:
            status = "OVER_QUANTITY"
        elif actual_qty < auth_qty:
            status = "UNDER_QUANTITY"
        elif ev.verdict == "REVIEW_REQUIRED":
            status = "COUNT_UNCERTAIN"
        else:
            status = "CORRECT"

        monitor_records.append({
            "movementId": f"MOV-{ev.event_id[:8]}",
            "eventId": ev.event_id,
            "timestamp": ev.ts.strftime("%H:%M:%S") if ev.ts else get_utc_now().strftime("%H:%M:%S"),
            "personName": person_name,
            "billNumber": bill_num,
            "productName": prod_name,
            "skuCode": sku_code,
            "authorizedQty": auth_qty,
            "actualQty": actual_qty,
            "remainingQty": remaining_qty,
            "progressPct": progress_pct,
            "status": status,
            "verdict": ev.verdict,
            "cameraLabel": ev.lane.label if ev.lane else (ev.lane_id or "Exit Gate 1"),
            "snapshotUrl": ev.snapshot_url or "/snapshots/preview_CAM-01.jpg",
            "notes": ev.notes or f"Traversing via {ev.lane_id or 'Gate'}",
        })

    return monitor_records


@router.get("/{event_id}", response_model=ExitEventDetailResponse)
async def get_event_detail(
    event_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves comprehensive forensic detail for a specific exit event."""
    query = (
        select(ExitEvent)
        .options(
            selectinload(ExitEvent.line_items),
            selectinload(ExitEvent.vision_detections),
            selectinload(ExitEvent.rfid_reads),
            selectinload(ExitEvent.weight_readings),
            selectinload(ExitEvent.face_matches),
            selectinload(ExitEvent.employee),
            selectinload(ExitEvent.invoice),
            selectinload(ExitEvent.appearance_summary),
        )
        .where(ExitEvent.event_id == event_id)
    )
    result = await session.execute(query)
    ev = result.scalar_one_or_none()

    if not ev:
        raise HTTPException(status_code=404, detail=f"Exit event '{event_id}' not found")

    line_items_data = [
        EventLineItemSchema(
            productId=li.product_id,
            casesQty=li.cases_qty,
            unitsQty=li.units_qty,
        )
        for li in ev.line_items
    ]

    raw_vision = [
        {
            "detectionId": vd.detection_id,
            "bbox": vd.bbox,
            "classLabel": vd.class_label,
            "productId": vd.product_id,
            "confidence": float(vd.confidence),
            "modelVersion": vd.model_version,
        }
        for vd in ev.vision_detections
    ]

    raw_rfid = [
        {
            "readId": rr.read_id,
            "epcTag": rr.epc_tag,
            "antennaId": rr.antenna_id,
            "rssi": float(rr.rssi) if rr.rssi else None,
        }
        for rr in ev.rfid_reads
    ]

    raw_weight = [
        {
            "readingId": wr.reading_id,
            "sensorId": wr.sensor_id,
            "weightKg": float(wr.weight_kg),
        }
        for wr in ev.weight_readings
    ]

    face_decision = ev.face_matches[0].decision if ev.face_matches else None

    # 1. Verified Employee Detail Display
    verified_emp = None
    cutoff_30d = get_utc_now() - timedelta(days=30)
    if face_decision == "MATCHED" and ev.employee:
        mismatches_res = await session.execute(
            select(ExitEvent.event_id)
            .where(ExitEvent.employee_id == ev.employee.employee_id)
            .where(ExitEvent.verdict == "MISMATCH")
            .where(ExitEvent.ts >= cutoff_30d)
        )
        mismatch_count_30d = len(mismatches_res.scalars().all())

        raw_sim = float(ev.face_matches[0].similarity) if ev.face_matches else (
            float(ev.employee_match_confidence) if ev.employee_match_confidence is not None else 1.0
        )
        verified_emp = EmployeeVerificationDetail(
            employeeId=ev.employee.employee_id,
            name=ev.employee.name,
            role=ev.employee.role,
            shift=str(ev.employee.shift_id or "MORNING"),
            rfidBadgeId=ev.employee.rfid_badge_id,
            activeFlag=bool(ev.employee.active_flag),
            similarity=raw_sim,
            mismatchCount30d=mismatch_count_30d,
        )

    # 2. Unverified Person Appearance Summary Display
    appearance_data = None
    if ev.appearance_summary:
        pas = ev.appearance_summary
        sighting_count = 1
        if pas.reid_cluster_id:
            count_res = await session.execute(
                select(PersonAppearanceSummary.summary_id)
                .where(PersonAppearanceSummary.reid_cluster_id == pas.reid_cluster_id)
                .where(PersonAppearanceSummary.created_at >= cutoff_30d)
            )
            sighting_count = max(1, len(count_res.scalars().all()))

        appearance_data = AppearanceSummaryResponse(
            summaryId=pas.summary_id,
            clothingTopColor=pas.clothing_top_color,
            clothingBottomColor=pas.clothing_bottom_color,
            buildCategory=pas.build_category,
            buildConfidence=float(pas.build_confidence),
            accessories=pas.accessories or [],
            accessoriesConfidence=pas.accessories_confidence or {},
            modelVersion=pas.model_version,
            recentSightingsCount=sighting_count,
            reidClusterId=pas.reid_cluster_id,
            createdAt=pas.created_at.isoformat(),
        )

    return ExitEventDetailResponse(
        eventId=ev.event_id,
        timestamp=ev.ts.isoformat(),
        laneId=ev.lane_id,
        employeeId=ev.employee_id,
        employeeName=ev.employee.name if ev.employee else None,
        employeeRole=ev.employee.role if ev.employee else None,
        employeeMatchConfidence=float(ev.employee_match_confidence) if ev.employee_match_confidence else None,
        casesDetected=ev.cases_detected,
        unitsDetected=ev.units_detected,
        visionCount=ev.vision_count,
        rfidCount=ev.rfid_count,
        weightKg=float(ev.weight_kg) if ev.weight_kg is not None else 0.0,
        consensusUnits=ev.consensus_units,
        consensusMethod=ev.consensus_method,
        invoiceId=ev.invoice_id,
        invoiceNumber=ev.invoice.invoice_number if ev.invoice else None,
        carrierName=ev.invoice.carrier_name if ev.invoice else None,
        declaredUnits=ev.declared_units,
        deltaUnits=ev.delta_units,
        verdict=ev.verdict,
        severity=ev.severity,
        lineItems=line_items_data,
        snapshotUrl=ev.snapshot_url,
        clipUrl=ev.clip_url,
        notes=ev.notes,
        rawVisionDetections=raw_vision,
        rawRfidReads=raw_rfid,
        rawWeightReadings=raw_weight,
        faceMatchDecision=face_decision,
        verifiedEmployee=verified_emp,
        appearanceSummary=appearance_data,
    )


