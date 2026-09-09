"""Baseline Configuration Initialization

Ensures standard store and threshold_config baseline exists without any seed
or mock data for products, employees, cameras, lanes, or events.
Strictly adheres to Part I Zero-Hardcode policy.
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

