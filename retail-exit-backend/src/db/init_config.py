from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import ThresholdConfig, AppUser, Store
from src.security import get_password_hash
import uuid

async def init_baseline_configuration(session: AsyncSession):
    # 1. Ensure baseline Store exists
    store_res = await session.execute(select(Store).limit(1))
    store = store_res.scalars().first()
    if not store:
        store = Store(
            store_id=str(uuid.uuid4()),
            name="Main Retail & Warehouse Exit Station",
            address="Exit Bay 1-4, Central Facility",
            timezone="UTC"
        )
        session.add(store)
        await session.flush()

    # 2. Ensure ADMIN user exists
    result = await session.execute(select(AppUser).where(AppUser.email == "admin@secops.local"))
    if not result.scalars().first():
        hashed_password = get_password_hash("admin123")
        admin_user = AppUser(
            user_id=str(uuid.uuid4()),
            email="admin@secops.local",
            password_hash=hashed_password,
            role="ADMIN",
            store_id=store.store_id,
            mfa_enabled=False
        )
        session.add(admin_user)

    # 3. Base Threshold Config
    cfg = await session.execute(select(ThresholdConfig).limit(1))
    if not cfg.scalars().first():
        new_cfg = ThresholdConfig(
            config_id="TCFG-DEFAULT",
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
    # 4. Baseline Lanes (LANE-01, LANE-02)
    from src.db.models import Lane
    l1 = await session.execute(select(Lane).where(Lane.lane_id == "LANE-01"))
    if not l1.scalar_one_or_none():
        session.add(Lane(
            lane_id="LANE-01",
            store_id=store.store_id,
            label="Main Exit Portal 1",
            status="ONLINE"
        ))
    l2 = await session.execute(select(Lane).where(Lane.lane_id == "LANE-02"))
    if not l2.scalar_one_or_none():
        session.add(Lane(
            lane_id="LANE-02",
            store_id=store.store_id,
            label="Express Exit Portal 2",
            status="ONLINE"
        ))
        
    await session.commit()
