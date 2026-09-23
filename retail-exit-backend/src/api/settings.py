"""System Threshold & Operational Settings Endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.session import get_db
from src.db.models import ThresholdConfig, get_utc_now
from src.db.audit import log_audit_entry
from src.schemas.settings import ThresholdConfigSchema
from src.cache import cache_service
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/thresholds", response_model=ThresholdConfigSchema)
async def get_thresholds(session: AsyncSession = Depends(get_db)):
    """Retrieves the store's active severity threshold configuration with cached reads."""
    cache_key = "settings:thresholds"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return ThresholdConfigSchema(**cached)

    result = await session.execute(select(ThresholdConfig).limit(1))
    cfg = result.scalar_one_or_none()

    if not cfg:
        # Default fallback
        resp = ThresholdConfigSchema()
        await cache_service.set(cache_key, resp.model_dump(), ttl_seconds=600)
        return resp

    resp = ThresholdConfigSchema(
        lowSeverityThreshold=cfg.low_severity_threshold,
        medSeverityThreshold=cfg.med_severity_threshold,
        highSeverityThreshold=cfg.high_severity_threshold,
        repeatOffenderThreshold=cfg.repeat_offender_count_trigger,
        repeatOffenderWindowDays=cfg.repeat_offender_window_days,
        audioAlarmEnabled=cfg.audio_alarm_enabled,
        turnstileAutoLockOnHigh=cfg.turnstile_auto_lock_on_high,
    )
    await cache_service.set(cache_key, resp.model_dump(), ttl_seconds=600)
    return resp


@router.put("/thresholds", response_model=ThresholdConfigSchema)
async def update_thresholds(
    body: ThresholdConfigSchema,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Updates operational thresholds and writes an immutable audit log row."""
    result = await session.execute(select(ThresholdConfig).limit(1))
    cfg = result.scalar_one_or_none()

    if not cfg:
        cfg = ThresholdConfig(config_id="cfg_default")
        session.add(cfg)

    before_state = {
        "low": cfg.low_severity_threshold,
        "med": cfg.med_severity_threshold,
        "high": cfg.high_severity_threshold,
        "repeat_trigger": cfg.repeat_offender_count_trigger,
    }

    cfg.low_severity_threshold = body.lowSeverityThreshold
    cfg.med_severity_threshold = body.medSeverityThreshold
    cfg.high_severity_threshold = body.highSeverityThreshold
    cfg.repeat_offender_count_trigger = body.repeatOffenderThreshold
    cfg.repeat_offender_window_days = body.repeatOffenderWindowDays
    cfg.audio_alarm_enabled = body.audioAlarmEnabled
    cfg.turnstile_auto_lock_on_high = body.turnstileAutoLockOnHigh
    cfg.updated_at = get_utc_now()

    await log_audit_entry(
        session=session,
        entity_type="CONFIG",
        entity_id=cfg.config_id,
        action="UPDATE_THRESHOLDS",
        actor_type="USER",
        before_state=before_state,
        after_state=body.model_dump(),
    )
    await session.commit()
    await cache_service.invalidate("settings:thresholds")

    return body


@router.post("/reset-database")
async def reset_database(
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Purges all operational records (products, employees, cameras, lanes, events, alerts)
    and restores the database to a clean zero-state baseline."""
    from sqlalchemy import delete
    from src.db.models import (
        TripwireCrossingEvent,
        VirtualTripwireConfig,
        DispatchSession,
        PackageDefinition,
        Material,
        ExitEventLineItem,
        VisionDetection,
        RfidRead,
        WeightReading,
        FaceMatchAttempt,
        AlarmDispatch,
        Alert,
        Invoice,
        ExitEvent,
        CameraHeartbeat,
        Camera,
        Lane,
        Employee,
        Product,
        AuditLog,
        CameraPairingToken,
        StaticImageDetection,
        PersonAppearanceSummary,
    )
    from src.realtime.hub import ws_hub

    # Delete in FK dependency order
    await session.execute(delete(TripwireCrossingEvent))
    await session.execute(delete(VirtualTripwireConfig))
    await session.execute(delete(DispatchSession))
    await session.execute(delete(PackageDefinition))
    await session.execute(delete(Material))
    await session.execute(delete(PersonAppearanceSummary))
    await session.execute(delete(CameraPairingToken))
    await session.execute(delete(StaticImageDetection))
    await session.execute(delete(ExitEventLineItem))
    await session.execute(delete(VisionDetection))
    await session.execute(delete(RfidRead))
    await session.execute(delete(WeightReading))
    await session.execute(delete(FaceMatchAttempt))
    await session.execute(delete(AlarmDispatch))
    await session.execute(delete(Alert))
    await session.execute(delete(Invoice))
    await session.execute(delete(ExitEvent))
    await session.execute(delete(CameraHeartbeat))
    await session.execute(delete(Camera))
    await session.execute(delete(Lane))
    await session.execute(delete(Employee))
    await session.execute(delete(Product))
    await session.execute(delete(AuditLog))
    await session.commit()

    await cache_service.clear()
    await ws_hub.broadcast_event("database_reset", {"status": "ZERO_STATE"})
    return {"status": "SUCCESS", "message": "Database purged to pure zero-state baseline."}


