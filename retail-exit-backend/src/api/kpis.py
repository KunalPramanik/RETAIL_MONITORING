"""Live KPI Strip Endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.db.session import get_db
from src.db.models import ExitEvent, Alert, Lane, Camera
from src.schemas.kpis import LiveKPIResponse

router = APIRouter(prefix="/kpis", tags=["KPIs"])


@router.get("/live", response_model=LiveKPIResponse)
async def get_live_kpis(session: AsyncSession = Depends(get_db)):
    """Computes real-time loss prevention and exit lane telemetry metrics."""
    # 1. Throughput Units (sum of consensus_units from actual exit events)
    res_units = await session.execute(select(func.coalesce(func.sum(ExitEvent.consensus_units), 0)))
    today_throughput = int(res_units.scalar_one())

    # 2. Open alerts by severity
    res_alerts = await session.execute(
        select(Alert.severity, func.count(Alert.alert_id))
        .where(Alert.status.in_(["OPEN", "ACKNOWLEDGED"]))
        .group_by(Alert.severity)
    )
    alert_counts = {"high": 0, "medium": 0, "low": 0}
    for sev, count in res_alerts.all():
        sev_key = sev.lower()
        if sev_key in alert_counts:
            alert_counts[sev_key] = count

    total_open_alerts = sum(alert_counts.values())

    # 3. Consensus accuracy rate (% PASS events)
    res_total_events = await session.execute(select(func.count(ExitEvent.event_id)))
    total_events = res_total_events.scalar_one()

    if total_events > 0:
        res_pass = await session.execute(
            select(func.count(ExitEvent.event_id)).where(ExitEvent.verdict == "PASS")
        )
        pass_count = res_pass.scalar_one()
        consensus_rate = round((pass_count / total_events) * 100.0, 1)
    else:
        consensus_rate = 100.0

    # 4. Lane status
    res_lanes = await session.execute(select(Lane))
    all_lanes = res_lanes.scalars().all()
    active_lanes = [l for l in all_lanes if str(l.status) == "ONLINE"]

    # 5. Camera fleet status
    res_cams = await session.execute(select(Camera).where(Camera.removed_at.is_(None)))
    all_cams = res_cams.scalars().all()
    online_cams = [c for c in all_cams if str(c.status) == "ONLINE"]

    return LiveKPIResponse(
        todayThroughputUnits=today_throughput,
        openAlertsCount=total_open_alerts,
        openAlertsBySeverity=alert_counts,
        consensusAccuracyRate=consensus_rate,
        activeLanesCount=len(active_lanes),
        totalLanesCount=len(all_lanes),
        camerasOnlineCount=len(online_cams),
        camerasTotalCount=len(all_cams),
    )
