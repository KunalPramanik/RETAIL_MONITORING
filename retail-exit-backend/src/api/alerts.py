"""Alert Management and Incident Resolution Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional, Any

from src.db.session import get_db
from src.db.models import Alert, get_utc_now
from src.db.audit import log_audit_entry
from src.schemas.alerts import AlertResponse, AcknowledgeAlertRequest, ResolveAlertRequest
from src.realtime.hub import ws_hub

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def serialize_alert(a: Any) -> AlertResponse:
    """Serializes an Alert ORM instance to a typed AlertResponse."""
    return AlertResponse(
        alertId=str(a.alert_id),
        eventId=str(a.event_id),
        alertType=str(a.alert_type),
        severity=str(a.severity),
        deltaUnits=int(a.delta_units) if a.delta_units is not None else 0,
        createdAt=a.created_at.isoformat() if a.created_at else "",
        status=str(a.status),
        resolvedBy=str(a.resolved_by) if a.resolved_by else None,
        resolutionNote=str(a.resolution_note) if a.resolution_note else None,
    )


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Lists alerts with status, severity filters, and bounded pagination. Open HIGH alerts are prioritized."""
    query = select(Alert).order_by(desc(Alert.created_at))

    if status and status != "ALL":
        query = query.where(Alert.status == status)
    if severity and severity != "ALL":
        query = query.where(Alert.severity == severity)

    result = await session.execute(query)
    alerts = result.scalars().all()

    # Sort in memory: Open/Acked on top, then HIGH severity, then newest timestamp
    severity_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    sorted_alerts = sorted(
        alerts,
        key=lambda a: (
            1 if str(a.status) in ["OPEN", "ACKNOWLEDGED"] else 0,
            severity_order.get(str(a.severity), 0),
            a.created_at.timestamp() if getattr(a, "created_at", None) is not None else 0,
        ),
        reverse=True,
    )

    paginated_alerts = sorted_alerts[offset : offset + limit]
    return [serialize_alert(a) for a in paginated_alerts]


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    body: AcknowledgeAlertRequest,
    session: AsyncSession = Depends(get_db),
):
    """Acknowledges an open alert and writes an immutable audit log entry."""
    result = await session.execute(select(Alert).where(Alert.alert_id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

    a_any: Any = alert
    before_state = {"status": str(a_any.status), "resolved_by": str(a_any.resolved_by) if a_any.resolved_by else None}

    a_any.status = "ACKNOWLEDGED"
    a_any.resolved_by = body.acknowledgedBy

    # Write transactional audit log
    await log_audit_entry(
        session=session,
        entity_type="ALERT",
        entity_id=alert_id,
        action="ACKNOWLEDGE_ALERT",
        actor_type="USER",
        actor_id=body.acknowledgedBy,
        before_state=before_state,
        after_state={"status": "ACKNOWLEDGED", "acknowledged_by": body.acknowledgedBy},
    )

    await session.commit()

    resp = serialize_alert(alert)

    # Real-time WebSocket fan-out
    await ws_hub.broadcast_event("alert_status_changed", resp.model_dump())
    return resp


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: str,
    body: ResolveAlertRequest,
    session: AsyncSession = Depends(get_db),
):
    """Resolves an alert with mandatory resolution notes and logs an immutable audit trail."""
    if not body.resolutionNote or len(body.resolutionNote.strip()) < 5:
        raise HTTPException(status_code=400, detail="Mandatory resolution note (minimum 5 characters) is required for audit integrity")

    result = await session.execute(select(Alert).where(Alert.alert_id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

    now = get_utc_now()
    a_any: Any = alert
    before_state = {"status": str(a_any.status), "note": str(a_any.resolution_note) if a_any.resolution_note else None}

    a_any.status = "RESOLVED"
    a_any.resolution_note = body.resolutionNote.strip()
    a_any.resolved_by = body.resolvedBy
    a_any.resolved_at = now

    # Write transactional audit log
    await log_audit_entry(
        session=session,
        entity_type="ALERT",
        entity_id=alert_id,
        action="RESOLVE_ALERT",
        actor_type="USER",
        actor_id=body.resolvedBy,
        before_state=before_state,
        after_state={
            "status": "RESOLVED",
            "resolution_note": a_any.resolution_note,
            "resolved_by": a_any.resolved_by,
        },
    )

    await session.commit()

    resp = serialize_alert(alert)

    # Real-time WebSocket fan-out
    await ws_hub.broadcast_event("alert_status_changed", resp.model_dump())
    return resp

