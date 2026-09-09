"""Exit Events Query Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional

from src.db.session import get_db
from src.db.models import ExitEvent, ExitEventLineItem, Employee, Invoice, Product
from src.schemas.events import ExitEventResponse, ExitEventDetailResponse, EventLineItemSchema

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
    )

