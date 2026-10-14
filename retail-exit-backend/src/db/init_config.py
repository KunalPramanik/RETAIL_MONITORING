from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import ThresholdConfig, AppUser, Store
from src.security import get_password_hash
import uuid
import os

async def init_baseline_configuration(session: AsyncSession):
    # 0. Ensure schema compatibility on SQLite (auto-migrate missing columns)
    bind = session.bind or session.get_bind()
    if bind and getattr(bind.dialect, "name", None) == "sqlite":
        try:
            from sqlalchemy import text
            # Employee table migrations
            cols_res = await session.execute(text("PRAGMA table_info(employee);"))
            emp_cols = [r[1] for r in cols_res.fetchall()]
            if emp_cols and "employee_code" not in emp_cols:
                await session.execute(text("ALTER TABLE employee ADD COLUMN employee_code VARCHAR(32);"))

            # Camera table migrations
            cam_cols_res = await session.execute(text("PRAGMA table_info(camera);"))
            cam_cols = [r[1] for r in cam_cols_res.fetchall()]
            if cam_cols:
                if "degraded_reason" not in cam_cols:
                    await session.execute(text("ALTER TABLE camera ADD COLUMN degraded_reason VARCHAR(255);"))
                if "last_frame_at" not in cam_cols:
                    await session.execute(text("ALTER TABLE camera ADD COLUMN last_frame_at DATETIME;"))
                if "last_inference_at" not in cam_cols:
                    await session.execute(text("ALTER TABLE camera ADD COLUMN last_inference_at DATETIME;"))
                if "inference_latency_ms" not in cam_cols:
                    await session.execute(text("ALTER TABLE camera ADD COLUMN inference_latency_ms NUMERIC(8, 2);"))

            # VisionDetection table migrations
            vis_cols_res = await session.execute(text("PRAGMA table_info(vision_detection);"))
            vis_cols = [r[1] for r in vis_cols_res.fetchall()]
            if vis_cols:
                if "track_id" not in vis_cols:
                    await session.execute(text("ALTER TABLE vision_detection ADD COLUMN track_id VARCHAR(64);"))
                if "category" not in vis_cols:
                    await session.execute(text("ALTER TABLE vision_detection ADD COLUMN category VARCHAR(32) DEFAULT 'GENERAL_OBJECT';"))
                if "snapshot_url" not in vis_cols:
                    await session.execute(text("ALTER TABLE vision_detection ADD COLUMN snapshot_url TEXT;"))

            await session.flush()
        except Exception:
            pass

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

    # 2. Ensure at least one active ADMIN user exists
    existing_admin = await session.execute(select(AppUser).where(AppUser.role == "ADMIN", AppUser.is_active == True))
    if not existing_admin.scalars().first():
        initial_pw = os.getenv("ADMIN_INITIAL_PASSWORD")
        if not initial_pw:
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env == "production":
                raise RuntimeError(
                    "FATAL: ADMIN_INITIAL_PASSWORD environment variable must be configured "
                    "in environment or secret manager before first-run database bootstrap in production."
                )
            import secrets
            import sys
            initial_pw = secrets.token_urlsafe(18)
            sys.stderr.write(
                f"\n[BOOTSTRAP] Initial admin user provisioned. One-time setup password: {initial_pw}\n"
            )

        hashed_password = get_password_hash(initial_pw)
        admin_user = AppUser(
            user_id=str(uuid.uuid4()),
            email="admin@secops.local",
            username="admin",
            password_hash=hashed_password,
            role="ADMIN",
            store_id=store.store_id,
            mfa_enabled=False,
            is_active=True,
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
