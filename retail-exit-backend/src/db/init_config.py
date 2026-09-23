"""Baseline Configuration Initialization

Ensures standard store and threshold_config baseline exists without any seed
or mock data for products, employees, cameras, lanes, or events.
Guarantees a completely dynamic operational data architecture.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from src.db.models import Store, ThresholdConfig, Shift, get_utc_now

logger = logging.getLogger("secops.init_config")


async def init_baseline_configuration(session: AsyncSession):
    """Initializes only the baseline Store and ThresholdConfig rows if not present."""
    # Check if default store exists
    res = await session.execute(select(Store).filter(Store.store_id == "store_0402"))
    store = res.scalar_one_or_none()
    if not store:
        store = Store(
            store_id="store_0402",
            name="SuperStore #402 - Metro Central",
            address="742 Evergreen Terrace, Sector 4",
            timezone="America/New_York",
        )
        session.add(store)
        await session.flush()
        logger.info("Initialized baseline store: %s", store.store_id)

    # Check if baseline shifts exist
    shifts_res = await session.execute(select(Shift).limit(1))
    if not shifts_res.scalar_one_or_none():
        shifts = [
            Shift(shift_id="shift_morning", label="Morning Shift A", starts_at="06:00:00", ends_at="14:30:00"),
            Shift(shift_id="shift_afternoon", label="Afternoon Shift B", starts_at="14:00:00", ends_at="22:30:00"),
            Shift(shift_id="shift_night", label="Night Shift C", starts_at="22:00:00", ends_at="06:30:00"),
        ]
        session.add_all(shifts)
        logger.info("Initialized standard shift schedules.")

    # Check if threshold_config exists
    cfg_res = await session.execute(select(ThresholdConfig).limit(1))
    if not cfg_res.scalar_one_or_none():
        cfg = ThresholdConfig(
            store_id=store.store_id,
            unit_tolerance=0,
            pct_tolerance=0.0,
            low_severity_threshold=1,
            med_severity_threshold=3,
            high_severity_threshold=6,
            repeat_offender_window_days=30,
            repeat_offender_count_trigger=3,
            camera_offline_alert_after_sec=60,
            turnstile_auto_lock_on_high=True,
            audio_alarm_enabled=True,
        )
        session.add(cfg)
        logger.info("Initialized baseline threshold configuration.")

    await session.commit()

    # Reconcile any duplicate physical cameras in the database
    await reconcile_duplicate_cameras(session)


async def reconcile_duplicate_cameras(session: AsyncSession):
    """Detects and reconciles any duplicate camera records for the same physical endpoint.
    
    Groups active cameras by normalized (ip_address, rtsp_path) or stream_url.
    Preserves the primary camera (prioritizing assigned lane, or earliest created)
    and soft-deletes duplicate rows with an immutable audit log entry.
    """
    from collections import defaultdict
    from src.db.models import Camera
    from src.db.audit import log_audit_entry

    res = await session.execute(select(Camera).where(Camera.removed_at.is_(None)))
    active_cams = res.scalars().all()
    if len(active_cams) < 2:
        return

    grouped = defaultdict(list)
    for c in active_cams:
        ip = (c.ip_address or "").strip().lower()
        path = (c.rtsp_path or "").strip().lower()
        stream = (c.stream_url or "").strip().lower()
        if ip and ip not in ("0", "1", "webcam"):
            key = f"ip:{ip}:{path}"
        elif stream:
            key = f"stream:{stream}"
        else:
            key = f"id:{c.camera_id}"
        grouped[key].append(c)

    now = get_utc_now()
    reconciled_any = False

    for key, cam_list in grouped.items():
        if len(cam_list) > 1:
            # Sort: first priority has lane_id assigned; secondary: earlier added_at
            cam_list.sort(key=lambda x: (1 if x.lane_id else 0, x.added_at or now), reverse=True)
            primary = cam_list[0]
            duplicates = cam_list[1:]

            for dup in duplicates:
                logger.warning(
                    "Reconciling duplicate camera row %s into primary %s for endpoint %s",
                    dup.camera_id, primary.camera_id, key
                )
                dup.removed_at = now
                dup.status = "OFFLINE"
                await log_audit_entry(
                    session=session,
                    entity_type="CAMERA",
                    entity_id=dup.camera_id,
                    action="RECONCILE_DUPLICATE_CAMERA",
                    actor_type="SYSTEM",
                    before_state={"camera_id": dup.camera_id, "status": dup.status, "lane_id": dup.lane_id},
                    after_state={
                        "camera_id": dup.camera_id,
                        "status": "OFFLINE",
                        "merged_into_camera_id": primary.camera_id,
                        "endpoint_key": key,
                        "reason": "Reconciled duplicate physical camera stream registration on startup",
                    },
                )
                reconciled_any = True

    if reconciled_any:
        await session.commit()
        logger.info("Successfully reconciled duplicate camera registrations.")

