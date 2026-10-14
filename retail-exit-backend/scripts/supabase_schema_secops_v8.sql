-- ==============================================================================
-- SEC-OPS V8 — COMPLETE SUPABASE (POSTGRESQL) PRODUCTION DATABASE SCHEMA
-- ==============================================================================
-- Target Engine: Supabase / PostgreSQL 15+
-- Target Platform: Retail & Industrial Security Operations Platform
-- Includes: Extensions, Functions, Tables, Constraints, Indexes, Triggers,
--           and Initial Seed Data with ONE ACTIVE Software Owner:
--           Email: ces@gmail.com | Password: Ces@1234 | Role: ADMIN
-- ==============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. TRIGGER FUNCTION FOR AUTO-UPDATING updated_at
CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Clean slate / optional drop (commented out by default)
-- DROP SCHEMA public CASCADE;
-- CREATE SCHEMA public;

-- ==============================================================================
-- 3. CORE & TENANCY TABLES
-- ==============================================================================

-- 3.1 Store / Tenant Master
CREATE TABLE IF NOT EXISTS public.store (
    store_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'
);

-- 3.2 Threshold Configuration
CREATE TABLE IF NOT EXISTS public.threshold_config (
    config_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    store_id VARCHAR(36) REFERENCES public.store(store_id) ON DELETE CASCADE,
    unit_tolerance INTEGER NOT NULL DEFAULT 0,
    pct_tolerance NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    low_severity_threshold INTEGER NOT NULL DEFAULT 1,
    med_severity_threshold INTEGER NOT NULL DEFAULT 3,
    high_severity_threshold INTEGER NOT NULL DEFAULT 6,
    repeat_offender_window_days INTEGER NOT NULL DEFAULT 30,
    repeat_offender_count_trigger INTEGER NOT NULL DEFAULT 3,
    camera_offline_alert_after_sec INTEGER NOT NULL DEFAULT 60,
    turnstile_auto_lock_on_high BOOLEAN NOT NULL DEFAULT TRUE,
    audio_alarm_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_by VARCHAR(36),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3.3 Application Users (Authentication & Authorization)
CREATE TABLE IF NOT EXISTS public.app_user (
    user_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(64) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (role IN ('SUPERVISOR', 'ADMIN', 'VIEWER')),
    store_id VARCHAR(36) REFERENCES public.store(store_id) ON DELETE SET NULL,
    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_app_user_email ON public.app_user(email);
CREATE INDEX IF NOT EXISTS ix_app_user_username ON public.app_user(username);

-- Alias view for backward compatibility if queries refer to 'user'
CREATE OR REPLACE VIEW public.user AS SELECT * FROM public.app_user;

-- ==============================================================================
-- 4. HARDWARE, LANES & CAMERAS
-- ==============================================================================

-- 4.1 Physical Lanes
CREATE TABLE IF NOT EXISTS public.lane (
    lane_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    label VARCHAR(128) NOT NULL,
    store_id VARCHAR(36) NOT NULL REFERENCES public.store(store_id) ON DELETE CASCADE,
    camera_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    rfid_antenna_id VARCHAR(128),
    weight_sensor_id VARCHAR(128),
    turnstile_ctrl_id VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'ONLINE' CHECK (status IN ('ONLINE', 'OFFLINE', 'DEGRADED')),
    last_heartbeat_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_lane_store ON public.lane(store_id);

-- 4.2 Camera Fleet
CREATE TABLE IF NOT EXISTS public.camera (
    camera_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    label VARCHAR(255) NOT NULL,
    lane_id VARCHAR(36) REFERENCES public.lane(lane_id) ON DELETE SET NULL,
    ip_address VARCHAR(64) NOT NULL,
    rtsp_path VARCHAR(255) NOT NULL,
    sub_stream_path VARCHAR(255),
    credentials_ref VARCHAR(128),
    stream_url TEXT,
    pairing_method VARCHAR(32) NOT NULL DEFAULT 'MANUAL' CHECK (pairing_method IN ('MANUAL', 'QR_CAMERA_DISPLAYED', 'QR_APP_GENERATED')),
    resolution VARCHAR(32) DEFAULT '1920x1080',
    fps INTEGER DEFAULT 30,
    pipeline_mode VARCHAR(64) NOT NULL DEFAULT 'STANDARD_DETECTION' CHECK (pipeline_mode IN ('STANDARD_DETECTION', 'MATERIAL_SEGMENTATION', 'PERIMETER_TRIPWIRE_GATE')),
    camera_role VARCHAR(32) NOT NULL DEFAULT 'GENERAL_MONITORING' CHECK (camera_role IN ('ENTRY_EXIT', 'STOCK_AREA', 'SHELF', 'WAREHOUSE', 'DISPATCH', 'GENERAL_MONITORING')),
    roi_polygon JSONB,
    ignored_classes JSONB,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING_SETUP' CHECK (status IN ('ONLINE', 'OFFLINE', 'DEGRADED', 'PENDING_SETUP')),
    degraded_reason VARCHAR(255),
    last_frame_at TIMESTAMPTZ,
    last_inference_at TIMESTAMPTZ,
    inference_latency_ms NUMERIC(8, 2),
    last_heartbeat_at TIMESTAMPTZ,
    offline_since TIMESTAMPTZ,
    added_by VARCHAR(36) REFERENCES public.app_user(user_id) ON DELETE SET NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_camera_lane ON public.camera(lane_id);
CREATE INDEX IF NOT EXISTS idx_camera_status ON public.camera(status);
CREATE INDEX IF NOT EXISTS idx_camera_role ON public.camera(camera_role);

-- 4.3 Camera Pairing Tokens
CREATE TABLE IF NOT EXISTS public.camera_pairing_token (
    token_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    token_value VARCHAR(128) UNIQUE NOT NULL,
    store_id VARCHAR(36) NOT NULL REFERENCES public.store(store_id) ON DELETE CASCADE,
    lane_id VARCHAR(36) REFERENCES public.lane(lane_id) ON DELETE SET NULL,
    created_by VARCHAR(36) REFERENCES public.app_user(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    used_by_camera_id VARCHAR(36) REFERENCES public.camera(camera_id) ON DELETE SET NULL,
    qr_payload TEXT
);
CREATE INDEX IF NOT EXISTS ix_camera_pairing_token_token_value ON public.camera_pairing_token(token_value);

-- 4.4 Camera Heartbeats
CREATE TABLE IF NOT EXISTS public.camera_heartbeat (
    heartbeat_id BIGSERIAL PRIMARY KEY,
    camera_id VARCHAR(36) NOT NULL REFERENCES public.camera(camera_id) ON DELETE CASCADE,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fps_observed NUMERIC(6, 2),
    bitrate_kbps NUMERIC(10, 2),
    dropped_frames INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_camera_heartbeat_camera_id ON public.camera_heartbeat(camera_id);
CREATE INDEX IF NOT EXISTS ix_camera_heartbeat_received_at ON public.camera_heartbeat(received_at);

-- 4.5 Virtual Tripwire Configurations
CREATE TABLE IF NOT EXISTS public.virtual_tripwire_config (
    tripwire_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    camera_id VARCHAR(36) NOT NULL REFERENCES public.camera(camera_id) ON DELETE CASCADE,
    label VARCHAR(128) NOT NULL,
    line_coords JSONB NOT NULL DEFAULT '[[0.1, 0.5], [0.9, 0.5]]'::jsonb,
    direction_mode VARCHAR(32) NOT NULL DEFAULT 'BIDIRECTIONAL' CHECK (direction_mode IN ('BIDIRECTIONAL', 'ENTRY_ONLY', 'EXIT_ONLY', 'ENTRY', 'EXIT', 'BOTH')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tripwire_camera ON public.virtual_tripwire_config(camera_id);

-- ==============================================================================
-- 5. PRODUCT & MATERIAL MASTER CATALOG
-- ==============================================================================

-- 5.1 Discrete Products
CREATE TABLE IF NOT EXISTS public.product (
    product_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    sku_code VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(128) NOT NULL,
    pack_size INTEGER NOT NULL CHECK (pack_size > 0),
    unit_price NUMERIC(12, 2) NOT NULL,
    case_price NUMERIC(12, 2) NOT NULL,
    reorder_threshold INTEGER NOT NULL DEFAULT 0,
    rfid_epc_prefix VARCHAR(64),
    avg_unit_weight_g NUMERIC(10, 2),
    vision_class_id INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_product_sku_code ON public.product(sku_code);
CREATE INDEX IF NOT EXISTS ix_product_vision_class_id ON public.product(vision_class_id);

-- 5.2 Initial Stock Baseline Verification
CREATE TABLE IF NOT EXISTS public.initial_stock_verification (
    verification_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    product_id VARCHAR(36) NOT NULL REFERENCES public.product(product_id) ON DELETE CASCADE,
    sku_code VARCHAR(64) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    camera_id VARCHAR(36) REFERENCES public.camera(camera_id) ON DELETE SET NULL,
    ai_proposed_count INTEGER NOT NULL,
    verified_count INTEGER,
    difference INTEGER,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING_VERIFICATION' CHECK (status IN ('PENDING_VERIFICATION', 'VERIFIED_ACCURATE', 'CORRECTED', 'REJECTED')),
    verified_by VARCHAR(128),
    correction_reason VARCHAR(255),
    snapshot_url TEXT,
    model_version VARCHAR(64) DEFAULT 'yolox_retail_v8',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_stock_verif_prod_status ON public.initial_stock_verification(product_id, status);
CREATE INDEX IF NOT EXISTS ix_initial_stock_verification_sku_code ON public.initial_stock_verification(sku_code);

-- 5.3 Pending Product Identification (Unmapped Runtime Detections)
CREATE TABLE IF NOT EXISTS public.pending_product_identification (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    camera_id VARCHAR(36) REFERENCES public.camera(camera_id) ON DELETE SET NULL,
    vision_class_id INTEGER NOT NULL,
    detected_label VARCHAR(128) NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.5000,
    snapshot_url TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING_MAPPING' CHECK (status IN ('PENDING_MAPPING', 'MAPPED_TO_SKU', 'CREATED_NEW_PRODUCT', 'IGNORED')),
    mapped_sku VARCHAR(64),
    mapped_product_id VARCHAR(36) REFERENCES public.product(product_id) ON DELETE SET NULL,
    reviewed_by VARCHAR(128),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_pending_prod_id_vision ON public.pending_product_identification(vision_class_id);
CREATE INDEX IF NOT EXISTS idx_pending_prod_status ON public.pending_product_identification(status);

-- 5.4 Industrial & Stacked Material Catalog
CREATE TABLE IF NOT EXISTS public.material (
    material_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name VARCHAR(255) NOT NULL,
    sku_code VARCHAR(64) UNIQUE NOT NULL,
    category VARCHAR(64) NOT NULL,
    deployment_profile VARCHAR(64) NOT NULL DEFAULT 'WAREHOUSE_DISPATCH' CHECK (deployment_profile IN ('RETAIL_EXIT', 'WAREHOUSE_DISPATCH', 'INDUSTRIAL_PERIMETER')),
    count_unit VARCHAR(32) NOT NULL DEFAULT 'piece',
    packaging_type VARCHAR(64) NOT NULL DEFAULT 'loose_unit',
    dimensions JSONB,
    nominal_unit_weight_kg NUMERIC(10, 3),
    weight_tolerance_pct NUMERIC(5, 2) NOT NULL DEFAULT 5.0,
    length_m NUMERIC(8, 3),
    diameter_mm NUMERIC(8, 2),
    area_sqm NUMERIC(8, 3),
    volume_cbm NUMERIC(8, 3),
    bundle_quantity INTEGER,
    units_per_package INTEGER NOT NULL DEFAULT 1,
    counting_tier VARCHAR(32) NOT NULL DEFAULT 'SINGLE_UNIT' CHECK (counting_tier IN ('SINGLE_UNIT', 'PACKAGED_BOX', 'BULK_MATERIAL')),
    barcode VARCHAR(64),
    rfid_epc_prefix VARCHAR(64),
    visual_attributes JSONB,
    approved_model_class VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('DRAFT', 'DATA_COLLECTION', 'ANNOTATION', 'TRAINING', 'EVALUATION', 'SHADOW', 'APPROVED', 'ACTIVE')),
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revision INTEGER NOT NULL DEFAULT 1,
    created_by VARCHAR(128) NOT NULL DEFAULT 'system',
    approved_by VARCHAR(128),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_material_sku_code ON public.material(sku_code);

-- 5.5 Package Definitions
CREATE TABLE IF NOT EXISTS public.package_definition (
    definition_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    material_id VARCHAR(36) NOT NULL REFERENCES public.material(material_id) ON DELETE CASCADE,
    units_per_package INTEGER NOT NULL CHECK (units_per_package > 0),
    package_barcode VARCHAR(64),
    rfid_prefix VARCHAR(64),
    gross_weight_kg NUMERIC(10, 3),
    net_weight_kg NUMERIC(10, 3),
    tolerance_range_pct NUMERIC(5, 2) NOT NULL DEFAULT 5.0,
    effective_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_end TIMESTAMPTZ,
    evidence_source VARCHAR(64) NOT NULL DEFAULT 'MANUFACTURER_SPEC',
    approval_status VARCHAR(32) NOT NULL DEFAULT 'APPROVED' CHECK (approval_status IN ('PENDING', 'APPROVED', 'SUPERSEDED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_package_definition_material_id ON public.package_definition(material_id);

-- ==============================================================================
-- 6. EMPLOYEES & IDENTITY
-- ==============================================================================

-- 6.1 Shifts
CREATE TABLE IF NOT EXISTS public.shift (
    shift_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    label VARCHAR(128) NOT NULL,
    starts_at VARCHAR(8) NOT NULL,
    ends_at VARCHAR(8) NOT NULL
);

-- 6.2 Employees & Face Embeddings
CREATE TABLE IF NOT EXISTS public.employee (
    employee_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    employee_code VARCHAR(32) UNIQUE,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(128) NOT NULL,
    rfid_badge_id VARCHAR(128) UNIQUE NOT NULL,
    shift_id VARCHAR(36) REFERENCES public.shift(shift_id) ON DELETE SET NULL,
    active_flag BOOLEAN NOT NULL DEFAULT TRUE,
    face_embedding JSONB,
    embedding_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_employee_rfid_badge_id ON public.employee(rfid_badge_id);
CREATE INDEX IF NOT EXISTS ix_employee_code ON public.employee(employee_code);

-- ==============================================================================
-- 7. INVOICES, BILLS & SENSORY EXIT EVENTS
-- ==============================================================================

-- 7.1 Invoices & Billed Manifests
CREATE TABLE IF NOT EXISTS public.invoice (
    invoice_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    invoice_number VARCHAR(128) UNIQUE NOT NULL,
    carrier_name VARCHAR(255) NOT NULL,
    store_destination VARCHAR(255) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'SCAN' CHECK (source IN ('SCAN', 'EMAIL', 'API')),
    raw_file_url TEXT NOT NULL,
    ocr_model_version VARCHAR(64) NOT NULL,
    extraction_confidence NUMERIC(5, 4) NOT NULL,
    extracted_json JSONB NOT NULL,
    declared_total_units INTEGER,
    linked_event_id VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_invoice_invoice_number ON public.invoice(invoice_number);

-- 7.2 Exit Verification Events
CREATE TABLE IF NOT EXISTS public.exit_event (
    event_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lane_id VARCHAR(36) NOT NULL REFERENCES public.lane(lane_id) ON DELETE CASCADE,
    employee_id VARCHAR(36) REFERENCES public.employee(employee_id) ON DELETE SET NULL,
    employee_match_confidence NUMERIC(5, 4),
    cases_detected INTEGER NOT NULL DEFAULT 0,
    units_detected INTEGER NOT NULL DEFAULT 0,
    vision_count INTEGER NOT NULL DEFAULT 0,
    vision_confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
    rfid_count INTEGER,
    weight_kg NUMERIC(10, 3),
    weight_estimated_units INTEGER,
    consensus_units INTEGER NOT NULL DEFAULT 0,
    consensus_method VARCHAR(64) NOT NULL DEFAULT 'weighted_vote_v2',
    invoice_id VARCHAR(36) REFERENCES public.invoice(invoice_id) ON DELETE SET NULL,
    declared_units INTEGER,
    delta_units INTEGER NOT NULL DEFAULT 0,
    verdict VARCHAR(32) NOT NULL DEFAULT 'PASS' CHECK (verdict IN ('PASS', 'MATCH', 'MISMATCH', 'PARTIAL', 'UNVERIFIED', 'REVIEW_REQUIRED')),
    severity VARCHAR(32) NOT NULL DEFAULT 'NONE' CHECK (severity IN ('NONE', 'LOW', 'MEDIUM', 'HIGH')),
    snapshot_url TEXT,
    clip_url TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_exit_event_lane_ts ON public.exit_event(lane_id, ts);
CREATE INDEX IF NOT EXISTS ix_exit_event_severity ON public.exit_event(severity);
CREATE INDEX IF NOT EXISTS ix_exit_event_ts ON public.exit_event(ts);

-- 7.3 Exit Event Line Items
CREATE TABLE IF NOT EXISTS public.exit_event_line_item (
    line_item_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    event_id VARCHAR(36) NOT NULL REFERENCES public.exit_event(event_id) ON DELETE CASCADE,
    product_id VARCHAR(36) NOT NULL REFERENCES public.product(product_id) ON DELETE CASCADE,
    cases_qty INTEGER NOT NULL DEFAULT 0,
    units_qty INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_line_item_event ON public.exit_event_line_item(event_id);

-- 7.4 Vision Detections (Granular bounding box trace)
CREATE TABLE IF NOT EXISTS public.vision_detection (
    detection_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    event_id VARCHAR(36) REFERENCES public.exit_event(event_id) ON DELETE SET NULL,
    camera_id VARCHAR(36) REFERENCES public.camera(camera_id) ON DELETE SET NULL,
    frame_ts TIMESTAMPTZ NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    bbox JSONB NOT NULL,
    class_label VARCHAR(64) NOT NULL,
    product_id VARCHAR(36) REFERENCES public.product(product_id) ON DELETE SET NULL,
    confidence NUMERIC(5, 4) NOT NULL,
    track_id VARCHAR(64),
    category VARCHAR(32) NOT NULL DEFAULT 'GENERAL_OBJECT',
    snapshot_url TEXT,
    direction VARCHAR(32) DEFAULT 'IN'
);
CREATE INDEX IF NOT EXISTS idx_vis_det_event ON public.vision_detection(event_id);
CREATE INDEX IF NOT EXISTS idx_vis_det_camera ON public.vision_detection(camera_id);

-- 7.5 RFID Tag Reads
CREATE TABLE IF NOT EXISTS public.rfid_read (
    read_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    event_id VARCHAR(36) NOT NULL REFERENCES public.exit_event(event_id) ON DELETE CASCADE,
    epc_tag VARCHAR(128) NOT NULL,
    antenna_id VARCHAR(64) NOT NULL,
    rssi NUMERIC(6, 2),
    read_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rfid_event ON public.rfid_read(event_id);

-- 7.6 Scale Weight Readings
CREATE TABLE IF NOT EXISTS public.weight_reading (
    reading_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    event_id VARCHAR(36) NOT NULL REFERENCES public.exit_event(event_id) ON DELETE CASCADE,
    sensor_id VARCHAR(64) NOT NULL,
    weight_kg NUMERIC(10, 3) NOT NULL,
    read_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_weight_event ON public.weight_reading(event_id);

-- 7.7 Face Match Verification Attempts
CREATE TABLE IF NOT EXISTS public.face_match_attempt (
    attempt_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    event_id VARCHAR(36) NOT NULL REFERENCES public.exit_event(event_id) ON DELETE CASCADE,
    matched_employee_id VARCHAR(36) REFERENCES public.employee(employee_id) ON DELETE SET NULL,
    similarity NUMERIC(5, 4) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    decision VARCHAR(32) NOT NULL CHECK (decision IN ('MATCHED', 'NO_MATCH', 'LOW_CONFIDENCE', 'DISABLED', 'BYPASS')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_face_match_event ON public.face_match_attempt(event_id);

-- 7.8 Person Appearance Summary (Non-invasive Re-ID)
CREATE TABLE IF NOT EXISTS public.person_appearance_summary (
    summary_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    event_id VARCHAR(36) NOT NULL REFERENCES public.exit_event(event_id) ON DELETE CASCADE,
    face_match_attempt_id VARCHAR(36) REFERENCES public.face_match_attempt(attempt_id) ON DELETE SET NULL,
    clothing_top_color VARCHAR(64) NOT NULL,
    clothing_bottom_color VARCHAR(64) NOT NULL,
    build_category VARCHAR(32) NOT NULL CHECK (build_category IN ('SHORTER','AVERAGE','TALLER','UNKNOWN')),
    build_confidence NUMERIC(5, 4) NOT NULL,
    accessories JSONB NOT NULL DEFAULT '[]'::jsonb,
    accessories_confidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version VARCHAR(64) NOT NULL DEFAULT 'appearance-reid-v1.0',
    reid_embedding JSONB,
    reid_cluster_id VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_appearance_cluster_created ON public.person_appearance_summary(reid_cluster_id, created_at);

-- ==============================================================================
-- 8. ALERTS, ALARMS & DISPATCH
-- ==============================================================================

-- 8.1 Real-time Security & Safety Alerts
CREATE TABLE IF NOT EXISTS public.alert (
    alert_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    event_id VARCHAR(36) REFERENCES public.exit_event(event_id) ON DELETE SET NULL,
    camera_id VARCHAR(36) REFERENCES public.camera(camera_id) ON DELETE SET NULL,
    alert_type VARCHAR(64) NOT NULL CHECK (alert_type IN ('SENSOR_DISAGREEMENT', 'OVER_CARRY', 'UNDER_DECLARE', 'UNAUTHORIZED_ACCESS', 'INTRUSION', 'CAMERA_OFFLINE', 'FIRE_HAZARD', 'SUSPICIOUS_BEHAVIOR', 'PPE_VIOLATION', 'MATERIAL_DEFECT')),
    severity VARCHAR(32) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH')),
    delta_units INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
    resolved_by VARCHAR(128),
    resolution_note TEXT,
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_alert_camera_id ON public.alert(camera_id);
CREATE INDEX IF NOT EXISTS ix_alert_event_id ON public.alert(event_id);
CREATE INDEX IF NOT EXISTS ix_alert_status ON public.alert(status);
CREATE INDEX IF NOT EXISTS ix_alert_severity ON public.alert(severity);
CREATE INDEX IF NOT EXISTS ix_alert_created_at ON public.alert(created_at);

-- 8.2 Physical Hardware & Siren Dispatches
CREATE TABLE IF NOT EXISTS public.alarm_dispatch (
    dispatch_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    alert_id VARCHAR(36) NOT NULL REFERENCES public.alert(alert_id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL CHECK (channel IN ('SIREN', 'STROBE', 'TTS', 'TURNSTILE_LOCK', 'PUSH', 'SMS')),
    status VARCHAR(32) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'SENT', 'ACKED', 'FAILED')),
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_alarm_dispatch_alert ON public.alarm_dispatch(alert_id);

-- ==============================================================================
-- 9. INVENTORY LEDGER, MOVEMENTS & DISPATCH
-- ==============================================================================

-- 9.1 Real-Time Material Inventory Balances
CREATE TABLE IF NOT EXISTS public.material_inventory_balance (
    balance_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    material_id VARCHAR(36) NOT NULL REFERENCES public.material(material_id) ON DELETE CASCADE,
    location_id VARCHAR(64) NOT NULL DEFAULT 'MAIN_WAREHOUSE',
    opening_stock INTEGER NOT NULL DEFAULT 0,
    incoming_confirmed INTEGER NOT NULL DEFAULT 0,
    outgoing_confirmed INTEGER NOT NULL DEFAULT 0,
    defective_stock INTEGER NOT NULL DEFAULT 0,
    adjusted_stock INTEGER NOT NULL DEFAULT 0,
    current_stock INTEGER NOT NULL DEFAULT 0,
    last_reconciled_at TIMESTAMPTZ,
    last_transaction_id VARCHAR(36),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT idx_balance_mat_loc UNIQUE (material_id, location_id)
);
CREATE INDEX IF NOT EXISTS ix_mat_inv_bal_loc ON public.material_inventory_balance(location_id);
CREATE INDEX IF NOT EXISTS ix_mat_inv_bal_mat ON public.material_inventory_balance(material_id);

-- 9.2 Immutable Material Movement Transaction Ledger
CREATE TABLE IF NOT EXISTS public.material_movement_ledger (
    ledger_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    transaction_type VARCHAR(32) NOT NULL CHECK (transaction_type IN ('IN', 'OUT', 'ADJUSTMENT', 'TRANSFER_IN', 'TRANSFER_OUT', 'RETURN')),
    material_id VARCHAR(36) NOT NULL REFERENCES public.material(material_id) ON DELETE CASCADE,
    camera_id VARCHAR(36) REFERENCES public.camera(camera_id) ON DELETE SET NULL,
    zone_id VARCHAR(64),
    tripwire_id VARCHAR(36) REFERENCES public.virtual_tripwire_config(tripwire_id) ON DELETE SET NULL,
    track_id VARCHAR(64),
    direction VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN' CHECK (direction IN ('ENTRY', 'EXIT', 'TRAVERSAL', 'UNKNOWN', 'IN', 'OUT')),
    person_id VARCHAR(36) REFERENCES public.employee(employee_id) ON DELETE SET NULL,
    person_name VARCHAR(255) NOT NULL DEFAULT 'UNKNOWN_PERSON',
    person_identity_status VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN_PERSON' CHECK (person_identity_status IN ('VERIFIED_KNOWN', 'UNKNOWN_PERSON', 'UNAVAILABLE')),
    carrier_relation VARCHAR(32) NOT NULL DEFAULT 'standalone',
    packaging_type VARCHAR(64) NOT NULL DEFAULT 'loose_unit',
    package_quantity INTEGER NOT NULL DEFAULT 0,
    units_per_package INTEGER NOT NULL DEFAULT 1,
    unit_quantity INTEGER NOT NULL DEFAULT 0,
    defect_status VARCHAR(32) NOT NULL DEFAULT 'NORMAL' CHECK (defect_status IN ('NORMAL', 'DAMAGED', 'DEFECTIVE', 'UNKNOWN_CONDITION')),
    defect_severity VARCHAR(32) NOT NULL DEFAULT 'NONE',
    confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.9500,
    discrepancy_units INTEGER NOT NULL DEFAULT 0,
    discrepancy_reason VARCHAR(255),
    source_frame_path TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ledger_mat_ts ON public.material_movement_ledger(material_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_ledger_cam_ts ON public.material_movement_ledger(camera_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_ledger_track_id ON public.material_movement_ledger(track_id);

-- 9.3 Physical Packaging & Material Defect Events
CREATE TABLE IF NOT EXISTS public.material_defect_event (
    defect_event_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    ledger_id VARCHAR(36) REFERENCES public.material_movement_ledger(ledger_id) ON DELETE SET NULL,
    material_id VARCHAR(36) NOT NULL REFERENCES public.material(material_id) ON DELETE CASCADE,
    camera_id VARCHAR(36) REFERENCES public.camera(camera_id) ON DELETE SET NULL,
    defect_class VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.9500,
    affected_units INTEGER NOT NULL DEFAULT 1,
    snapshot_url TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'QUARANTINED' CHECK (status IN ('QUARANTINED', 'ACCEPTED_WITH_CONCESSION', 'REJECTED', 'SCRAPPED')),
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_material_defect_event_material_id ON public.material_defect_event(material_id);
CREATE INDEX IF NOT EXISTS ix_material_defect_event_created_at ON public.material_defect_event(created_at);

-- 9.4 Dispatch Sessions & Dock Manifest Reconciliation
CREATE TABLE IF NOT EXISTS public.dispatch_session (
    session_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    dock_lane_id VARCHAR(36) NOT NULL REFERENCES public.lane(lane_id) ON DELETE CASCADE,
    manifest_id VARCHAR(128),
    carrier_employee_id VARCHAR(36) REFERENCES public.employee(employee_id) ON DELETE SET NULL,
    vehicle_identifier VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'FLAGGED_DISCREPANCY', 'ABORTED')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    before_count JSONB NOT NULL DEFAULT '{}'::jsonb,
    after_count JSONB NOT NULL DEFAULT '{}'::jsonb,
    removed_delta JSONB NOT NULL DEFAULT '{}'::jsonb,
    manifest_expected JSONB NOT NULL DEFAULT '{}'::jsonb,
    discrepancy_type VARCHAR(32) NOT NULL DEFAULT 'MATCH' CHECK (discrepancy_type IN ('MATCH', 'OVER_AUTHORIZED', 'UNDER_COUNT', 'UNMANIFESTED_SKU')),
    discrepancy_magnitude INTEGER NOT NULL DEFAULT 0,
    tracking_interrupted_seconds NUMERIC(8, 2) NOT NULL DEFAULT 0.0,
    archival_snapshot_url TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dispatch_dock_lane ON public.dispatch_session(dock_lane_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_status ON public.dispatch_session(status);

-- ==============================================================================
-- 10. ACCESS CONTROL, VEHICLES & AUXILIARY PERIMETER
-- ==============================================================================

-- 10.1 Tripwire Crossing Events (Turnstiles, EAS Gates)
CREATE TABLE IF NOT EXISTS public.tripwire_crossing_event (
    crossing_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tripwire_id VARCHAR(36) NOT NULL REFERENCES public.virtual_tripwire_config(tripwire_id) ON DELETE CASCADE,
    camera_id VARCHAR(36) NOT NULL,
    track_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    direction VARCHAR(16) NOT NULL CHECK (direction IN ('ENTRY', 'EXIT', 'UNKNOWN')),
    entity_type VARCHAR(32) NOT NULL DEFAULT 'PERSON',
    biometric_status VARCHAR(32) NOT NULL DEFAULT 'UNAVAILABLE' CHECK (biometric_status IN ('VERIFIED_KNOWN', 'UNKNOWN_INTRUDER', 'UNAVAILABLE')),
    matched_employee_id VARCHAR(36) REFERENCES public.employee(employee_id) ON DELETE SET NULL,
    is_tailgating BOOLEAN NOT NULL DEFAULT FALSE,
    tailgating_details JSONB,
    snapshot_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_crossing_tripwire ON public.tripwire_crossing_event(tripwire_id);
CREATE INDEX IF NOT EXISTS idx_crossing_timestamp ON public.tripwire_crossing_event(timestamp);

-- 10.2 Door Access Control Events
CREATE TABLE IF NOT EXISTS public.access_control_event (
    access_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    door_id VARCHAR(64) NOT NULL,
    employee_id VARCHAR(36) REFERENCES public.employee(employee_id) ON DELETE SET NULL,
    credential_type VARCHAR(32) NOT NULL,
    access_status VARCHAR(32) NOT NULL,
    denial_reason VARCHAR(128),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_access_control_event_door_id ON public.access_control_event(door_id);
CREATE INDEX IF NOT EXISTS ix_access_control_event_event_time ON public.access_control_event(event_time);

-- 10.3 Vehicle & License Plate Detections
CREATE TABLE IF NOT EXISTS public.vehicle_detection (
    detection_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    camera_id VARCHAR(36) NOT NULL REFERENCES public.camera(camera_id) ON DELETE CASCADE,
    license_plate VARCHAR(32),
    plate_confidence NUMERIC(5, 4),
    vehicle_class VARCHAR(32) NOT NULL,
    color VARCHAR(32),
    direction VARCHAR(32),
    watchlist_hit BOOLEAN NOT NULL DEFAULT FALSE,
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_vehicle_detection_camera_id ON public.vehicle_detection(camera_id);
CREATE INDEX IF NOT EXISTS ix_vehicle_detection_license_plate ON public.vehicle_detection(license_plate);
CREATE INDEX IF NOT EXISTS ix_vehicle_detection_event_time ON public.vehicle_detection(event_time);

-- 10.4 Static Image & Picture-on-Wall Detections
CREATE TABLE IF NOT EXISTS public.static_image_detection (
    detection_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    camera_id VARCHAR(36) NOT NULL REFERENCES public.camera(camera_id) ON DELETE CASCADE,
    frame_ts TIMESTAMPTZ NOT NULL,
    bbox JSONB NOT NULL,
    liveness_score NUMERIC(5, 4) NOT NULL,
    classification VARCHAR(64) NOT NULL CHECK (classification IN ('RELIGIOUS_IMAGE','PERSON_PHOTO','POSTER_OR_SIGNAGE','SCREEN_DISPLAY','UNCLASSIFIED_STATIC')),
    classification_confidence NUMERIC(5, 4) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    suppressed_alert BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_static_cam_time ON public.static_image_detection(camera_id, frame_ts);

-- 10.5 Smart Video Wall Layouts
CREATE TABLE IF NOT EXISTS public.smart_wall_layout (
    layout_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name VARCHAR(128) NOT NULL,
    grid_type VARCHAR(16) NOT NULL,
    camera_mappings JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10.6 Cryptographic Evidence Artifacts (Chain of Custody)
CREATE TABLE IF NOT EXISTS public.evidence_artifact (
    artifact_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    event_id VARCHAR(36) NOT NULL REFERENCES public.exit_event(event_id) ON DELETE CASCADE,
    camera_id VARCHAR(36) REFERENCES public.camera(camera_id) ON DELETE SET NULL,
    artifact_type VARCHAR(32) NOT NULL,
    s3_key VARCHAR(512) NOT NULL,
    cryptographic_hash VARCHAR(128) NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retention_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_evidence_artifact_event_id ON public.evidence_artifact(event_id);

-- 10.7 Audit Log (Full System Activity Trail)
CREATE TABLE IF NOT EXISTS public.audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    action VARCHAR(64) NOT NULL,
    actor_id VARCHAR(36),
    actor_type VARCHAR(32) NOT NULL CHECK (actor_type IN ('USER', 'SYSTEM', 'MODEL')),
    before_state JSONB,
    after_state JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_log_entity_type ON public.audit_log(entity_type);
CREATE INDEX IF NOT EXISTS ix_audit_log_entity_id ON public.audit_log(entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON public.audit_log(created_at);

-- 10.8 Database Migration Tracker Table
CREATE TABLE IF NOT EXISTS public.alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);
INSERT INTO public.alembic_version (version_num) 
VALUES ('v8_cpu_production')
ON CONFLICT (version_num) DO NOTHING;

-- ==============================================================================

-- ==============================================================================
-- 11. PLATFORM CONTROL-PLANE TABLES (MULTI-TENANCY & FLEET GOVERNANCE)
-- ==============================================================================
-- Strictly isolated from tenant operational stores (cameras, frames, stock, events).
-- Manages platform billing, store onboarding, super admin access, and company registries.

-- 11.1 Platform Tenant / Company Registry
CREATE TABLE IF NOT EXISTS public.platform_tenant (
    tenant_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name VARCHAR(255) UNIQUE NOT NULL,
    slug VARCHAR(64) UNIQUE NOT NULL,
    db_identifier VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PROVISIONING' CHECK (status IN ('PROVISIONING', 'ACTIVE', 'SUSPENDED', 'DECOMMISSIONED')),
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata',
    currency VARCHAR(16) NOT NULL DEFAULT 'INR',
    contact_email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_platform_tenant_slug ON public.platform_tenant(slug);
CREATE INDEX IF NOT EXISTS ix_platform_tenant_status ON public.platform_tenant(status);

-- 11.2 Platform Master Super Admin Account
CREATE TABLE IF NOT EXISTS public.platform_super_admin (
    admin_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'SUPER_ADMIN',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_platform_super_admin_username ON public.platform_super_admin(username);
CREATE INDEX IF NOT EXISTS ix_platform_super_admin_email ON public.platform_super_admin(email);

-- 11.3 Platform-Level Immutable Audit Log
CREATE TABLE IF NOT EXISTS public.platform_audit_log (
    log_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    actor_id VARCHAR(36) NOT NULL,
    actor_type VARCHAR(32) NOT NULL DEFAULT 'SUPER_ADMIN',
    action VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(36),
    details JSONB,
    ip_address VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_platform_audit_log_action ON public.platform_audit_log(action);
CREATE INDEX IF NOT EXISTS ix_platform_audit_log_tenant_id ON public.platform_audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_audit_log_created_at ON public.platform_audit_log(created_at);

-- 11.4 Platform Subscription Tiers & Quota Definitions
CREATE TABLE IF NOT EXISTS public.platform_subscription_tier (
    tier_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name VARCHAR(64) UNIQUE NOT NULL,
    max_cameras INTEGER NOT NULL DEFAULT 4,
    price_cents INTEGER NOT NULL DEFAULT 0,
    currency VARCHAR(16) NOT NULL DEFAULT 'INR',
    billing_cycle VARCHAR(16) NOT NULL DEFAULT 'MONTHLY',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11.5 Store Tenant Subscriptions & Payment Verification
CREATE TABLE IF NOT EXISTS public.platform_store_subscription (
    subscription_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tenant_id VARCHAR(36) UNIQUE NOT NULL,
    tier_id VARCHAR(36) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'PAST_DUE', 'SUSPENDED', 'CANCELLED')),
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_period_end TIMESTAMPTZ NOT NULL,
    grace_period_days INTEGER NOT NULL DEFAULT 7,
    payment_verified BOOLEAN NOT NULL DEFAULT TRUE,
    auto_renew BOOLEAN NOT NULL DEFAULT TRUE,
    last_payment_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_platform_store_subscription_tenant ON public.platform_store_subscription(tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_store_subscription_status ON public.platform_store_subscription(status);

-- 11.6 Platform Billing Invoices
CREATE TABLE IF NOT EXISTS public.platform_billing_invoice (
    invoice_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tenant_id VARCHAR(36) NOT NULL,
    subscription_id VARCHAR(36),
    amount_cents INTEGER NOT NULL DEFAULT 0,
    currency VARCHAR(16) NOT NULL DEFAULT 'INR',
    status VARCHAR(32) NOT NULL DEFAULT 'PAID' CHECK (status IN ('PAID', 'UNPAID', 'DELINQUENT', 'VOID')),
    due_date TIMESTAMPTZ NOT NULL,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_platform_billing_invoice_tenant ON public.platform_billing_invoice(tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_billing_invoice_status ON public.platform_billing_invoice(status);

-- ==============================================================================
-- 12. AUTOMATIC UPDATED_AT TRIGGERS
-- ==============================================================================
CREATE OR REPLACE TRIGGER trg_threshold_config_updated_at
BEFORE UPDATE ON public.threshold_config
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_product_updated_at
BEFORE UPDATE ON public.product
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_material_updated_at
BEFORE UPDATE ON public.material
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_tripwire_updated_at
BEFORE UPDATE ON public.virtual_tripwire_config
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_smart_wall_updated_at
BEFORE UPDATE ON public.smart_wall_layout
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_mat_balance_updated_at
BEFORE UPDATE ON public.material_inventory_balance
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_platform_tenant_updated_at
BEFORE UPDATE ON public.platform_tenant
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_platform_store_sub_updated_at
BEFORE UPDATE ON public.platform_store_subscription
FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

-- ==============================================================================
-- 13. SEED DATA & USER ACTIVATION
-- ==============================================================================
-- Requirement: ONLY ONE ID ACTIVATED (Software Owner & Store Admin)
-- Email: ces@gmail.com
-- Password: Ces@1234
-- Store Role: ADMIN
-- Platform Role: SUPER_ADMIN
-- Bcrypt Hash (cost factor 12): $2b$12$3e3aXyOsHZ.ycnU3X3VIxuHQX9tCLHkFjvYefjhYrLr1xKbtUa0Tq
-- ==============================================================================

-- 13.1 Ensure Default Store exists
INSERT INTO public.store (store_id, name, address, timezone)
VALUES (
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    'Flagship Operations Facility',
    'Main Industrial Estate, Gate 1',
    'UTC'
)
ON CONFLICT (store_id) DO UPDATE 
SET name = EXCLUDED.name,
    address = EXCLUDED.address,
    timezone = EXCLUDED.timezone;

-- 13.2 Ensure Default Threshold Config exists
INSERT INTO public.threshold_config (config_id, store_id, unit_tolerance, pct_tolerance, low_severity_threshold, med_severity_threshold, high_severity_threshold)
VALUES (
    'th_default_001',
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    0,
    0.0,
    1,
    3,
    6
)
ON CONFLICT (config_id) DO NOTHING;

-- 13.3 Deactivate or Remove any previous demo/test users to guarantee ONLY ONE ACTIVE USER
UPDATE public.app_user
SET is_active = FALSE
WHERE email != 'ces@gmail.com';

-- 13.4 Insert or Activate the single Software Owner account (Store-level Admin)
INSERT INTO public.app_user (
    user_id,
    email,
    username,
    password_hash,
    role,
    store_id,
    mfa_enabled,
    is_active,
    created_at
)
VALUES (
    '9f405af6-751b-44c4-8d27-4734d4a501db',
    'ces@gmail.com',
    'ces',
    '$2b$12$3e3aXyOsHZ.ycnU3X3VIxuHQX9tCLHkFjvYefjhYrLr1xKbtUa0Tq',
    'ADMIN',
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    FALSE,
    TRUE,
    NOW()
)
ON CONFLICT (email) DO UPDATE 
SET 
    username = EXCLUDED.username,
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    is_active = TRUE,
    store_id = EXCLUDED.store_id;

-- 13.5 Insert or Activate Platform Super Admin account (Control-plane Owner)
INSERT INTO public.platform_super_admin (
    admin_id,
    username,
    email,
    password_hash,
    role,
    is_active,
    created_at
)
VALUES (
    'admin_root_001',
    'ces',
    'ces@gmail.com',
    '$2b$12$3e3aXyOsHZ.ycnU3X3VIxuHQX9tCLHkFjvYefjhYrLr1xKbtUa0Tq',
    'SUPER_ADMIN',
    TRUE,
    NOW()
)
ON CONFLICT (email) DO UPDATE 
SET 
    username = EXCLUDED.username,
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    is_active = TRUE;

-- 13.6 Subscription Tiers Setup
INSERT INTO public.platform_subscription_tier (tier_id, name, max_cameras, price_cents, currency, billing_cycle)
VALUES 
    ('tier_starter_01', 'Starter', 4, 499900, 'INR', 'MONTHLY'),
    ('tier_pro_01', 'Professional', 16, 1499900, 'INR', 'MONTHLY'),
    ('tier_enterprise_01', 'Enterprise', 64, 4999900, 'INR', 'MONTHLY')
ON CONFLICT (tier_id) DO UPDATE
SET name = EXCLUDED.name, max_cameras = EXCLUDED.max_cameras, price_cents = EXCLUDED.price_cents;

-- 13.7 Tenant Master Registry Linking
INSERT INTO public.platform_tenant (tenant_id, name, slug, db_identifier, status, timezone, currency, contact_email)
VALUES (
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    'Flagship Operations Facility',
    'flagship-store',
    'flagship_db',
    'ACTIVE',
    'UTC',
    'INR',
    'ces@gmail.com'
)
ON CONFLICT (tenant_id) DO UPDATE
SET name = EXCLUDED.name, status = EXCLUDED.status, contact_email = EXCLUDED.contact_email;

-- 13.8 Store Subscription Linking
INSERT INTO public.platform_store_subscription (
    subscription_id,
    tenant_id,
    tier_id,
    status,
    current_period_start,
    current_period_end,
    grace_period_days,
    payment_verified,
    auto_renew
)
VALUES (
    'sub_flagship_001',
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    'tier_enterprise_01',
    'ACTIVE',
    NOW(),
    NOW() + INTERVAL '365 days',
    7,
    TRUE,
    TRUE
)
ON CONFLICT (subscription_id) DO UPDATE
SET status = EXCLUDED.status, payment_verified = EXCLUDED.payment_verified;

-- 13.9 Initial Verified Billing Invoice
INSERT INTO public.platform_billing_invoice (
    invoice_id,
    tenant_id,
    subscription_id,
    amount_cents,
    currency,
    status,
    due_date,
    paid_at
)
VALUES (
    'inv_flagship_001',
    '0f8248a3-2947-4f6b-871d-5b6cb219e2c1',
    'sub_flagship_001',
    4999900,
    'INR',
    'PAID',
    NOW(),
    NOW()
)
ON CONFLICT (invoice_id) DO UPDATE
SET status = EXCLUDED.status, paid_at = EXCLUDED.paid_at;

-- ==============================================================================
-- 14. VERIFICATION QUERIES
-- ==============================================================================
-- Verify Single Active Store Admin
SELECT 'APP_USER' AS source, user_id, email, username, role, is_active FROM public.app_user WHERE is_active = TRUE;

-- Verify Single Active Platform Super Admin
SELECT 'PLATFORM_SUPER_ADMIN' AS source, admin_id, email, username, role, is_active FROM public.platform_super_admin WHERE is_active = TRUE;

-- Verify Total Platform & Store Tables Count
SELECT count(*) AS total_public_tables FROM information_schema.tables WHERE table_schema = 'public';
