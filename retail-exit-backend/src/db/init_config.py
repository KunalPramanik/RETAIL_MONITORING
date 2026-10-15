from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
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

    # 2. Production admin safety check (only enforced when bootstrapping initial admin)
    existing_admin = await session.execute(select(AppUser).where(AppUser.role == "ADMIN"))
    if not existing_admin.scalars().first():
        if os.getenv("ENVIRONMENT") == "production" and not os.getenv("ADMIN_INITIAL_PASSWORD"):
            raise RuntimeError("ADMIN_INITIAL_PASSWORD environment variable must be configured for baseline admin bootstrap in production")

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

    # 5. Baseline Product & Material Catalog (Cement bags, Iron rods, Heavy cartons, Bookshelf inventory, Single units)
    from src.db.models import Product, Material, MaterialInventoryBalance, get_utc_now
    now = get_utc_now()
    baseline_catalog = [
        {
            "sku": "MAT-CEM-50KG",
            "name": "Portland Construction Cement (50kg Bag)",
            "category": "STACKED_MATERIAL",
            "pack_size": 1,
            "unit_price": 9.50,
            "case_price": 9.50,
            "reorder_threshold": 20,
            "vision_class_id": 101,
            "count_unit": "bag",
            "packaging_type": "stack",
        },
        {
            "sku": "MAT-ROD-REBAR",
            "name": "Structural Steel TMT Rebar Rods",
            "category": "STACKED_MATERIAL",
            "pack_size": 1,
            "unit_price": 45.00,
            "case_price": 45.00,
            "reorder_threshold": 15,
            "vision_class_id": 102,
            "count_unit": "bundle",
            "packaging_type": "bundle",
        },
        {
            "sku": "MAT-BOX-HEAVY",
            "name": "Heavy Corrugated Master Shipping Carton",
            "category": "DISCRETE_PACKAGE",
            "pack_size": 1,
            "unit_price": 25.00,
            "case_price": 25.00,
            "reorder_threshold": 10,
            "vision_class_id": 104,
            "count_unit": "carton",
            "packaging_type": "sealed_case",
        },
        {
            "sku": "MAT-BOK-SHELF",
            "name": "Bookshelf Inventory & Documents (Shelf Row)",
            "category": "DISCRETE_PACKAGE",
            "pack_size": 1,
            "unit_price": 15.00,
            "case_price": 15.00,
            "reorder_threshold": 5,
            "vision_class_id": 108,
            "count_unit": "piece",
            "packaging_type": "loose_unit",
        },
        {
            "sku": "SKU-RETAIL-01",
            "name": "Standard Exposed Retail Item (Single Unit)",
            "category": "RETAIL_GOODS",
            "pack_size": 1,
            "unit_price": 12.00,
            "case_price": 12.00,
            "reorder_threshold": 10,
            "vision_class_id": 1006,
            "count_unit": "piece",
            "packaging_type": "loose_unit",
        },
    ]

    for item in baseline_catalog:
        prod_stmt = select(Product).where(Product.sku_code == item["sku"])
        p_res = await session.execute(prod_stmt)
        prod = p_res.scalar_one_or_none()
        if not prod:
            prod_id = f"prod_{uuid.uuid4().hex[:12]}"
            prod = Product(
                product_id=prod_id,
                sku_code=item["sku"],
                name=item["name"],
                category=item["category"],
                pack_size=item["pack_size"],
                unit_price=item["unit_price"],
                case_price=item["case_price"],
                reorder_threshold=item["reorder_threshold"],
                vision_class_id=item["vision_class_id"],
                created_at=now,
                updated_at=now,
            )
            session.add(prod)
            await session.flush()

        mat_stmt = select(Material).where(Material.sku_code == item["sku"])
        m_res = await session.execute(mat_stmt)
        mat = m_res.scalar_one_or_none()
        if not mat:
            mat = Material(
                material_id=str(prod.product_id),
                name=item["name"],
                sku_code=item["sku"],
                category=item["category"],
                deployment_profile="WAREHOUSE_DISPATCH",
                count_unit=item["count_unit"],
                packaging_type=item["packaging_type"],
                units_per_package=1,
                counting_tier="SINGLE_UNIT",
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            session.add(mat)
            await session.flush()

        bal_stmt = select(MaterialInventoryBalance).where(MaterialInventoryBalance.material_id == str(mat.material_id))
        b_res = await session.execute(bal_stmt)
        bal = b_res.scalar_one_or_none()
        if not bal:
            bal = MaterialInventoryBalance(
                balance_id=f"bal_{uuid.uuid4().hex[:12]}",
                material_id=str(mat.material_id),
                location_id="MAIN_WAREHOUSE",
                opening_stock=0,
                incoming_confirmed=0,
                outgoing_confirmed=0,
                defective_stock=0,
                adjusted_stock=0,
                current_stock=0,
                last_reconciled_at=now,
                updated_at=now,
            )
            session.add(bal)
            await session.flush()
        
    await session.commit()

