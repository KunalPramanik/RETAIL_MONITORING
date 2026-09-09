"""Database Seeding Module

Populates the database with realistic retail mock data matching frontend console contracts.
Includes products with case pack sizes, personnel rosters, sensor lanes, invoices, and events.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import (
    Store,
    Shift,
    Lane,
    Camera,
    CameraHeartbeat,
    Product,
    Employee,
    ThresholdConfig,
    Invoice,
    ExitEvent,
    ExitEventLineItem,
    VisionDetection,
    RfidRead,
    WeightReading,
    FaceMatchAttempt,
    Alert,
    AlarmDispatch,
    AuditLog,
    get_utc_now,
)


async def seed_database(session: AsyncSession):
    """Seed initial records if database is empty."""
    # Check if store exists
    result = await session.execute(select(Store).limit(1))
    if result.scalars().first() is not None:
        return  # Already seeded

    now = get_utc_now()

    # 1. Store
    store = Store(
        store_id="store_0402",
        name="SuperStore #402 - Metro Central",
        address="742 Evergreen Terrace, Sector 4",
        timezone="America/New_York",
    )
    session.add(store)

    # 2. Shifts
    shifts = [
        Shift(shift_id="shift_morning", label="Morning Shift A", starts_at="06:00:00", ends_at="14:30:00"),
        Shift(shift_id="shift_afternoon", label="Afternoon Shift B", starts_at="14:00:00", ends_at="22:30:00"),
        Shift(shift_id="shift_night", label="Night Shift C", starts_at="22:00:00", ends_at="06:30:00"),
    ]
    session.add_all(shifts)

    # 3. Lanes
    lanes = [
        Lane(
            lane_id="LANE-01",
            label="Exit Lane 01 (North Customer Exit)",
            store_id="store_0402",
            camera_ids=["cam_101"],
            rfid_antenna_id="ANT-L1-01",
            weight_sensor_id="SCALE-L1-A",
            turnstile_ctrl_id="TURN-L1-LOCK",
            status="ONLINE",
            last_heartbeat_at=now,
        ),
        Lane(
            lane_id="LANE-02",
            label="Exit Lane 02 (East Logistics Loading)",
            store_id="store_0402",
            camera_ids=["cam_102"],
            rfid_antenna_id="ANT-L2-01",
            weight_sensor_id="SCALE-L2-A",
            turnstile_ctrl_id="TURN-L2-LOCK",
            status="ONLINE",
            last_heartbeat_at=now,
        ),
        Lane(
            lane_id="LANE-03",
            label="Exit Lane 03 (South Portal - Contractor/Staff)",
            store_id="store_0402",
            camera_ids=["cam_103"],
            rfid_antenna_id="ANT-L3-01",
            weight_sensor_id="SCALE-L3-A",
            turnstile_ctrl_id="TURN-L3-LOCK",
            status="ONLINE",
            last_heartbeat_at=now,
        ),
        Lane(
            lane_id="LANE-04",
            label="Exit Lane 04 (West Bulk Staging Outflow)",
            store_id="store_0402",
            camera_ids=["cam_104"],
            rfid_antenna_id="ANT-L4-01",
            weight_sensor_id="SCALE-L4-A",
            turnstile_ctrl_id="TURN-L4-LOCK",
            status="DEGRADED",
            last_heartbeat_at=now - timedelta(minutes=5),
        ),
    ]
    session.add_all(lanes)

    # 3.1 Camera Fleet Registry
    cameras = [
        Camera(
            camera_id="cam_101",
            label="Exit Lane 1 — North Portal Main",
            lane_id="LANE-01",
            ip_address="192.168.10.41",
            rtsp_path="/live/main",
            stream_url="webrtc://edge-media-server.local:8554/cam_101",
            resolution="1920x1080",
            fps=30,
            status="ONLINE",
            last_heartbeat_at=now,
            added_at=now - timedelta(days=60),
        ),
        Camera(
            camera_id="cam_102",
            label="Exit Lane 2 — East Logistics Overview",
            lane_id="LANE-02",
            ip_address="192.168.10.42",
            rtsp_path="/live/ch0",
            stream_url="webrtc://edge-media-server.local:8554/cam_102",
            resolution="1920x1080",
            fps=30,
            status="ONLINE",
            last_heartbeat_at=now,
            added_at=now - timedelta(days=60),
        ),
        Camera(
            camera_id="cam_103",
            label="Exit Lane 3 — South Staff Portal",
            lane_id="LANE-03",
            ip_address="192.168.10.43",
            rtsp_path="/stream1",
            stream_url="webrtc://edge-media-server.local:8554/cam_103",
            resolution="1920x1080",
            fps=30,
            status="ONLINE",
            last_heartbeat_at=now,
            added_at=now - timedelta(days=45),
        ),
        Camera(
            camera_id="cam_104",
            label="Exit Lane 4 — West Bulk Staging Overhead",
            lane_id="LANE-04",
            ip_address="192.168.10.44",
            rtsp_path="/live/high",
            stream_url="webrtc://edge-media-server.local:8554/cam_104",
            resolution="1280x720",
            fps=18,
            status="DEGRADED",
            last_heartbeat_at=now - timedelta(minutes=4),
            added_at=now - timedelta(days=30),
        ),
        Camera(
            camera_id="cam_105",
            label="Reserve Loading Dock 5 — Spares",
            lane_id=None,
            ip_address="192.168.10.55",
            rtsp_path="/stream",
            stream_url=None,
            resolution="1920x1080",
            fps=30,
            status="PENDING_SETUP",
            last_heartbeat_at=None,
            added_at=now - timedelta(days=2),
        ),
    ]
    session.add_all(cameras)

    camera_heartbeats = [
        CameraHeartbeat(camera_id="cam_101", received_at=now, fps_observed=29.8, bitrate_kbps=4120.0),
        CameraHeartbeat(camera_id="cam_102", received_at=now, fps_observed=30.0, bitrate_kbps=4280.0),
        CameraHeartbeat(camera_id="cam_103", received_at=now, fps_observed=29.4, bitrate_kbps=3950.0),
        CameraHeartbeat(camera_id="cam_104", received_at=now - timedelta(minutes=4), fps_observed=18.2, bitrate_kbps=1840.0),
    ]
    session.add_all(camera_heartbeats)

    # 4. Products Master Catalog
    products = [
        Product(
            product_id="prod_001",
            sku_code="SKU-WTR-500-24",
            name="Glacier Pure Spring Water 500ml",
            category="Beverages",
            pack_size=24,
            unit_price=1.25,
            case_price=24.00,
            reorder_threshold=150,
            rfid_epc_prefix="303426",
            avg_unit_weight_g=520.0,
        ),
        Product(
            product_id="prod_002",
            sku_code="SKU-ENG-250-12",
            name="Volt Zero-Sugar Energy Drink 250ml",
            category="Beverages",
            pack_size=12,
            unit_price=2.75,
            case_price=28.50,
            reorder_threshold=80,
            rfid_epc_prefix="303427",
            avg_unit_weight_g=275.0,
        ),
        Product(
            product_id="prod_003",
            sku_code="SKU-SOD-330-24",
            name="Classic Spark Cola 330ml Cans",
            category="Beverages",
            pack_size=24,
            unit_price=1.10,
            case_price=22.00,
            reorder_threshold=120,
            rfid_epc_prefix="303428",
            avg_unit_weight_g=360.0,
        ),
        Product(
            product_id="prod_004",
            sku_code="SKU-DET-POD-06",
            name="CleanMax Ultra Laundry Pods 42ct",
            category="Household",
            pack_size=6,
            unit_price=14.50,
            case_price=78.00,
            reorder_threshold=40,
            rfid_epc_prefix="303429",
            avg_unit_weight_g=1200.0,
        ),
        Product(
            product_id="prod_005",
            sku_code="SKU-PST-PEN-16",
            name="Nonna Organic Penne Rigate 500g",
            category="Pantry",
            pack_size=16,
            unit_price=2.20,
            case_price=31.00,
            reorder_threshold=90,
            rfid_epc_prefix="303430",
            avg_unit_weight_g=530.0,
        ),
        Product(
            product_id="prod_006",
            sku_code="SKU-COF-DRK-08",
            name="Highland Dark Roast Whole Bean 1kg",
            category="Pantry",
            pack_size=8,
            unit_price=16.80,
            case_price=122.00,
            reorder_threshold=35,
            rfid_epc_prefix="303431",
            avg_unit_weight_g=1050.0,
        ),
        Product(
            product_id="prod_007",
            sku_code="SKU-OLV-EXT-06",
            name="Aura Extra Virgin Olive Oil 750ml",
            category="Pantry",
            pack_size=6,
            unit_price=11.20,
            case_price=62.00,
            reorder_threshold=45,
            rfid_epc_prefix="303432",
            avg_unit_weight_g=850.0,
        ),
        Product(
            product_id="prod_008",
            sku_code="SKU-BAR-PRT-12",
            name="PeakForce High Protein Crisp Bar 60g",
            category="Snacks",
            pack_size=12,
            unit_price=3.10,
            case_price=32.00,
            reorder_threshold=100,
            rfid_epc_prefix="303433",
            avg_unit_weight_g=70.0,
        ),
        Product(
            product_id="prod_009",
            sku_code="SKU-PAP-TWL-12",
            name="SuperSoft 2-Ply Paper Towels 6-Roll",
            category="Household",
            pack_size=4,
            unit_price=8.90,
            case_price=32.00,
            reorder_threshold=50,
            rfid_epc_prefix="303434",
            avg_unit_weight_g=1100.0,
        ),
        Product(
            product_id="prod_010",
            sku_code="SKU-BAT-ALK-20",
            name="PowerCell Industrial AA 10-Pack",
            category="Hardware",
            pack_size=20,
            unit_price=6.50,
            case_price=115.00,
            reorder_threshold=60,
            rfid_epc_prefix="303435",
            avg_unit_weight_g=240.0,
        ),
    ]
    session.add_all(products)

    # 5. Employees & ArcFace Embeddings (512-d normalized mock vectors)
    employees = [
        Employee(
            employee_id="emp_101",
            name="David Torres",
            role="Logistics Supervisor",
            rfid_badge_id="RFID-BADGE-8841",
            shift_id="shift_morning",
            active_flag=True,
            face_embedding=[0.05] * 512,
            embedding_updated_at=now,
        ),
        Employee(
            employee_id="emp_102",
            name="Marcus Vance",
            role="Forklift Operator",
            rfid_badge_id="RFID-BADGE-4419",
            shift_id="shift_morning",
            active_flag=True,
            face_embedding=[0.08] * 512,
            embedding_updated_at=now,
        ),
        Employee(
            employee_id="emp_103",
            name="Elena Rostova",
            role="Receiving Porter",
            rfid_badge_id="RFID-BADGE-2290",
            shift_id="shift_afternoon",
            active_flag=True,
            face_embedding=[0.02] * 512,
            embedding_updated_at=now,
        ),
        Employee(
            employee_id="emp_104",
            name="Priya Patel",
            role="Night Fulfillment Lead",
            rfid_badge_id="RFID-BADGE-7104",
            shift_id="shift_night",
            active_flag=True,
            face_embedding=[-0.03] * 512,
            embedding_updated_at=now,
        ),
        Employee(
            employee_id="emp_105",
            name="Jackson Reed",
            role="Exit Gate Attendant",
            rfid_badge_id="RFID-BADGE-5521",
            shift_id="shift_morning",
            active_flag=True,
            face_embedding=[0.01] * 512,
            embedding_updated_at=now,
        ),
        Employee(
            employee_id="emp_106",
            name="Carlos Mendez",
            role="General Stock Clerk",
            rfid_badge_id="RFID-BADGE-9083",
            shift_id="shift_afternoon",
            active_flag=False,
            face_embedding=[0.04] * 512,
            embedding_updated_at=now,
        ),
    ]
    session.add_all(employees)

    # 6. Threshold Configuration
    threshold_cfg = ThresholdConfig(
        config_id="cfg_default",
        store_id="store_0402",
        unit_tolerance=0,
        pct_tolerance=0.0,
        low_severity_threshold=1,
        med_severity_threshold=3,
        high_severity_threshold=6,
        repeat_offender_window_days=30,
        repeat_offender_count_trigger=3,
        turnstile_auto_lock_on_high=True,
        audio_alarm_enabled=True,
    )
    session.add(threshold_cfg)

    # 7. Invoices (OCR Manifests)
    invoices = [
        Invoice(
            invoice_id="inv_88201",
            invoice_number="INV-2026-0902-88201",
            carrier_name="FastTrack Logistics Inc.",
            store_destination="SuperStore #402 - Metro Central",
            source="SCAN",
            raw_file_url="https://storage.secops.internal/invoices/inv_88201.pdf",
            ocr_model_version="paddleocr-invoice-layout-v3.0",
            extraction_confidence=0.9840,
            declared_total_units=72,
            extracted_json=[
                {
                    "skuCode": "SKU-WTR-500-24",
                    "description": "Glacier Pure Spring Water 500ml",
                    "casesDeclared": 3,
                    "unitsPerCase": 24,
                    "totalUnits": 72,
                    "status": "MATCHED",
                }
            ],
        ),
        Invoice(
            invoice_id="inv_88202",
            invoice_number="INV-2026-0902-88202",
            carrier_name="Direct Haul Services",
            store_destination="SuperStore #402 - Metro Central",
            source="SCAN",
            raw_file_url="https://storage.secops.internal/invoices/inv_88202.pdf",
            ocr_model_version="paddleocr-invoice-layout-v3.0",
            extraction_confidence=0.9210,
            declared_total_units=48,
            extracted_json=[
                {
                    "skuCode": "SKU-ENG-250-12",
                    "description": "Volt Zero-Sugar Energy Drink 250ml",
                    "casesDeclared": 4,
                    "unitsPerCase": 12,
                    "totalUnits": 48,
                    "status": "DISCREPANCY",
                }
            ],
        ),
        Invoice(
            invoice_id="inv_88203",
            invoice_number="INV-2026-0902-88203",
            carrier_name="Prime Supply Chain LLC",
            store_destination="SuperStore #402 - Metro Central",
            source="SCAN",
            raw_file_url="https://storage.secops.internal/invoices/inv_88203.pdf",
            ocr_model_version="paddleocr-invoice-layout-v3.0",
            extraction_confidence=0.9680,
            declared_total_units=80,
            extracted_json=[
                {
                    "skuCode": "SKU-PST-PEN-16",
                    "description": "Nonna Organic Penne Rigate 500g",
                    "casesDeclared": 5,
                    "unitsPerCase": 16,
                    "totalUnits": 80,
                    "status": "MATCHED",
                }
            ],
        ),
        Invoice(
            invoice_id="inv_88204",
            invoice_number="INV-2026-0902-88204",
            carrier_name="Internal Transfer Hub 3",
            store_destination="Store #108 Express",
            source="SCAN",
            raw_file_url="https://storage.secops.internal/invoices/inv_88204.pdf",
            ocr_model_version="paddleocr-invoice-layout-v3.0",
            extraction_confidence=0.8920,
            declared_total_units=24,
            extracted_json=[
                {
                    "skuCode": "SKU-DET-POD-06",
                    "description": "CleanMax Ultra Laundry Pods 42ct",
                    "casesDeclared": 4,
                    "unitsPerCase": 6,
                    "totalUnits": 24,
                    "status": "DISCREPANCY",
                }
            ],
        ),
    ]
    session.add_all(invoices)

    # 8. Historical Exit Events
    event1 = ExitEvent(
        event_id="EVT-2026-9045",
        ts=now - timedelta(minutes=4),
        lane_id="LANE-02",
        employee_id="emp_102",  # Marcus Vance
        employee_match_confidence=0.9750,
        cases_detected=6,
        units_detected=36,
        vision_count=36,
        vision_confidence=0.9820,
        rfid_count=36,
        weight_kg=43.200,
        weight_estimated_units=36,
        consensus_units=36,
        consensus_method="weighted_vote_v2",
        invoice_id="inv_88204",
        declared_units=24,
        delta_units=12,
        verdict="MISMATCH",
        severity="HIGH",
        snapshot_url="/snapshots/lane2_snap_9045.jpg",
        notes="Cart carried 6 full sealed cases (36 units) vs invoice declaration of 4 cases (24 units). High severity escalation triggered due to +12 unit delta and repeat carrier record.",
    )
    session.add(event1)

    event2 = ExitEvent(
        event_id="EVT-2026-9044",
        ts=now - timedelta(minutes=10),
        lane_id="LANE-01",
        employee_id="emp_101",
        employee_match_confidence=0.9910,
        cases_detected=2,
        units_detected=48,
        vision_count=48,
        vision_confidence=0.9940,
        rfid_count=48,
        weight_kg=26.400,
        weight_estimated_units=48,
        consensus_units=48,
        consensus_method="weighted_vote_v2",
        invoice_id="inv_88201",
        declared_units=48,
        delta_units=0,
        verdict="PASS",
        severity="NONE",
        snapshot_url="/snapshots/lane1_snap_9044.jpg",
        notes="2 full cases of spring water verified across all 3 sensor channels.",
    )
    session.add(event2)

    event3 = ExitEvent(
        event_id="EVT-2026-9043",
        ts=now - timedelta(minutes=18),
        lane_id="LANE-03",
        employee_id="emp_103",
        employee_match_confidence=0.9880,
        cases_detected=5,
        units_detected=80,
        vision_count=80,
        vision_confidence=0.9780,
        rfid_count=80,
        weight_kg=42.000,
        weight_estimated_units=80,
        consensus_units=80,
        consensus_method="weighted_vote_v2",
        invoice_id="inv_88203",
        declared_units=80,
        delta_units=0,
        verdict="PASS",
        severity="NONE",
        snapshot_url="/snapshots/lane3_snap_9043.jpg",
        notes="Consensus match verified. 5 cases of Penne Rigate (80 units).",
    )
    session.add(event3)

    event4 = ExitEvent(
        event_id="EVT-2026-9042",
        ts=now - timedelta(minutes=30),
        lane_id="LANE-02",
        employee_id="emp_104",  # Priya Patel
        employee_match_confidence=0.9650,
        cases_detected=4,
        units_detected=52,
        vision_count=52,
        vision_confidence=0.9540,
        rfid_count=48,  # Attenuated
        weight_kg=16.800,
        weight_estimated_units=52,
        consensus_units=52,
        consensus_method="weighted_vote_v2",
        invoice_id="inv_88202",
        declared_units=48,
        delta_units=4,
        verdict="MISMATCH",
        severity="MEDIUM",
        snapshot_url="/snapshots/lane2_snap_9042.jpg",
        notes="4 sealed cases + 4 loose single cans detected on top rack. Declared invoice was 48 units (+4 delta).",
    )
    session.add(event4)

    event5 = ExitEvent(
        event_id="EVT-2026-9041",
        ts=now - timedelta(minutes=45),
        lane_id="LANE-01",
        employee_id="emp_105",
        employee_match_confidence=0.9820,
        cases_detected=3,
        units_detected=74,
        vision_count=74,
        vision_confidence=0.9850,
        rfid_count=74,
        weight_kg=39.800,
        weight_estimated_units=74,
        consensus_units=74,
        consensus_method="weighted_vote_v2",
        invoice_id="inv_88201",
        declared_units=72,
        delta_units=2,
        verdict="MISMATCH",
        severity="LOW",
        snapshot_url="/snapshots/lane1_snap_9041.jpg",
        notes="3 full cases (72 units) + 2 loose single bottles detected (+2 units over declared 72).",
    )
    session.add(event5)

    # 9. Line Items for Events
    line_items = [
        ExitEventLineItem(event_id="EVT-2026-9045", product_id="prod_004", cases_qty=6, units_qty=36),
        ExitEventLineItem(event_id="EVT-2026-9044", product_id="prod_001", cases_qty=2, units_qty=48),
        ExitEventLineItem(event_id="EVT-2026-9043", product_id="prod_005", cases_qty=5, units_qty=80),
        ExitEventLineItem(event_id="EVT-2026-9042", product_id="prod_002", cases_qty=4, units_qty=48),
        ExitEventLineItem(event_id="EVT-2026-9042", product_id="prod_002", cases_qty=0, units_qty=4),
        ExitEventLineItem(event_id="EVT-2026-9041", product_id="prod_001", cases_qty=3, units_qty=72),
        ExitEventLineItem(event_id="EVT-2026-9041", product_id="prod_001", cases_qty=0, units_qty=2),
    ]
    session.add_all(line_items)

    # 10. Raw Model Artefacts (Vision, RFID, Weight, Face)
    detections = [
        VisionDetection(
            event_id="EVT-2026-9045",
            frame_ts=now - timedelta(minutes=4),
            model_version="yolov8-retail-pack-v2.1",
            bbox=[120, 80, 240, 320],
            class_label="case_full",
            product_id="prod_004",
            confidence=0.9820,
        ),
        VisionDetection(
            event_id="EVT-2026-9042",
            frame_ts=now - timedelta(minutes=30),
            model_version="yolov8-retail-pack-v2.1",
            bbox=[100, 60, 200, 280],
            class_label="case_full",
            product_id="prod_002",
            confidence=0.9540,
        ),
    ]
    session.add_all(detections)

    rfid_reads = [
        RfidRead(
            event_id="EVT-2026-9045",
            epc_tag="303429-001-A9F88",
            antenna_id="ANT-L2-01",
            rssi=-42.50,
            read_at=now - timedelta(minutes=4),
        ),
        RfidRead(
            event_id="EVT-2026-9042",
            epc_tag="303427-004-C8821",
            antenna_id="ANT-L2-01",
            rssi=-68.20,  # Attenuated RSSI
            read_at=now - timedelta(minutes=30),
        ),
    ]
    session.add_all(rfid_reads)

    weight_reads = [
        WeightReading(
            event_id="EVT-2026-9045",
            sensor_id="SCALE-L2-A",
            weight_kg=43.200,
            read_at=now - timedelta(minutes=4),
        ),
        WeightReading(
            event_id="EVT-2026-9042",
            sensor_id="SCALE-L2-A",
            weight_kg=16.800,
            read_at=now - timedelta(minutes=30),
        ),
    ]
    session.add_all(weight_reads)

    face_matches = [
        FaceMatchAttempt(
            event_id="EVT-2026-9045",
            matched_employee_id="emp_102",
            similarity=0.9750,
            model_version="arcface-r100-512d-v1.4",
            decision="MATCHED",
            created_at=now - timedelta(minutes=4),
        ),
        FaceMatchAttempt(
            event_id="EVT-2026-9042",
            matched_employee_id="emp_104",
            similarity=0.9650,
            model_version="arcface-r100-512d-v1.4",
            decision="MATCHED",
            created_at=now - timedelta(minutes=30),
        ),
    ]
    session.add_all(face_matches)

    # 11. Alerts & Dispatches
    alert1 = Alert(
        alert_id="ALT-8001",
        event_id="EVT-2026-9045",
        alert_type="OVER_CARRY",
        severity="HIGH",
        delta_units=12,
        status="OPEN",
        created_at=now - timedelta(minutes=4),
    )
    alert2 = Alert(
        alert_id="ALT-8002",
        event_id="EVT-2026-9042",
        alert_type="OVER_CARRY",
        severity="MEDIUM",
        delta_units=4,
        status="OPEN",
        created_at=now - timedelta(minutes=30),
    )
    alert3 = Alert(
        alert_id="ALT-8003",
        event_id="EVT-2026-9041",
        alert_type="OVER_CARRY",
        severity="LOW",
        delta_units=2,
        status="ACKNOWLEDGED",
        resolved_by="David Torres",
        resolution_note="Inspected customer cart at North Portal. Operator confirmed promotional promo sample inclusion.",
        created_at=now - timedelta(minutes=45),
    )
    alert4 = Alert(
        alert_id="ALT-8004",
        event_id="EVT-2026-9043",
        alert_type="SENSOR_DISAGREEMENT",
        severity="HIGH",
        delta_units=8,
        status="RESOLVED",
        resolved_by="David Torres",
        resolution_note="RFID gate antenna #2 recalibrated. Blindspot eliminated after angle alignment.",
        resolved_at=now - timedelta(minutes=15),
        created_at=now - timedelta(hours=2),
    )
    session.add_all([alert1, alert2, alert3, alert4])

    # Dispatches
    dispatches = [
        AlarmDispatch(
            dispatch_id="disp_01",
            alert_id="ALT-8001",
            channel="TURNSTILE_LOCK",
            status="ACKED",
            attempted_at=now - timedelta(minutes=4),
        ),
        AlarmDispatch(
            dispatch_id="disp_02",
            alert_id="ALT-8001",
            channel="SIREN",
            status="SENT",
            attempted_at=now - timedelta(minutes=4),
        ),
        AlarmDispatch(
            dispatch_id="disp_03",
            alert_id="ALT-8001",
            channel="PUSH",
            status="SENT",
            attempted_at=now - timedelta(minutes=4),
        ),
    ]
    session.add_all(dispatches)

    # 12. Audit Trail
    audit_entries = [
        AuditLog(
            entity_type="SYSTEM",
            entity_id="store_0402",
            action="BOOTSTRAP_SYSTEM",
            actor_type="SYSTEM",
            before_state=None,
            after_state={"status": "INITIALIZED", "nodes": 4},
            created_at=now - timedelta(hours=3),
        ),
        AuditLog(
            entity_type="ALERT",
            entity_id="ALT-8004",
            action="RESOLVE_INCIDENT",
            actor_type="USER",
            actor_id="emp_101",
            before_state={"status": "OPEN"},
            after_state={"status": "RESOLVED", "note": "RFID gate antenna #2 recalibrated."},
            created_at=now - timedelta(minutes=15),
        ),
    ]
    session.add_all(audit_entries)

    await session.commit()

