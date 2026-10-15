-- =============================================================================
-- SEC-OPS RETAIL EXIT MONITORING SYSTEM // V8 PRODUCTION DDL & SEED
-- TARGET: Supabase (PostgreSQL 15+)
-- BASELINE: Clean state with ONLY Software Owner (ces@gmail.com / SUPER_ADMIN)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. PLATFORM CONTROL-PLANE TABLES (Multi-Tenant & Super Admin Registry)
-- -----------------------------------------------------------------------------

CREATE TABLE platform_audit_log (
	log_id VARCHAR(36) NOT NULL, 
	actor_id VARCHAR(36) NOT NULL, 
	actor_type VARCHAR(32) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	tenant_id VARCHAR(36), 
	details JSON, 
	ip_address VARCHAR(64), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (log_id)
);

CREATE INDEX ix_platform_audit_log_created_at ON platform_audit_log (created_at);

CREATE INDEX ix_platform_audit_log_action ON platform_audit_log (action);

CREATE INDEX ix_platform_audit_log_tenant_id ON platform_audit_log (tenant_id);

CREATE TABLE platform_billing_invoice (
	invoice_id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	subscription_id VARCHAR(36), 
	amount_cents INTEGER NOT NULL, 
	currency VARCHAR(16) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	due_date TIMESTAMP WITH TIME ZONE NOT NULL, 
	paid_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (invoice_id), 
	CONSTRAINT chk_platform_invoice_status CHECK (status IN ('PAID', 'UNPAID', 'DELINQUENT', 'VOID'))
);

CREATE INDEX ix_platform_billing_invoice_tenant_id ON platform_billing_invoice (tenant_id);

CREATE INDEX ix_platform_billing_invoice_status ON platform_billing_invoice (status);

CREATE TABLE platform_store_subscription (
	subscription_id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	tier_id VARCHAR(36) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	current_period_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	current_period_end TIMESTAMP WITH TIME ZONE NOT NULL, 
	grace_period_days INTEGER NOT NULL, 
	payment_verified BOOLEAN NOT NULL, 
	auto_renew BOOLEAN NOT NULL, 
	last_payment_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (subscription_id), 
	CONSTRAINT chk_platform_sub_status CHECK (status IN ('ACTIVE', 'PAST_DUE', 'SUSPENDED', 'CANCELLED'))
);

CREATE INDEX ix_platform_store_subscription_status ON platform_store_subscription (status);

CREATE UNIQUE INDEX ix_platform_store_subscription_tenant_id ON platform_store_subscription (tenant_id);

CREATE TABLE platform_subscription_tier (
	tier_id VARCHAR(36) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	max_cameras INTEGER NOT NULL, 
	price_cents INTEGER NOT NULL, 
	currency VARCHAR(16) NOT NULL, 
	billing_cycle VARCHAR(16) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (tier_id), 
	UNIQUE (name)
);

CREATE TABLE platform_super_admin (
	admin_id VARCHAR(36) NOT NULL, 
	username VARCHAR(64) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role VARCHAR(32) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (admin_id)
);

CREATE UNIQUE INDEX ix_platform_super_admin_username ON platform_super_admin (username);

CREATE UNIQUE INDEX ix_platform_super_admin_email ON platform_super_admin (email);

CREATE TABLE platform_tenant (
	tenant_id VARCHAR(36) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	slug VARCHAR(64) NOT NULL, 
	db_identifier VARCHAR(255) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	timezone VARCHAR(64) NOT NULL, 
	currency VARCHAR(16) NOT NULL, 
	contact_email VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (tenant_id), 
	CONSTRAINT chk_platform_tenant_status CHECK (status IN ('PROVISIONING', 'ACTIVE', 'SUSPENDED', 'DECOMMISSIONED')), 
	UNIQUE (name), 
	UNIQUE (db_identifier)
);

CREATE UNIQUE INDEX ix_platform_tenant_slug ON platform_tenant (slug);

CREATE INDEX ix_platform_tenant_status ON platform_tenant (status);


-- -----------------------------------------------------------------------------
-- 2. OPERATIONAL TENANT TABLES (Stores, Lanes, Cameras, Vision & Exit Tracking)
-- -----------------------------------------------------------------------------

CREATE TABLE audit_log (
	audit_id SERIAL NOT NULL, 
	entity_type VARCHAR(64) NOT NULL, 
	entity_id VARCHAR(36) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	actor_id VARCHAR(36), 
	actor_type VARCHAR(32) NOT NULL, 
	before_state JSON, 
	after_state JSON, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (audit_id), 
	CONSTRAINT chk_audit_actor_type CHECK (actor_type IN ('USER', 'SYSTEM', 'MODEL'))
);

CREATE INDEX ix_audit_log_created_at ON audit_log (created_at);

CREATE INDEX ix_audit_log_entity_type ON audit_log (entity_type);

CREATE INDEX ix_audit_log_entity_id ON audit_log (entity_id);

CREATE TABLE invoice (
	invoice_id VARCHAR(36) NOT NULL, 
	invoice_number VARCHAR(128) NOT NULL, 
	carrier_name VARCHAR(255) NOT NULL, 
	store_destination VARCHAR(255) NOT NULL, 
	source VARCHAR(32) NOT NULL, 
	raw_file_url TEXT NOT NULL, 
	ocr_model_version VARCHAR(64) NOT NULL, 
	extraction_confidence NUMERIC(5, 4) NOT NULL, 
	extracted_json JSON NOT NULL, 
	declared_total_units INTEGER, 
	linked_event_id VARCHAR(36), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (invoice_id), 
	CONSTRAINT chk_invoice_source CHECK (source IN ('SCAN', 'EMAIL', 'API'))
);

CREATE UNIQUE INDEX ix_invoice_invoice_number ON invoice (invoice_number);

CREATE TABLE material (
	material_id VARCHAR(36) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	sku_code VARCHAR(64) NOT NULL, 
	category VARCHAR(64) NOT NULL, 
	deployment_profile VARCHAR(64) NOT NULL, 
	count_unit VARCHAR(32) NOT NULL, 
	packaging_type VARCHAR(64) NOT NULL, 
	dimensions JSON, 
	nominal_unit_weight_kg NUMERIC(10, 3), 
	weight_tolerance_pct NUMERIC(5, 2) NOT NULL, 
	length_m NUMERIC(8, 3), 
	diameter_mm NUMERIC(8, 2), 
	area_sqm NUMERIC(8, 3), 
	volume_cbm NUMERIC(8, 3), 
	bundle_quantity INTEGER, 
	units_per_package INTEGER NOT NULL, 
	counting_tier VARCHAR(32) NOT NULL, 
	barcode VARCHAR(64), 
	rfid_epc_prefix VARCHAR(64), 
	visual_attributes JSON, 
	approved_model_class VARCHAR(64), 
	status VARCHAR(32) NOT NULL, 
	effective_from TIMESTAMP WITH TIME ZONE NOT NULL, 
	revision INTEGER NOT NULL, 
	created_by VARCHAR(128) NOT NULL, 
	approved_by VARCHAR(128), 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (material_id), 
	CONSTRAINT chk_material_status CHECK (status IN ('DRAFT', 'DATA_COLLECTION', 'ANNOTATION', 'TRAINING', 'EVALUATION', 'SHADOW', 'APPROVED', 'ACTIVE')), 
	CONSTRAINT chk_material_deployment_profile CHECK (deployment_profile IN ('RETAIL_EXIT', 'WAREHOUSE_DISPATCH', 'INDUSTRIAL_PERIMETER')), 
	CONSTRAINT chk_material_counting_tier CHECK (counting_tier IN ('SINGLE_UNIT', 'PACKAGED_BOX', 'BULK_MATERIAL'))
);

CREATE UNIQUE INDEX ix_material_sku_code ON material (sku_code);

CREATE TABLE product (
	product_id VARCHAR(36) NOT NULL, 
	sku_code VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	category VARCHAR(128) NOT NULL, 
	pack_size INTEGER NOT NULL, 
	unit_price NUMERIC(12, 2) NOT NULL, 
	case_price NUMERIC(12, 2) NOT NULL, 
	reorder_threshold INTEGER NOT NULL, 
	rfid_epc_prefix VARCHAR(64), 
	avg_unit_weight_g NUMERIC(10, 2), 
	vision_class_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (product_id), 
	CONSTRAINT chk_product_pack_size_pos CHECK (pack_size > 0)
);

CREATE INDEX ix_product_vision_class_id ON product (vision_class_id);

CREATE UNIQUE INDEX ix_product_sku_code ON product (sku_code);

CREATE TABLE shift (
	shift_id VARCHAR(36) NOT NULL, 
	label VARCHAR(128) NOT NULL, 
	starts_at VARCHAR(8) NOT NULL, 
	ends_at VARCHAR(8) NOT NULL, 
	PRIMARY KEY (shift_id)
);

CREATE TABLE smart_wall_layout (
	layout_id VARCHAR(36) NOT NULL, 
	name VARCHAR(128) NOT NULL, 
	grid_type VARCHAR(16) NOT NULL, 
	camera_mappings JSON NOT NULL, 
	is_default BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (layout_id)
);

CREATE TABLE store (
	store_id VARCHAR(36) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	address TEXT, 
	timezone VARCHAR(64) NOT NULL, 
	PRIMARY KEY (store_id)
);

CREATE TABLE app_user (
	user_id VARCHAR(36) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	username VARCHAR(64), 
	password_hash VARCHAR(255) NOT NULL, 
	role VARCHAR(32) NOT NULL, 
	store_id VARCHAR(36), 
	mfa_enabled BOOLEAN NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (user_id), 
	CONSTRAINT chk_app_user_role CHECK (role IN ('SUPERVISOR', 'ADMIN', 'VIEWER')), 
	FOREIGN KEY(store_id) REFERENCES store (store_id)
);

CREATE UNIQUE INDEX ix_app_user_username ON app_user (username);

CREATE UNIQUE INDEX ix_app_user_email ON app_user (email);

CREATE TABLE employee (
	employee_id VARCHAR(36) NOT NULL, 
	employee_code VARCHAR(32), 
	name VARCHAR(255) NOT NULL, 
	role VARCHAR(128) NOT NULL, 
	rfid_badge_id VARCHAR(128) NOT NULL, 
	shift_id VARCHAR(36), 
	active_flag BOOLEAN NOT NULL, 
	face_embedding JSON, 
	embedding_updated_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (employee_id), 
	FOREIGN KEY(shift_id) REFERENCES shift (shift_id)
);

CREATE UNIQUE INDEX ix_employee_rfid_badge_id ON employee (rfid_badge_id);

CREATE UNIQUE INDEX ix_employee_employee_code ON employee (employee_code);

CREATE TABLE lane (
	lane_id VARCHAR(36) NOT NULL, 
	label VARCHAR(128) NOT NULL, 
	store_id VARCHAR(36) NOT NULL, 
	camera_ids JSON NOT NULL, 
	rfid_antenna_id VARCHAR(128), 
	weight_sensor_id VARCHAR(128), 
	turnstile_ctrl_id VARCHAR(128), 
	status VARCHAR(32) NOT NULL, 
	last_heartbeat_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (lane_id), 
	CONSTRAINT chk_lane_status CHECK (status IN ('ONLINE', 'OFFLINE', 'DEGRADED')), 
	FOREIGN KEY(store_id) REFERENCES store (store_id)
);

CREATE TABLE material_inventory_balance (
	balance_id VARCHAR(36) NOT NULL, 
	material_id VARCHAR(36) NOT NULL, 
	location_id VARCHAR(64) NOT NULL, 
	opening_stock INTEGER NOT NULL, 
	incoming_confirmed INTEGER NOT NULL, 
	outgoing_confirmed INTEGER NOT NULL, 
	defective_stock INTEGER NOT NULL, 
	adjusted_stock INTEGER NOT NULL, 
	current_stock INTEGER NOT NULL, 
	last_reconciled_at TIMESTAMP WITH TIME ZONE, 
	last_transaction_id VARCHAR(36), 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (balance_id), 
	FOREIGN KEY(material_id) REFERENCES material (material_id) ON DELETE CASCADE
);

CREATE INDEX ix_material_inventory_balance_material_id ON material_inventory_balance (material_id);

CREATE UNIQUE INDEX idx_balance_mat_loc ON material_inventory_balance (material_id, location_id);

CREATE INDEX ix_material_inventory_balance_location_id ON material_inventory_balance (location_id);

CREATE TABLE package_definition (
	definition_id VARCHAR(36) NOT NULL, 
	material_id VARCHAR(36) NOT NULL, 
	units_per_package INTEGER NOT NULL, 
	package_barcode VARCHAR(64), 
	rfid_prefix VARCHAR(64), 
	gross_weight_kg NUMERIC(10, 3), 
	net_weight_kg NUMERIC(10, 3), 
	tolerance_range_pct NUMERIC(5, 2) NOT NULL, 
	effective_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	effective_end TIMESTAMP WITH TIME ZONE, 
	evidence_source VARCHAR(64) NOT NULL, 
	approval_status VARCHAR(32) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (definition_id), 
	CONSTRAINT chk_pkg_def_units_pos CHECK (units_per_package > 0), 
	CONSTRAINT chk_pkg_def_status CHECK (approval_status IN ('PENDING', 'APPROVED', 'SUPERSEDED')), 
	FOREIGN KEY(material_id) REFERENCES material (material_id) ON DELETE CASCADE
);

CREATE INDEX ix_package_definition_material_id ON package_definition (material_id);

CREATE TABLE threshold_config (
	config_id VARCHAR(36) NOT NULL, 
	store_id VARCHAR(36), 
	unit_tolerance INTEGER NOT NULL, 
	pct_tolerance NUMERIC(5, 2) NOT NULL, 
	low_severity_threshold INTEGER NOT NULL, 
	med_severity_threshold INTEGER NOT NULL, 
	high_severity_threshold INTEGER NOT NULL, 
	repeat_offender_window_days INTEGER NOT NULL, 
	repeat_offender_count_trigger INTEGER NOT NULL, 
	camera_offline_alert_after_sec INTEGER NOT NULL, 
	turnstile_auto_lock_on_high BOOLEAN NOT NULL, 
	audio_alarm_enabled BOOLEAN NOT NULL, 
	updated_by VARCHAR(36), 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (config_id), 
	FOREIGN KEY(store_id) REFERENCES store (store_id)
);

CREATE TABLE access_control_event (
	access_id VARCHAR(36) NOT NULL, 
	door_id VARCHAR(64) NOT NULL, 
	employee_id VARCHAR(36), 
	credential_type VARCHAR(32) NOT NULL, 
	access_status VARCHAR(32) NOT NULL, 
	denial_reason VARCHAR(128), 
	event_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (access_id), 
	FOREIGN KEY(employee_id) REFERENCES employee (employee_id)
);

CREATE INDEX ix_access_control_event_event_time ON access_control_event (event_time);

CREATE INDEX ix_access_control_event_door_id ON access_control_event (door_id);

CREATE TABLE camera (
	camera_id VARCHAR(36) NOT NULL, 
	label VARCHAR(255) NOT NULL, 
	lane_id VARCHAR(36), 
	ip_address VARCHAR(64) NOT NULL, 
	rtsp_path VARCHAR(255) NOT NULL, 
	sub_stream_path VARCHAR(255), 
	credentials_ref VARCHAR(128), 
	stream_url TEXT, 
	pairing_method VARCHAR(32) NOT NULL, 
	resolution VARCHAR(32), 
	fps INTEGER, 
	pipeline_mode VARCHAR(64) NOT NULL, 
	camera_role VARCHAR(32) NOT NULL, 
	roi_polygon JSON, 
	ignored_classes JSON, 
	status VARCHAR(32) NOT NULL, 
	degraded_reason VARCHAR(255), 
	last_frame_at TIMESTAMP WITH TIME ZONE, 
	last_inference_at TIMESTAMP WITH TIME ZONE, 
	inference_latency_ms NUMERIC(8, 2), 
	last_heartbeat_at TIMESTAMP WITH TIME ZONE, 
	offline_since TIMESTAMP WITH TIME ZONE, 
	added_by VARCHAR(36), 
	added_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	removed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (camera_id), 
	CONSTRAINT chk_camera_status CHECK (status IN ('ONLINE', 'OFFLINE', 'DEGRADED', 'PENDING_SETUP')), 
	CONSTRAINT chk_camera_pairing_method CHECK (pairing_method IN ('MANUAL', 'QR_CAMERA_DISPLAYED', 'QR_APP_GENERATED')), 
	CONSTRAINT chk_camera_pipeline_mode CHECK (pipeline_mode IN ('STANDARD_DETECTION', 'MATERIAL_SEGMENTATION', 'PERIMETER_TRIPWIRE_GATE')), 
	CONSTRAINT chk_camera_role CHECK (camera_role IN ('ENTRY_EXIT', 'STOCK_AREA', 'SHELF', 'WAREHOUSE', 'DISPATCH', 'GENERAL_MONITORING')), 
	FOREIGN KEY(lane_id) REFERENCES lane (lane_id), 
	FOREIGN KEY(added_by) REFERENCES app_user (user_id)
);

CREATE INDEX idx_camera_lane ON camera (lane_id);

CREATE TABLE dispatch_session (
	session_id VARCHAR(36) NOT NULL, 
	dock_lane_id VARCHAR(36) NOT NULL, 
	manifest_id VARCHAR(128), 
	carrier_employee_id VARCHAR(36), 
	vehicle_identifier VARCHAR(64), 
	status VARCHAR(32) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	before_count JSON NOT NULL, 
	after_count JSON NOT NULL, 
	removed_delta JSON NOT NULL, 
	manifest_expected JSON NOT NULL, 
	discrepancy_type VARCHAR(32) NOT NULL, 
	discrepancy_magnitude INTEGER NOT NULL, 
	tracking_interrupted_seconds NUMERIC(8, 2) NOT NULL, 
	archival_snapshot_url TEXT, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (session_id), 
	CONSTRAINT chk_dispatch_status CHECK (status IN ('ACTIVE', 'COMPLETED', 'FLAGGED_DISCREPANCY', 'ABORTED')), 
	CONSTRAINT chk_dispatch_discrepancy CHECK (discrepancy_type IN ('MATCH', 'OVER_AUTHORIZED', 'UNDER_COUNT', 'UNMANIFESTED_SKU')), 
	FOREIGN KEY(dock_lane_id) REFERENCES lane (lane_id), 
	FOREIGN KEY(carrier_employee_id) REFERENCES employee (employee_id)
);

CREATE INDEX ix_dispatch_session_manifest_id ON dispatch_session (manifest_id);

CREATE INDEX idx_dispatch_dock_lane ON dispatch_session (dock_lane_id);

CREATE INDEX idx_dispatch_status ON dispatch_session (status);

CREATE TABLE exit_event (
	event_id VARCHAR(36) NOT NULL, 
	ts TIMESTAMP WITH TIME ZONE NOT NULL, 
	lane_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36), 
	employee_match_confidence NUMERIC(5, 4), 
	cases_detected INTEGER NOT NULL, 
	units_detected INTEGER NOT NULL, 
	vision_count INTEGER NOT NULL, 
	vision_confidence NUMERIC(5, 4) NOT NULL, 
	rfid_count INTEGER, 
	weight_kg NUMERIC(10, 3), 
	weight_estimated_units INTEGER, 
	consensus_units INTEGER NOT NULL, 
	consensus_method VARCHAR(64) NOT NULL, 
	invoice_id VARCHAR(36), 
	declared_units INTEGER, 
	delta_units INTEGER NOT NULL, 
	verdict VARCHAR(32) NOT NULL, 
	severity VARCHAR(32) NOT NULL, 
	snapshot_url TEXT, 
	clip_url TEXT, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (event_id), 
	CONSTRAINT chk_exit_event_verdict CHECK (verdict IN ('PASS', 'MATCH', 'MISMATCH', 'PARTIAL', 'UNVERIFIED', 'REVIEW_REQUIRED')), 
	CONSTRAINT chk_exit_event_severity CHECK (severity IN ('NONE', 'LOW', 'MEDIUM', 'HIGH')), 
	FOREIGN KEY(lane_id) REFERENCES lane (lane_id), 
	FOREIGN KEY(employee_id) REFERENCES employee (employee_id), 
	FOREIGN KEY(invoice_id) REFERENCES invoice (invoice_id)
);

CREATE INDEX idx_exit_event_lane_ts ON exit_event (lane_id, ts);

CREATE INDEX ix_exit_event_ts ON exit_event (ts);

CREATE INDEX ix_exit_event_lane_id ON exit_event (lane_id);

CREATE INDEX ix_exit_event_severity ON exit_event (severity);

CREATE TABLE alert (
	alert_id VARCHAR(36) NOT NULL, 
	event_id VARCHAR(36), 
	camera_id VARCHAR(36), 
	alert_type VARCHAR(64) NOT NULL, 
	severity VARCHAR(32) NOT NULL, 
	delta_units INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	resolved_by VARCHAR(128), 
	resolution_note TEXT, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (alert_id), 
	CONSTRAINT chk_alert_type CHECK (alert_type IN ('SENSOR_DISAGREEMENT', 'OVER_CARRY', 'UNDER_DECLARE', 'UNAUTHORIZED_ACCESS', 'INTRUSION', 'CAMERA_OFFLINE', 'FIRE_HAZARD', 'SUSPICIOUS_BEHAVIOR', 'PPE_VIOLATION', 'MATERIAL_DEFECT')), 
	CONSTRAINT chk_alert_severity CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH')), 
	CONSTRAINT chk_alert_status CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')), 
	FOREIGN KEY(event_id) REFERENCES exit_event (event_id), 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id)
);

CREATE INDEX ix_alert_severity ON alert (severity);

CREATE INDEX ix_alert_created_at ON alert (created_at);

CREATE INDEX ix_alert_camera_id ON alert (camera_id);

CREATE INDEX ix_alert_event_id ON alert (event_id);

CREATE INDEX ix_alert_status ON alert (status);

CREATE TABLE camera_heartbeat (
	heartbeat_id SERIAL NOT NULL, 
	camera_id VARCHAR(36) NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	fps_observed NUMERIC(6, 2), 
	bitrate_kbps NUMERIC(10, 2), 
	dropped_frames INTEGER, 
	PRIMARY KEY (heartbeat_id), 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id) ON DELETE CASCADE
);

CREATE INDEX ix_camera_heartbeat_received_at ON camera_heartbeat (received_at);

CREATE INDEX ix_camera_heartbeat_camera_id ON camera_heartbeat (camera_id);

CREATE TABLE camera_pairing_token (
	token_id VARCHAR(36) NOT NULL, 
	token_value VARCHAR(128) NOT NULL, 
	store_id VARCHAR(36) NOT NULL, 
	lane_id VARCHAR(36), 
	created_by VARCHAR(36), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	used_at TIMESTAMP WITH TIME ZONE, 
	used_by_camera_id VARCHAR(36), 
	qr_payload TEXT, 
	PRIMARY KEY (token_id), 
	FOREIGN KEY(store_id) REFERENCES store (store_id), 
	FOREIGN KEY(lane_id) REFERENCES lane (lane_id), 
	FOREIGN KEY(created_by) REFERENCES app_user (user_id), 
	FOREIGN KEY(used_by_camera_id) REFERENCES camera (camera_id)
);

CREATE UNIQUE INDEX ix_camera_pairing_token_token_value ON camera_pairing_token (token_value);

CREATE TABLE evidence_artifact (
	artifact_id VARCHAR(36) NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	camera_id VARCHAR(36), 
	artifact_type VARCHAR(32) NOT NULL, 
	s3_key VARCHAR(512) NOT NULL, 
	cryptographic_hash VARCHAR(128) NOT NULL, 
	captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	retention_expires_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (artifact_id), 
	FOREIGN KEY(event_id) REFERENCES exit_event (event_id) ON DELETE CASCADE, 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id)
);

CREATE INDEX ix_evidence_artifact_event_id ON evidence_artifact (event_id);

CREATE TABLE exit_event_line_item (
	line_item_id VARCHAR(36) NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	cases_qty INTEGER NOT NULL, 
	units_qty INTEGER NOT NULL, 
	PRIMARY KEY (line_item_id), 
	FOREIGN KEY(event_id) REFERENCES exit_event (event_id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES product (product_id)
);

CREATE TABLE face_match_attempt (
	attempt_id VARCHAR(36) NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	matched_employee_id VARCHAR(36), 
	similarity NUMERIC(5, 4) NOT NULL, 
	model_version VARCHAR(64) NOT NULL, 
	decision VARCHAR(32) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (attempt_id), 
	CONSTRAINT chk_face_decision CHECK (decision IN ('MATCHED', 'NO_MATCH', 'LOW_CONFIDENCE', 'DISABLED', 'BYPASS')), 
	FOREIGN KEY(event_id) REFERENCES exit_event (event_id) ON DELETE CASCADE, 
	FOREIGN KEY(matched_employee_id) REFERENCES employee (employee_id)
);

CREATE TABLE initial_stock_verification (
	verification_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	sku_code VARCHAR(64) NOT NULL, 
	product_name VARCHAR(255) NOT NULL, 
	camera_id VARCHAR(36), 
	ai_proposed_count INTEGER NOT NULL, 
	verified_count INTEGER, 
	difference INTEGER, 
	status VARCHAR(32) NOT NULL, 
	verified_by VARCHAR(128), 
	correction_reason VARCHAR(255), 
	snapshot_url TEXT, 
	model_version VARCHAR(64), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (verification_id), 
	CONSTRAINT chk_stock_verif_status CHECK (status IN ('PENDING_VERIFICATION', 'VERIFIED_ACCURATE', 'CORRECTED', 'REJECTED')), 
	FOREIGN KEY(product_id) REFERENCES product (product_id) ON DELETE CASCADE, 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id)
);

CREATE INDEX idx_stock_verif_prod_status ON initial_stock_verification (product_id, status);

CREATE INDEX ix_initial_stock_verification_product_id ON initial_stock_verification (product_id);

CREATE INDEX ix_initial_stock_verification_camera_id ON initial_stock_verification (camera_id);

CREATE INDEX ix_initial_stock_verification_sku_code ON initial_stock_verification (sku_code);

CREATE TABLE pending_product_identification (
	id VARCHAR(36) NOT NULL, 
	camera_id VARCHAR(36), 
	vision_class_id INTEGER NOT NULL, 
	detected_label VARCHAR(128) NOT NULL, 
	confidence NUMERIC(5, 4) NOT NULL, 
	snapshot_url TEXT, 
	status VARCHAR(32) NOT NULL, 
	mapped_sku VARCHAR(64), 
	mapped_product_id VARCHAR(36), 
	reviewed_by VARCHAR(128), 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT chk_pending_prod_id_status CHECK (status IN ('PENDING_MAPPING', 'MAPPED_TO_SKU', 'CREATED_NEW_PRODUCT', 'IGNORED')), 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id), 
	FOREIGN KEY(mapped_product_id) REFERENCES product (product_id) ON DELETE SET NULL
);

CREATE INDEX ix_pending_product_identification_vision_class_id ON pending_product_identification (vision_class_id);

CREATE INDEX idx_pending_prod_status ON pending_product_identification (status);

CREATE INDEX ix_pending_product_identification_camera_id ON pending_product_identification (camera_id);

CREATE INDEX ix_pending_product_identification_created_at ON pending_product_identification (created_at);

CREATE TABLE rfid_read (
	read_id VARCHAR(36) NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	epc_tag VARCHAR(128) NOT NULL, 
	antenna_id VARCHAR(64) NOT NULL, 
	rssi NUMERIC(6, 2), 
	read_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (read_id), 
	FOREIGN KEY(event_id) REFERENCES exit_event (event_id) ON DELETE CASCADE
);

CREATE TABLE static_image_detection (
	detection_id VARCHAR(36) NOT NULL, 
	camera_id VARCHAR(36) NOT NULL, 
	frame_ts TIMESTAMP WITH TIME ZONE NOT NULL, 
	bbox JSON NOT NULL, 
	liveness_score NUMERIC(5, 4) NOT NULL, 
	classification VARCHAR(64) NOT NULL, 
	classification_confidence NUMERIC(5, 4) NOT NULL, 
	model_version VARCHAR(64) NOT NULL, 
	suppressed_alert BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (detection_id), 
	CONSTRAINT chk_static_classification CHECK (classification IN ('RELIGIOUS_IMAGE','PERSON_PHOTO','POSTER_OR_SIGNAGE','SCREEN_DISPLAY','UNCLASSIFIED_STATIC')), 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id) ON DELETE CASCADE
);

CREATE INDEX idx_static_cam_time ON static_image_detection (camera_id, frame_ts);

CREATE TABLE vehicle_detection (
	detection_id VARCHAR(36) NOT NULL, 
	camera_id VARCHAR(36) NOT NULL, 
	license_plate VARCHAR(32), 
	plate_confidence NUMERIC(5, 4), 
	vehicle_class VARCHAR(32) NOT NULL, 
	color VARCHAR(32), 
	direction VARCHAR(32), 
	watchlist_hit BOOLEAN NOT NULL, 
	event_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (detection_id), 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id)
);

CREATE INDEX ix_vehicle_detection_camera_id ON vehicle_detection (camera_id);

CREATE INDEX ix_vehicle_detection_event_time ON vehicle_detection (event_time);

CREATE INDEX ix_vehicle_detection_license_plate ON vehicle_detection (license_plate);

CREATE TABLE virtual_tripwire_config (
	tripwire_id VARCHAR(36) NOT NULL, 
	camera_id VARCHAR(36) NOT NULL, 
	label VARCHAR(128) NOT NULL, 
	line_coords JSON NOT NULL, 
	direction_mode VARCHAR(32) NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (tripwire_id), 
	CONSTRAINT chk_tripwire_direction_mode CHECK (direction_mode IN ('BIDIRECTIONAL', 'ENTRY_ONLY', 'EXIT_ONLY', 'ENTRY', 'EXIT', 'BOTH')), 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id)
);

CREATE INDEX idx_tripwire_camera ON virtual_tripwire_config (camera_id);

CREATE TABLE vision_detection (
	detection_id VARCHAR(36) NOT NULL, 
	event_id VARCHAR(36), 
	camera_id VARCHAR(36), 
	frame_ts TIMESTAMP WITH TIME ZONE NOT NULL, 
	model_version VARCHAR(64) NOT NULL, 
	bbox JSON NOT NULL, 
	class_label VARCHAR(64) NOT NULL, 
	product_id VARCHAR(36), 
	confidence NUMERIC(5, 4) NOT NULL, 
	track_id VARCHAR(64), 
	category VARCHAR(32) NOT NULL, 
	snapshot_url TEXT, 
	direction VARCHAR(32), 
	PRIMARY KEY (detection_id), 
	FOREIGN KEY(event_id) REFERENCES exit_event (event_id) ON DELETE SET NULL, 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id), 
	FOREIGN KEY(product_id) REFERENCES product (product_id)
);

CREATE TABLE weight_reading (
	reading_id VARCHAR(36) NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	sensor_id VARCHAR(64) NOT NULL, 
	weight_kg NUMERIC(10, 3) NOT NULL, 
	read_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (reading_id), 
	FOREIGN KEY(event_id) REFERENCES exit_event (event_id) ON DELETE CASCADE
);

CREATE TABLE alarm_dispatch (
	dispatch_id VARCHAR(36) NOT NULL, 
	alert_id VARCHAR(36) NOT NULL, 
	channel VARCHAR(32) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	attempted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	error_detail TEXT, 
	PRIMARY KEY (dispatch_id), 
	CONSTRAINT chk_dispatch_channel CHECK (channel IN ('SIREN', 'STROBE', 'TTS', 'TURNSTILE_LOCK', 'PUSH', 'SMS')), 
	CONSTRAINT chk_dispatch_status CHECK (status IN ('QUEUED', 'SENT', 'ACKED', 'FAILED')), 
	FOREIGN KEY(alert_id) REFERENCES alert (alert_id)
);

CREATE TABLE material_movement_ledger (
	ledger_id VARCHAR(36) NOT NULL, 
	transaction_type VARCHAR(32) NOT NULL, 
	material_id VARCHAR(36) NOT NULL, 
	camera_id VARCHAR(36), 
	zone_id VARCHAR(64), 
	tripwire_id VARCHAR(36), 
	track_id VARCHAR(64), 
	direction VARCHAR(16) NOT NULL, 
	person_id VARCHAR(36), 
	person_name VARCHAR(255) NOT NULL, 
	person_identity_status VARCHAR(32) NOT NULL, 
	carrier_relation VARCHAR(32) NOT NULL, 
	packaging_type VARCHAR(64) NOT NULL, 
	package_quantity INTEGER NOT NULL, 
	units_per_package INTEGER NOT NULL, 
	unit_quantity INTEGER NOT NULL, 
	defect_status VARCHAR(32) NOT NULL, 
	defect_severity VARCHAR(32) NOT NULL, 
	confidence NUMERIC(5, 4) NOT NULL, 
	discrepancy_units INTEGER NOT NULL, 
	discrepancy_reason VARCHAR(255), 
	source_frame_path TEXT, 
	timestamp TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (ledger_id), 
	CONSTRAINT chk_ledger_tx_type CHECK (transaction_type IN ('IN', 'OUT', 'ADJUSTMENT', 'TRANSFER_IN', 'TRANSFER_OUT', 'RETURN')), 
	CONSTRAINT chk_ledger_direction CHECK (direction IN ('ENTRY', 'EXIT', 'TRAVERSAL', 'UNKNOWN', 'IN', 'OUT')), 
	CONSTRAINT chk_ledger_person_status CHECK (person_identity_status IN ('VERIFIED_KNOWN', 'UNKNOWN_PERSON', 'UNAVAILABLE')), 
	CONSTRAINT chk_ledger_defect_status CHECK (defect_status IN ('NORMAL', 'DAMAGED', 'DEFECTIVE', 'UNKNOWN_CONDITION')), 
	FOREIGN KEY(material_id) REFERENCES material (material_id) ON DELETE CASCADE, 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id), 
	FOREIGN KEY(tripwire_id) REFERENCES virtual_tripwire_config (tripwire_id), 
	FOREIGN KEY(person_id) REFERENCES employee (employee_id)
);

CREATE INDEX ix_material_movement_ledger_camera_id ON material_movement_ledger (camera_id);

CREATE INDEX idx_ledger_cam_ts ON material_movement_ledger (camera_id, timestamp);

CREATE INDEX ix_material_movement_ledger_material_id ON material_movement_ledger (material_id);

CREATE INDEX ix_material_movement_ledger_timestamp ON material_movement_ledger (timestamp);

CREATE INDEX idx_ledger_mat_ts ON material_movement_ledger (material_id, timestamp);

CREATE INDEX ix_material_movement_ledger_track_id ON material_movement_ledger (track_id);

CREATE INDEX ix_material_movement_ledger_person_id ON material_movement_ledger (person_id);

CREATE TABLE person_appearance_summary (
	summary_id VARCHAR(36) NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	face_match_attempt_id VARCHAR(36), 
	clothing_top_color VARCHAR(64) NOT NULL, 
	clothing_bottom_color VARCHAR(64) NOT NULL, 
	build_category VARCHAR(32) NOT NULL, 
	build_confidence NUMERIC(5, 4) NOT NULL, 
	accessories JSON NOT NULL, 
	accessories_confidence JSON NOT NULL, 
	model_version VARCHAR(64) NOT NULL, 
	reid_embedding JSON, 
	reid_cluster_id VARCHAR(36), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (summary_id), 
	CONSTRAINT chk_appearance_build_category CHECK (build_category IN ('SHORTER','AVERAGE','TALLER','UNKNOWN')), 
	FOREIGN KEY(event_id) REFERENCES exit_event (event_id) ON DELETE CASCADE, 
	FOREIGN KEY(face_match_attempt_id) REFERENCES face_match_attempt (attempt_id)
);

CREATE INDEX ix_person_appearance_summary_reid_cluster_id ON person_appearance_summary (reid_cluster_id);

CREATE INDEX ix_person_appearance_summary_created_at ON person_appearance_summary (created_at);

CREATE INDEX ix_person_appearance_summary_event_id ON person_appearance_summary (event_id);

CREATE INDEX idx_appearance_cluster_created ON person_appearance_summary (reid_cluster_id, created_at);

CREATE TABLE tripwire_crossing_event (
	crossing_id VARCHAR(36) NOT NULL, 
	tripwire_id VARCHAR(36) NOT NULL, 
	camera_id VARCHAR(36) NOT NULL, 
	track_id VARCHAR(64) NOT NULL, 
	timestamp TIMESTAMP WITH TIME ZONE NOT NULL, 
	direction VARCHAR(16) NOT NULL, 
	entity_type VARCHAR(32) NOT NULL, 
	biometric_status VARCHAR(32) NOT NULL, 
	matched_employee_id VARCHAR(36), 
	is_tailgating BOOLEAN NOT NULL, 
	tailgating_details JSON, 
	snapshot_url TEXT, 
	PRIMARY KEY (crossing_id), 
	CONSTRAINT chk_crossing_direction CHECK (direction IN ('ENTRY', 'EXIT', 'UNKNOWN')), 
	CONSTRAINT chk_crossing_biometric CHECK (biometric_status IN ('VERIFIED_KNOWN', 'UNKNOWN_INTRUDER', 'UNAVAILABLE')), 
	FOREIGN KEY(tripwire_id) REFERENCES virtual_tripwire_config (tripwire_id), 
	FOREIGN KEY(matched_employee_id) REFERENCES employee (employee_id)
);

CREATE INDEX idx_crossing_tripwire ON tripwire_crossing_event (tripwire_id);

CREATE INDEX idx_crossing_timestamp ON tripwire_crossing_event (timestamp);

CREATE INDEX ix_tripwire_crossing_event_timestamp ON tripwire_crossing_event (timestamp);

CREATE TABLE material_defect_event (
	defect_event_id VARCHAR(36) NOT NULL, 
	ledger_id VARCHAR(36), 
	material_id VARCHAR(36) NOT NULL, 
	camera_id VARCHAR(36), 
	defect_class VARCHAR(64) NOT NULL, 
	severity VARCHAR(32) NOT NULL, 
	confidence NUMERIC(5, 4) NOT NULL, 
	affected_units INTEGER NOT NULL, 
	snapshot_url TEXT, 
	status VARCHAR(32) NOT NULL, 
	details JSON, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (defect_event_id), 
	CONSTRAINT chk_defect_evt_severity CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')), 
	CONSTRAINT chk_defect_evt_status CHECK (status IN ('QUARANTINED', 'ACCEPTED_WITH_CONCESSION', 'REJECTED', 'SCRAPPED')), 
	FOREIGN KEY(ledger_id) REFERENCES material_movement_ledger (ledger_id) ON DELETE SET NULL, 
	FOREIGN KEY(material_id) REFERENCES material (material_id) ON DELETE CASCADE, 
	FOREIGN KEY(camera_id) REFERENCES camera (camera_id)
);

CREATE INDEX ix_material_defect_event_material_id ON material_defect_event (material_id);

CREATE INDEX ix_material_defect_event_created_at ON material_defect_event (created_at);


-- -----------------------------------------------------------------------------
-- 3. BASELINE SEED DATA (SOFTWARE OWNER ONLY)
-- -----------------------------------------------------------------------------

-- 3a. Platform Control-Plane Master Super Admin (Software Owner)
INSERT INTO platform_super_admin (admin_id, username, email, password_hash, role, is_active, created_at)
VALUES (
    'admin_software_owner_ces',
    'ces',
    'ces@gmail.com',
    '$2b$12$9VWIY5JVDGrSEQRWb7c7JOgaiyRoK.HSNwEPp/oMoej2TXSRa6Nr6',
    'SUPER_ADMIN',
    true,
    NOW()
) ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role = 'SUPER_ADMIN',
    is_active = true;

-- 3b. Platform Default Tenant Registry
INSERT INTO platform_tenant (tenant_id, name, slug, db_identifier, status, timezone, currency, contact_email, created_at, updated_at)
VALUES (
    'tenant_ces_flagship',
    'CES Flagship Retail & Warehouse',
    'ces-retail',
    'secops_tenant_ces_retail',
    'ACTIVE',
    'Asia/Kolkata',
    'INR',
    'ces@gmail.com',
    NOW(),
    NOW()
) ON CONFLICT (slug) DO UPDATE SET
    status = 'ACTIVE',
    contact_email = EXCLUDED.contact_email;

-- 3c. Store Operational Entity
INSERT INTO store (store_id, name, address, timezone)
VALUES (
    'STORE-01',
    'Flagship Retail & Warehouse Exit Station',
    'Central Facility, Bay 1-4',
    'Asia/Kolkata'
) ON CONFLICT (store_id) DO NOTHING;

-- 3d. Operational Software Owner User (AppUser)
INSERT INTO app_user (user_id, store_id, email, username, password_hash, role, mfa_enabled, is_active, created_at)
VALUES (
    'user_software_owner_ces',
    'STORE-01',
    'ces@gmail.com',
    'ces',
    '$2b$12$9VWIY5JVDGrSEQRWb7c7JOgaiyRoK.HSNwEPp/oMoej2TXSRa6Nr6',
    'ADMIN',
    false,
    true,
    NOW()
) ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role = 'ADMIN',
    is_active = true;

-- 3e. Standard Exit Lanes
INSERT INTO lane (lane_id, store_id, label, status)
VALUES
    ('LANE-01', 'STORE-01', 'Main Exit Portal 1', 'ONLINE'),
    ('LANE-02', 'STORE-01', 'Express Exit Portal 2', 'ONLINE')
ON CONFLICT (lane_id) DO NOTHING;

-- 3f. Standard Threshold Configuration
INSERT INTO threshold_config (
    config_id, store_id, unit_tolerance, pct_tolerance,
    low_severity_threshold, med_severity_threshold, high_severity_threshold,
    repeat_offender_window_days, repeat_offender_count_trigger,
    camera_offline_alert_after_sec, turnstile_auto_lock_on_high, audio_alarm_enabled
) VALUES (
    'TCFG-DEFAULT', 'STORE-01', 0, 0.0,
    1, 3, 6,
    30, 3,
    60, true, true
) ON CONFLICT (config_id) DO NOTHING;
