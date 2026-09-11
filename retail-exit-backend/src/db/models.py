"""Database ORM Models Module

Implements the complete relational schema defined in Section 5 & Part C of the SEC-OPS Master Specification.
Designed for PostgreSQL production deployment while supporting SQLite for rapid local testing.
"""

from datetime import datetime, timezone
from typing import Optional, List, Any
import uuid
import json

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
    Index,
    JSON,
    TypeDecorator,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JSONType(TypeDecorator):
    """Platform-independent JSON type."""
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return value
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. Reference / Master Data Models
# ─────────────────────────────────────────────────────────────────────────────

class Store(Base):
    __tablename__ = "store"

    store_id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    timezone = Column(String(64), nullable=False, default="UTC")

    lanes = relationship("Lane", back_populates="store", cascade="all, delete-orphan")
    users = relationship("AppUser", back_populates="store")
    threshold_configs = relationship("ThresholdConfig", back_populates="store")


class Shift(Base):
    __tablename__ = "shift"

    shift_id = Column(String(36), primary_key=True, default=generate_uuid)
    label = Column(String(128), nullable=False)
    starts_at = Column(String(8), nullable=False)  # HH:MM:SS
    ends_at = Column(String(8), nullable=False)    # HH:MM:SS

    employees = relationship("Employee", back_populates="shift")


class Product(Base):
    __tablename__ = "product"

    product_id = Column(String(36), primary_key=True, default=generate_uuid)
    sku_code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(128), nullable=False)
    pack_size = Column(Integer, nullable=False)  # units per sealed case
    unit_price = Column(Numeric(12, 2), nullable=False)
    case_price = Column(Numeric(12, 2), nullable=False)
    reorder_threshold = Column(Integer, nullable=False, default=0)
    rfid_epc_prefix = Column(String(64), nullable=True)
    avg_unit_weight_g = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        CheckConstraint("pack_size > 0", name="chk_product_pack_size_pos"),
    )

    line_items = relationship("ExitEventLineItem", back_populates="product")
    vision_detections = relationship("VisionDetection", back_populates="product")


class Employee(Base):
    __tablename__ = "employee"

    employee_id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    role = Column(String(128), nullable=False)
    rfid_badge_id = Column(String(128), unique=True, nullable=False, index=True)
    shift_id = Column(String(36), ForeignKey("shift.shift_id"), nullable=True)
    active_flag = Column(Boolean, nullable=False, default=True)
    face_embedding = Column(JSONType, nullable=True)  # 512-d ArcFace vector or JSON array
    embedding_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    shift = relationship("Shift", back_populates="employees")
    exit_events = relationship("ExitEvent", back_populates="employee")
    face_matches = relationship("FaceMatchAttempt", back_populates="employee")


class Lane(Base):
    __tablename__ = "lane"

    lane_id = Column(String(36), primary_key=True, default=generate_uuid)
    label = Column(String(128), nullable=False)
    store_id = Column(String(36), ForeignKey("store.store_id"), nullable=False)
    camera_ids = Column(JSONType, nullable=False, default=list)  # list of camera IDs/IPs
    rfid_antenna_id = Column(String(128), nullable=True)
    weight_sensor_id = Column(String(128), nullable=True)
    turnstile_ctrl_id = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="ONLINE")
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('ONLINE', 'OFFLINE', 'DEGRADED')", name="chk_lane_status"),
    )

    store = relationship("Store", back_populates="lanes")
    exit_events = relationship("ExitEvent", back_populates="lane")
    cameras = relationship("Camera", back_populates="lane")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Camera Fleet Management Models (Part C)
# ─────────────────────────────────────────────────────────────────────────────

class Camera(Base):
    __tablename__ = "camera"

    camera_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    label: Any = Column(String(255), nullable=False)  # e.g. "Exit Lane 3 — North"
    lane_id: Any = Column(String(36), ForeignKey("lane.lane_id"), nullable=True)
    ip_address: Any = Column(String(64), nullable=False)
    rtsp_path: Any = Column(String(255), nullable=False)
    sub_stream_path: Any = Column(String(255), nullable=True)
    credentials_ref: Any = Column(String(128), nullable=True)  # pointer into secrets manager
    stream_url: Any = Column(Text, nullable=True)  # media-server WebRTC/HLS URL
    pairing_method: Any = Column(String(32), nullable=False, default="MANUAL")
    resolution: Any = Column(String(32), nullable=True, default="1920x1080")
    fps: Any = Column(Integer, nullable=True, default=30)
    status: Any = Column(String(32), nullable=False, default="PENDING_SETUP")
    last_heartbeat_at: Any = Column(DateTime(timezone=True), nullable=True)
    offline_since: Any = Column(DateTime(timezone=True), nullable=True)
    added_by: Any = Column(String(36), ForeignKey("app_user.user_id"), nullable=True)
    added_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    removed_at: Any = Column(DateTime(timezone=True), nullable=True)  # Soft delete

    __table_args__ = (
        CheckConstraint("status IN ('ONLINE', 'OFFLINE', 'DEGRADED', 'PENDING_SETUP')", name="chk_camera_status"),
        CheckConstraint("pairing_method IN ('MANUAL', 'QR_CAMERA_DISPLAYED', 'QR_APP_GENERATED')", name="chk_camera_pairing_method"),
        Index("idx_camera_lane", "lane_id"),
        Index("idx_camera_status", "status"),
    )

    lane = relationship("Lane", back_populates="cameras")
    heartbeats = relationship("CameraHeartbeat", back_populates="camera", cascade="all, delete-orphan")
    vision_detections = relationship("VisionDetection", back_populates="camera")
    alerts = relationship("Alert", back_populates="camera")


class CameraPairingToken(Base):
    __tablename__ = "camera_pairing_token"

    token_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    token_value: Any = Column(String(128), unique=True, nullable=False, index=True)
    store_id: Any = Column(String(36), ForeignKey("store.store_id"), nullable=False)
    lane_id: Any = Column(String(36), ForeignKey("lane.lane_id"), nullable=True)
    created_by: Any = Column(String(36), ForeignKey("app_user.user_id"), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    expires_at: Any = Column(DateTime(timezone=True), nullable=False)
    used_at: Any = Column(DateTime(timezone=True), nullable=True)
    used_by_camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=True)
    qr_payload: Any = Column(Text, nullable=True)

    store = relationship("Store")
    lane = relationship("Lane")
    camera = relationship("Camera", foreign_keys=[used_by_camera_id])


class CameraHeartbeat(Base):
    __tablename__ = "camera_heartbeat"

    heartbeat_id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(36), ForeignKey("camera.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)
    fps_observed = Column(Numeric(6, 2), nullable=True)
    bitrate_kbps = Column(Numeric(10, 2), nullable=True)
    dropped_frames = Column(Integer, nullable=True, default=0)

    camera = relationship("Camera", back_populates="heartbeats")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Core Event & Forensic Evidence Models
# ─────────────────────────────────────────────────────────────────────────────

class ExitEvent(Base):
    __tablename__ = "exit_event"

    event_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    ts: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)
    lane_id: Any = Column(String(36), ForeignKey("lane.lane_id"), nullable=False, index=True)
    employee_id: Any = Column(String(36), ForeignKey("employee.employee_id"), nullable=True)
    employee_match_confidence: Any = Column(Numeric(5, 4), nullable=True)
    cases_detected: Any = Column(Integer, nullable=False, default=0)
    units_detected: Any = Column(Integer, nullable=False, default=0)  # vision-derived
    vision_count: Any = Column(Integer, nullable=False, default=0)
    vision_confidence: Any = Column(Numeric(5, 4), nullable=False, default=0.0)
    rfid_count: Any = Column(Integer, nullable=True)
    weight_kg: Any = Column(Numeric(10, 3), nullable=True)
    weight_estimated_units: Any = Column(Integer, nullable=True)
    consensus_units: Any = Column(Integer, nullable=False, default=0)
    consensus_method: Any = Column(String(64), nullable=False, default="weighted_vote_v2")
    invoice_id: Any = Column(String(36), ForeignKey("invoice.invoice_id"), nullable=True)
    declared_units: Any = Column(Integer, nullable=True)
    delta_units: Any = Column(Integer, nullable=False, default=0)
    verdict: Any = Column(String(32), nullable=False, default="PASS")
    severity: Any = Column(String(32), nullable=False, default="NONE", index=True)
    snapshot_url: Any = Column(Text, nullable=True)
    clip_url: Any = Column(Text, nullable=True)
    notes: Any = Column(Text, nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("verdict IN ('PASS', 'MISMATCH')", name="chk_exit_event_verdict"),
        CheckConstraint("severity IN ('NONE', 'LOW', 'MEDIUM', 'HIGH')", name="chk_exit_event_severity"),
        Index("idx_exit_event_lane_ts", "lane_id", "ts"),
    )

    lane = relationship("Lane", back_populates="exit_events")
    employee = relationship("Employee", back_populates="exit_events")
    invoice = relationship("Invoice", foreign_keys=[invoice_id], back_populates="linked_events")
    line_items = relationship("ExitEventLineItem", back_populates="event", cascade="all, delete-orphan")
    vision_detections = relationship("VisionDetection", back_populates="event", cascade="all, delete-orphan")
    rfid_reads = relationship("RfidRead", back_populates="event", cascade="all, delete-orphan")
    weight_readings = relationship("WeightReading", back_populates="event", cascade="all, delete-orphan")
    face_matches = relationship("FaceMatchAttempt", back_populates="event", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="event")


class ExitEventLineItem(Base):
    __tablename__ = "exit_event_line_item"

    line_item_id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(String(36), ForeignKey("product.product_id"), nullable=False)
    cases_qty = Column(Integer, nullable=False, default=0)
    units_qty = Column(Integer, nullable=False, default=0)

    event = relationship("ExitEvent", back_populates="line_items")
    product = relationship("Product", back_populates="line_items")


class VisionDetection(Base):
    __tablename__ = "vision_detection"

    detection_id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    camera_id = Column(String(36), ForeignKey("camera.camera_id"), nullable=True)
    frame_ts = Column(DateTime(timezone=True), nullable=False)
    model_version = Column(String(64), nullable=False)
    bbox = Column(JSONType, nullable=False)  # [x, y, w, h] normalized or pixel
    class_label = Column(String(64), nullable=False)  # 'case_full', 'case_open', 'single_unit', 'person'
    product_id = Column(String(36), ForeignKey("product.product_id"), nullable=True)
    confidence = Column(Numeric(5, 4), nullable=False)

    event = relationship("ExitEvent", back_populates="vision_detections")
    camera = relationship("Camera", back_populates="vision_detections")
    product = relationship("Product", back_populates="vision_detections")


class RfidRead(Base):
    __tablename__ = "rfid_read"

    read_id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    epc_tag = Column(String(128), nullable=False)
    antenna_id = Column(String(64), nullable=False)
    rssi = Column(Numeric(6, 2), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=False)

    event = relationship("ExitEvent", back_populates="rfid_reads")


class WeightReading(Base):
    __tablename__ = "weight_reading"

    reading_id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    sensor_id = Column(String(64), nullable=False)
    weight_kg = Column(Numeric(10, 3), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=False)

    event = relationship("ExitEvent", back_populates="weight_readings")


class Invoice(Base):
    __tablename__ = "invoice"

    invoice_id = Column(String(36), primary_key=True, default=generate_uuid)
    invoice_number = Column(String(128), unique=True, nullable=False, index=True)
    carrier_name = Column(String(255), nullable=False)
    store_destination = Column(String(255), nullable=False)
    source = Column(String(32), nullable=False, default="SCAN")
    raw_file_url = Column(Text, nullable=False)
    ocr_model_version = Column(String(64), nullable=False)
    extraction_confidence = Column(Numeric(5, 4), nullable=False)
    extracted_json = Column(JSONType, nullable=False)  # line items array
    declared_total_units = Column(Integer, nullable=True)
    linked_event_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("source IN ('SCAN', 'EMAIL', 'API')", name="chk_invoice_source"),
    )

    linked_events = relationship("ExitEvent", foreign_keys=[ExitEvent.invoice_id], back_populates="invoice")


class FaceMatchAttempt(Base):
    __tablename__ = "face_match_attempt"

    attempt_id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    matched_employee_id = Column(String(36), ForeignKey("employee.employee_id"), nullable=True)
    similarity = Column(Numeric(5, 4), nullable=False)
    model_version = Column(String(64), nullable=False)
    decision = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("decision IN ('MATCHED', 'NO_MATCH', 'LOW_CONFIDENCE')", name="chk_face_decision"),
    )

    event = relationship("ExitEvent", back_populates="face_matches")
    employee = relationship("Employee", back_populates="face_matches")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Alerts, Alarms & Append-Only Audit Trail
# ─────────────────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alert"

    alert_id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("exit_event.event_id"), nullable=True, index=True)
    camera_id = Column(String(36), ForeignKey("camera.camera_id"), nullable=True, index=True)
    alert_type = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False, index=True)
    delta_units = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    resolved_by = Column(String(128), nullable=True)
    resolution_note = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('SENSOR_DISAGREEMENT', 'OVER_CARRY', 'UNDER_DECLARE', 'UNAUTHORIZED_ACCESS', 'INTRUSION', 'CAMERA_OFFLINE')",
            name="chk_alert_type",
        ),
        CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH')", name="chk_alert_severity"),
        CheckConstraint("status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')", name="chk_alert_status"),
    )

    event = relationship("ExitEvent", back_populates="alerts")
    camera = relationship("Camera", back_populates="alerts")
    dispatches = relationship("AlarmDispatch", back_populates="alert", cascade="all, delete-orphan")


class AlarmDispatch(Base):
    __tablename__ = "alarm_dispatch"

    dispatch_id = Column(String(36), primary_key=True, default=generate_uuid)
    alert_id = Column(String(36), ForeignKey("alert.alert_id"), nullable=False)
    channel = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="QUEUED")
    attempted_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    error_detail = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "channel IN ('SIREN', 'STROBE', 'TTS', 'TURNSTILE_LOCK', 'PUSH', 'SMS')",
            name="chk_dispatch_channel",
        ),
        CheckConstraint("status IN ('QUEUED', 'SENT', 'ACKED', 'FAILED')", name="chk_dispatch_status"),
    )

    alert = relationship("Alert", back_populates="dispatches")


class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    actor_id = Column(String(36), nullable=True)
    actor_type = Column(String(32), nullable=False)
    before_state = Column(JSONType, nullable=True)
    after_state = Column(JSONType, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)

    __table_args__ = (
        CheckConstraint("actor_type IN ('USER', 'SYSTEM', 'MODEL')", name="chk_audit_actor_type"),
    )


class AppUser(Base):
    __tablename__ = "app_user"

    user_id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False)
    store_id = Column(String(36), ForeignKey("store.store_id"), nullable=True)
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("role IN ('SUPERVISOR', 'ADMIN', 'VIEWER')", name="chk_app_user_role"),
    )

    store = relationship("Store", back_populates="users")


class ThresholdConfig(Base):
    __tablename__ = "threshold_config"

    config_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    store_id: Any = Column(String(36), ForeignKey("store.store_id"), nullable=True)
    unit_tolerance: Any = Column(Integer, nullable=False, default=0)
    pct_tolerance: Any = Column(Numeric(5, 2), nullable=False, default=0.0)
    low_severity_threshold: Any = Column(Integer, nullable=False, default=1)
    med_severity_threshold: Any = Column(Integer, nullable=False, default=3)
    high_severity_threshold: Any = Column(Integer, nullable=False, default=6)
    repeat_offender_window_days: Any = Column(Integer, nullable=False, default=30)
    repeat_offender_count_trigger: Any = Column(Integer, nullable=False, default=3)
    camera_offline_alert_after_sec: Any = Column(Integer, nullable=False, default=60)
    turnstile_auto_lock_on_high: Any = Column(Boolean, nullable=False, default=True)
    audio_alarm_enabled: Any = Column(Boolean, nullable=False, default=True)
    updated_by: Any = Column(String(36), nullable=True)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    store = relationship("Store", back_populates="threshold_configs")

