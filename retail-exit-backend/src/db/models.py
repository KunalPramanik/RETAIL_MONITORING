"""Database ORM Models Module

Implements the complete relational schema for SEC-OPS surveillance, exit verification, and industrial monitoring.
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

    store_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    name: Any = Column(String(255), nullable=False)
    address: Any = Column(Text, nullable=True)
    timezone: Any = Column(String(64), nullable=False, default="UTC")

    lanes = relationship("Lane", back_populates="store", cascade="all, delete-orphan")
    users = relationship("AppUser", back_populates="store")
    threshold_configs = relationship("ThresholdConfig", back_populates="store")


class Shift(Base):
    __tablename__ = "shift"

    shift_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    label: Any = Column(String(128), nullable=False)
    starts_at: Any = Column(String(8), nullable=False)  # HH:MM:SS
    ends_at: Any = Column(String(8), nullable=False)    # HH:MM:SS

    employees = relationship("Employee", back_populates="shift")


class Product(Base):
    __tablename__ = "product"

    product_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    sku_code: Any = Column(String(64), unique=True, nullable=False, index=True)
    name: Any = Column(String(255), nullable=False)
    category: Any = Column(String(128), nullable=False)
    pack_size: Any = Column(Integer, nullable=False)  # units per sealed case
    unit_price: Any = Column(Numeric(12, 2), nullable=False)
    case_price: Any = Column(Numeric(12, 2), nullable=False)
    reorder_threshold: Any = Column(Integer, nullable=False, default=0)
    rfid_epc_prefix: Any = Column(String(64), nullable=True)
    avg_unit_weight_g: Any = Column(Numeric(10, 2), nullable=True)
    vision_class_id: Any = Column(Integer, nullable=True, index=True) # Dynamically links YOLOX output to Product
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        CheckConstraint("pack_size > 0", name="chk_product_pack_size_pos"),
    )

    line_items = relationship("ExitEventLineItem", back_populates="product")
    vision_detections = relationship("VisionDetection", back_populates="product")


class Material(Base):
    """Dynamic Material Catalog entity.
    
    Supports dynamic onboarding, physical dimensions, nominal unit weights,
    tolerances, and 8-stage lifecycle without any hardcoded inventory classes.
    """
    __tablename__ = "material"

    material_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    name: Any = Column(String(255), nullable=False)
    sku_code: Any = Column(String(64), unique=True, nullable=False, index=True)
    category: Any = Column(String(64), nullable=False)  # STACKED_MATERIAL, BULK_GOODS, DISCRETE_PACKAGE, HAZARD, GENERAL
    deployment_profile: Any = Column(String(64), nullable=False, default="WAREHOUSE_DISPATCH")
    count_unit: Any = Column(String(32), nullable=False, default="piece")  # piece, bag, sheet, tile, rod, bundle, carton, pallet
    packaging_type: Any = Column(String(64), nullable=False, default="loose_unit")  # loose_unit, sealed_case, open_case, bundle, stack, sheet, rod, roll, pallet
    dimensions: Any = Column(JSONType, nullable=True)  # {"length_cm": ..., "width_cm": ..., "height_cm": ...}
    nominal_unit_weight_kg: Any = Column(Numeric(10, 3), nullable=True)
    weight_tolerance_pct: Any = Column(Numeric(5, 2), nullable=False, default=5.0)
    length_m: Any = Column(Numeric(8, 3), nullable=True)
    diameter_mm: Any = Column(Numeric(8, 2), nullable=True)
    area_sqm: Any = Column(Numeric(8, 3), nullable=True)
    volume_cbm: Any = Column(Numeric(8, 3), nullable=True)
    bundle_quantity: Any = Column(Integer, nullable=True)
    units_per_package: Any = Column(Integer, nullable=False, default=1)
    counting_tier: Any = Column(String(32), nullable=False, default="SINGLE_UNIT")  # SINGLE_UNIT, PACKAGED_BOX, BULK_MATERIAL
    barcode: Any = Column(String(64), nullable=True)
    rfid_epc_prefix: Any = Column(String(64), nullable=True)
    visual_attributes: Any = Column(JSONType, nullable=True)  # {"color": ..., "texture": ..., "shape": ...}
    approved_model_class: Any = Column(String(64), nullable=True)
    status: Any = Column(String(32), nullable=False, default="DRAFT")
    effective_from: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    revision: Any = Column(Integer, nullable=False, default=1)
    created_by: Any = Column(String(128), nullable=False, default="system")
    approved_by: Any = Column(String(128), nullable=True)
    notes: Any = Column(Text, nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'DATA_COLLECTION', 'ANNOTATION', 'TRAINING', 'EVALUATION', 'SHADOW', 'APPROVED', 'ACTIVE')",
            name="chk_material_status",
        ),
        CheckConstraint(
            "deployment_profile IN ('RETAIL_EXIT', 'WAREHOUSE_DISPATCH', 'INDUSTRIAL_PERIMETER')",
            name="chk_material_deployment_profile",
        ),
        CheckConstraint(
            "counting_tier IN ('SINGLE_UNIT', 'PACKAGED_BOX', 'BULK_MATERIAL')",
            name="chk_material_counting_tier",
        ),
    )

    package_definitions = relationship("PackageDefinition", back_populates="material", cascade="all, delete-orphan")
    movement_ledgers = relationship("MaterialMovementLedger", back_populates="material", cascade="all, delete-orphan")
    inventory_balances = relationship("MaterialInventoryBalance", back_populates="material", cascade="all, delete-orphan")


class PackageDefinition(Base):
    """Versioned case, pack, or bundle packaging definition.
    
    Prevents mutating historical pack-size values and preserves arithmetic auditability.
    """
    __tablename__ = "package_definition"

    definition_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    material_id: Any = Column(String(36), ForeignKey("material.material_id", ondelete="CASCADE"), nullable=False, index=True)
    units_per_package: Any = Column(Integer, nullable=False)
    package_barcode: Any = Column(String(64), nullable=True)
    rfid_prefix: Any = Column(String(64), nullable=True)
    gross_weight_kg: Any = Column(Numeric(10, 3), nullable=True)
    net_weight_kg: Any = Column(Numeric(10, 3), nullable=True)
    tolerance_range_pct: Any = Column(Numeric(5, 2), nullable=False, default=5.0)
    effective_start: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    effective_end: Any = Column(DateTime(timezone=True), nullable=True)
    evidence_source: Any = Column(String(64), nullable=False, default="MANUFACTURER_SPEC")
    approval_status: Any = Column(String(32), nullable=False, default="APPROVED")
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("units_per_package > 0", name="chk_pkg_def_units_pos"),
        CheckConstraint("approval_status IN ('PENDING', 'APPROVED', 'SUPERSEDED')", name="chk_pkg_def_status"),
    )

    material = relationship("Material", back_populates="package_definitions")


class Employee(Base):
    __tablename__ = "employee"

    employee_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    name: Any = Column(String(255), nullable=False)
    role: Any = Column(String(128), nullable=False)
    rfid_badge_id: Any = Column(String(128), unique=True, nullable=False, index=True)
    shift_id: Any = Column(String(36), ForeignKey("shift.shift_id"), nullable=True)
    active_flag: Any = Column(Boolean, nullable=False, default=True)
    face_embedding: Any = Column(JSONType, nullable=True)  # 512-d ArcFace vector or JSON array
    embedding_updated_at: Any = Column(DateTime(timezone=True), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    shift = relationship("Shift", back_populates="employees")
    exit_events = relationship("ExitEvent", back_populates="employee")
    face_matches = relationship("FaceMatchAttempt", back_populates="employee")
    movement_ledgers = relationship("MaterialMovementLedger", back_populates="employee")


class Lane(Base):
    __tablename__ = "lane"

    lane_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    label: Any = Column(String(128), nullable=False)
    store_id: Any = Column(String(36), ForeignKey("store.store_id"), nullable=False)
    camera_ids: Any = Column(JSONType, nullable=False, default=list)  # list of camera IDs/IPs
    rfid_antenna_id: Any = Column(String(128), nullable=True)
    weight_sensor_id: Any = Column(String(128), nullable=True)
    turnstile_ctrl_id: Any = Column(String(128), nullable=True)
    status: Any = Column(String(32), nullable=False, default="ONLINE")
    last_heartbeat_at: Any = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('ONLINE', 'OFFLINE', 'DEGRADED')", name="chk_lane_status"),
    )

    store = relationship("Store", back_populates="lanes")
    exit_events = relationship("ExitEvent", back_populates="lane")
    cameras = relationship("Camera", back_populates="lane")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Camera Fleet Management Models
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
    pipeline_mode: Any = Column(String(64), nullable=False, default="STANDARD_DETECTION")
    roi_polygon: Any = Column(JSONType, nullable=True)  # Dynamic Region of Interest (e.g. [[x,y], ...])
    ignored_classes: Any = Column(JSONType, nullable=True)  # Classes to ignore (e.g. ["STORAGE_SHELF"])
    status: Any = Column(String(32), nullable=False, default="PENDING_SETUP")
    last_heartbeat_at: Any = Column(DateTime(timezone=True), nullable=True)
    offline_since: Any = Column(DateTime(timezone=True), nullable=True)
    added_by: Any = Column(String(36), ForeignKey("app_user.user_id"), nullable=True)
    added_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    removed_at: Any = Column(DateTime(timezone=True), nullable=True)  # Soft delete

    __table_args__ = (
        CheckConstraint("status IN ('ONLINE', 'OFFLINE', 'DEGRADED', 'PENDING_SETUP')", name="chk_camera_status"),
        CheckConstraint("pairing_method IN ('MANUAL', 'QR_CAMERA_DISPLAYED', 'QR_APP_GENERATED')", name="chk_camera_pairing_method"),
        CheckConstraint("pipeline_mode IN ('STANDARD_DETECTION', 'MATERIAL_SEGMENTATION', 'PERIMETER_TRIPWIRE_GATE')", name="chk_camera_pipeline_mode"),
        Index("idx_camera_lane", "lane_id"),
    )

    lane = relationship("Lane", back_populates="cameras")
    static_image_detections = relationship("StaticImageDetection", back_populates="camera", cascade="all, delete-orphan")
    virtual_tripwires = relationship("VirtualTripwireConfig", back_populates="camera", cascade="all, delete-orphan")
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

    heartbeat_id: Any = Column(Integer, primary_key=True, autoincrement=True)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    received_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)
    fps_observed: Any = Column(Numeric(6, 2), nullable=True)
    bitrate_kbps: Any = Column(Numeric(10, 2), nullable=True)
    dropped_frames: Any = Column(Integer, nullable=True, default=0)

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
        CheckConstraint("verdict IN ('PASS', 'MATCH', 'MISMATCH', 'PARTIAL', 'UNVERIFIED', 'REVIEW_REQUIRED')", name="chk_exit_event_verdict"),
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
    appearance_summary = relationship("PersonAppearanceSummary", uselist=False, back_populates="event", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="event")


class ExitEventLineItem(Base):
    __tablename__ = "exit_event_line_item"

    line_item_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    event_id: Any = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    product_id: Any = Column(String(36), ForeignKey("product.product_id"), nullable=False)
    cases_qty: Any = Column(Integer, nullable=False, default=0)
    units_qty: Any = Column(Integer, nullable=False, default=0)

    event = relationship("ExitEvent", back_populates="line_items")
    product = relationship("Product", back_populates="line_items")


class VisionDetection(Base):
    __tablename__ = "vision_detection"

    detection_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    event_id: Any = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=True)
    frame_ts: Any = Column(DateTime(timezone=True), nullable=False)
    model_version: Any = Column(String(64), nullable=False)
    bbox: Any = Column(JSONType, nullable=False)  # [x, y, w, h] normalized or pixel
    class_label: Any = Column(String(64), nullable=False)  # 'case_full', 'case_open', 'single_unit', 'person'
    product_id: Any = Column(String(36), ForeignKey("product.product_id"), nullable=True)
    confidence: Any = Column(Numeric(5, 4), nullable=False)

    event = relationship("ExitEvent", back_populates="vision_detections")
    camera = relationship("Camera", back_populates="vision_detections")
    product = relationship("Product", back_populates="vision_detections")


class StaticImageDetection(Base):
    __tablename__ = "static_image_detection"

    detection_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id", ondelete="CASCADE"), nullable=False)
    frame_ts: Any = Column(DateTime(timezone=True), nullable=False)
    bbox: Any = Column(JSONType, nullable=False)  # [x, y, w, h]
    liveness_score: Any = Column(Numeric(5, 4), nullable=False)
    classification: Any = Column(String(64), nullable=False)
    classification_confidence: Any = Column(Numeric(5, 4), nullable=False)
    model_version: Any = Column(String(64), nullable=False)
    suppressed_alert: Any = Column(Boolean, nullable=False, default=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint(
            "classification IN ('RELIGIOUS_IMAGE','PERSON_PHOTO','POSTER_OR_SIGNAGE','SCREEN_DISPLAY','UNCLASSIFIED_STATIC')",
            name="chk_static_classification",
        ),
        Index("idx_static_cam_time", "camera_id", "frame_ts"),
    )

    camera = relationship("Camera", back_populates="static_image_detections")


class RfidRead(Base):
    __tablename__ = "rfid_read"

    read_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    event_id: Any = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    epc_tag: Any = Column(String(128), nullable=False)
    antenna_id: Any = Column(String(64), nullable=False)
    rssi: Any = Column(Numeric(6, 2), nullable=True)
    read_at: Any = Column(DateTime(timezone=True), nullable=False)

    event = relationship("ExitEvent", back_populates="rfid_reads")


class WeightReading(Base):
    __tablename__ = "weight_reading"

    reading_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    event_id: Any = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    sensor_id: Any = Column(String(64), nullable=False)
    weight_kg: Any = Column(Numeric(10, 3), nullable=False)
    read_at: Any = Column(DateTime(timezone=True), nullable=False)

    event = relationship("ExitEvent", back_populates="weight_readings")


class Invoice(Base):
    __tablename__ = "invoice"

    invoice_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    invoice_number: Any = Column(String(128), unique=True, nullable=False, index=True)
    carrier_name: Any = Column(String(255), nullable=False)
    store_destination: Any = Column(String(255), nullable=False)
    source: Any = Column(String(32), nullable=False, default="SCAN")
    raw_file_url: Any = Column(Text, nullable=False)
    ocr_model_version: Any = Column(String(64), nullable=False)
    extraction_confidence: Any = Column(Numeric(5, 4), nullable=False)
    extracted_json: Any = Column(JSONType, nullable=False)  # line items array
    declared_total_units: Any = Column(Integer, nullable=True)
    linked_event_id: Any = Column(String(36), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("source IN ('SCAN', 'EMAIL', 'API')", name="chk_invoice_source"),
    )

    linked_events = relationship("ExitEvent", foreign_keys=[ExitEvent.invoice_id], back_populates="invoice")


class FaceMatchAttempt(Base):
    __tablename__ = "face_match_attempt"

    attempt_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    event_id: Any = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False)
    matched_employee_id: Any = Column(String(36), ForeignKey("employee.employee_id"), nullable=True)
    similarity: Any = Column(Numeric(5, 4), nullable=False)
    model_version: Any = Column(String(64), nullable=False)
    decision: Any = Column(String(32), nullable=False)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("decision IN ('MATCHED', 'NO_MATCH', 'LOW_CONFIDENCE')", name="chk_face_decision"),
    )

    event = relationship("ExitEvent", back_populates="face_matches")
    employee = relationship("Employee", back_populates="face_matches")


class PersonAppearanceSummary(Base):
    """Stores non-invasive visual appearance summary and Re-ID cluster embeddings for unverified persons."""
    __tablename__ = "person_appearance_summary"

    summary_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    event_id: Any = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False, index=True)
    face_match_attempt_id: Any = Column(String(36), ForeignKey("face_match_attempt.attempt_id"), nullable=True)
    clothing_top_color: Any = Column(String(64), nullable=False)
    clothing_bottom_color: Any = Column(String(64), nullable=False)
    build_category: Any = Column(String(32), nullable=False)
    build_confidence: Any = Column(Numeric(5, 4), nullable=False)
    accessories: Any = Column(JSONType, nullable=False, default=list)  # e.g. ["bag", "cap", "glasses"]
    accessories_confidence: Any = Column(JSONType, nullable=False, default=dict)  # {"bag": 0.88, "cap": 0.76}
    model_version: Any = Column(String(64), nullable=False, default="appearance-reid-v1.0")
    reid_embedding: Any = Column(JSONType, nullable=True)  # 256-d normalized float vector
    reid_cluster_id: Any = Column(String(36), nullable=True, index=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)

    __table_args__ = (
        CheckConstraint(
            "build_category IN ('SHORTER','AVERAGE','TALLER','UNKNOWN')",
            name="chk_appearance_build_category",
        ),
        Index("idx_appearance_cluster_created", "reid_cluster_id", "created_at"),
    )

    event = relationship("ExitEvent", back_populates="appearance_summary")
    face_match_attempt = relationship("FaceMatchAttempt")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Alerts, Alarms & Append-Only Audit Trail
# ─────────────────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alert"

    alert_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    event_id: Any = Column(String(36), ForeignKey("exit_event.event_id"), nullable=True, index=True)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=True, index=True)
    alert_type: Any = Column(String(64), nullable=False)
    severity: Any = Column(String(32), nullable=False, index=True)
    delta_units: Any = Column(Integer, nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)
    status: Any = Column(String(32), nullable=False, default="OPEN", index=True)
    resolved_by: Any = Column(String(128), nullable=True)
    resolution_note: Any = Column(Text, nullable=True)
    resolved_at: Any = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('SENSOR_DISAGREEMENT', 'OVER_CARRY', 'UNDER_DECLARE', 'UNAUTHORIZED_ACCESS', 'INTRUSION', 'CAMERA_OFFLINE', 'FIRE_HAZARD', 'SUSPICIOUS_BEHAVIOR', 'PPE_VIOLATION', 'MATERIAL_DEFECT')",
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

    dispatch_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    alert_id: Any = Column(String(36), ForeignKey("alert.alert_id"), nullable=False)
    channel: Any = Column(String(32), nullable=False)
    status: Any = Column(String(32), nullable=False, default="QUEUED")
    attempted_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    error_detail: Any = Column(Text, nullable=True)

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

    audit_id: Any = Column(Integer, primary_key=True, autoincrement=True)
    entity_type: Any = Column(String(64), nullable=False, index=True)
    entity_id: Any = Column(String(36), nullable=False, index=True)
    action: Any = Column(String(64), nullable=False)
    actor_id: Any = Column(String(36), nullable=True)
    actor_type: Any = Column(String(32), nullable=False)
    before_state: Any = Column(JSONType, nullable=True)
    after_state: Any = Column(JSONType, nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)

    __table_args__ = (
        CheckConstraint("actor_type IN ('USER', 'SYSTEM', 'MODEL')", name="chk_audit_actor_type"),
    )


class AppUser(Base):
    __tablename__ = "app_user"

    user_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    email: Any = Column(String(255), unique=True, nullable=False, index=True)
    password_hash: Any = Column(String(255), nullable=False)
    role: Any = Column(String(32), nullable=False)
    store_id: Any = Column(String(36), ForeignKey("store.store_id"), nullable=True)
    mfa_enabled: Any = Column(Boolean, nullable=False, default=False)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

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


# ─────────────────────────────────────────────────────────────────────────────
# 8. Industrial Dispatch & Warehouse Exit Models
# ─────────────────────────────────────────────────────────────────────────────

class DispatchSession(Base):
    __tablename__ = "dispatch_session"

    session_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    dock_lane_id: Any = Column(String(36), ForeignKey("lane.lane_id"), nullable=False)
    manifest_id: Any = Column(String(128), nullable=True, index=True)
    carrier_employee_id: Any = Column(String(36), ForeignKey("employee.employee_id"), nullable=True)
    vehicle_identifier: Any = Column(String(64), nullable=True)
    status: Any = Column(String(32), nullable=False, default="ACTIVE")
    started_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    completed_at: Any = Column(DateTime(timezone=True), nullable=True)
    before_count: Any = Column(JSONType, nullable=False, default=dict)
    after_count: Any = Column(JSONType, nullable=False, default=dict)
    removed_delta: Any = Column(JSONType, nullable=False, default=dict)
    manifest_expected: Any = Column(JSONType, nullable=False, default=dict)
    discrepancy_type: Any = Column(String(32), nullable=False, default="MATCH")
    discrepancy_magnitude: Any = Column(Integer, nullable=False, default=0)
    tracking_interrupted_seconds: Any = Column(Numeric(8, 2), nullable=False, default=0.0)
    archival_snapshot_url: Any = Column(Text, nullable=True)
    notes: Any = Column(Text, nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'COMPLETED', 'FLAGGED_DISCREPANCY', 'ABORTED')", name="chk_dispatch_status"),
        CheckConstraint("discrepancy_type IN ('MATCH', 'OVER_AUTHORIZED', 'UNDER_COUNT', 'UNMANIFESTED_SKU')", name="chk_dispatch_discrepancy"),
        Index("idx_dispatch_dock_lane", "dock_lane_id"),
        Index("idx_dispatch_status", "status"),
    )

    lane = relationship("Lane")
    carrier = relationship("Employee")


class VirtualTripwireConfig(Base):
    __tablename__ = "virtual_tripwire_config"

    tripwire_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=False)
    label: Any = Column(String(128), nullable=False)
    line_coords: Any = Column(JSONType, nullable=False, default=lambda: [[0.1, 0.5], [0.9, 0.5]])
    direction_mode: Any = Column(String(32), nullable=False, default="BIDIRECTIONAL")
    active: Any = Column(Boolean, nullable=False, default=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        CheckConstraint("direction_mode IN ('BIDIRECTIONAL', 'ENTRY_ONLY', 'EXIT_ONLY', 'ENTRY', 'EXIT', 'BOTH')", name="chk_tripwire_direction_mode"),
        Index("idx_tripwire_camera", "camera_id"),
    )


    camera = relationship("Camera", back_populates="virtual_tripwires")
    crossing_events = relationship("TripwireCrossingEvent", back_populates="tripwire", cascade="all, delete-orphan")


class TripwireCrossingEvent(Base):
    __tablename__ = "tripwire_crossing_event"

    crossing_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    tripwire_id: Any = Column(String(36), ForeignKey("virtual_tripwire_config.tripwire_id"), nullable=False)
    camera_id: Any = Column(String(36), nullable=False)
    track_id: Any = Column(String(64), nullable=False)
    timestamp: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)
    direction: Any = Column(String(16), nullable=False)
    entity_type: Any = Column(String(32), nullable=False, default="PERSON")
    biometric_status: Any = Column(String(32), nullable=False, default="UNAVAILABLE")
    matched_employee_id: Any = Column(String(36), ForeignKey("employee.employee_id"), nullable=True)
    is_tailgating: Any = Column(Boolean, nullable=False, default=False)
    tailgating_details: Any = Column(JSONType, nullable=True)
    snapshot_url: Any = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("direction IN ('ENTRY', 'EXIT', 'UNKNOWN')", name="chk_crossing_direction"),
        CheckConstraint("biometric_status IN ('VERIFIED_KNOWN', 'UNKNOWN_INTRUDER', 'UNAVAILABLE')", name="chk_crossing_biometric"),
        Index("idx_crossing_tripwire", "tripwire_id"),
        Index("idx_crossing_timestamp", "timestamp"),
    )

    tripwire = relationship("VirtualTripwireConfig", back_populates="crossing_events")
    employee = relationship("Employee")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Real-Time Material Flow, Dynamic Inventory Ledger & Defect Tracking Models
# ─────────────────────────────────────────────────────────────────────────────

class MaterialMovementLedger(Base):
    """Immutable transaction ledger recording confirmed physical material movement.
    
    Tracks arrivals (IN), dispatches (OUT), internal transfers, adjustments, and returns,
    capturing spatial context (camera, zone, tripwire, track_id), carrier/person attribution,
    packaging tier conversion, defect condition, and discrepancy tags.
    """
    __tablename__ = "material_movement_ledger"

    ledger_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    transaction_type: Any = Column(String(32), nullable=False)  # IN, OUT, ADJUSTMENT, TRANSFER_IN, TRANSFER_OUT, RETURN
    material_id: Any = Column(String(36), ForeignKey("material.material_id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=True, index=True)
    zone_id: Any = Column(String(64), nullable=True)
    tripwire_id: Any = Column(String(36), ForeignKey("virtual_tripwire_config.tripwire_id"), nullable=True)
    track_id: Any = Column(String(64), nullable=True, index=True)
    direction: Any = Column(String(16), nullable=False, default="UNKNOWN")  # ENTRY, EXIT, TRAVERSAL, UNKNOWN
    person_id: Any = Column(String(36), ForeignKey("employee.employee_id"), nullable=True, index=True)
    person_name: Any = Column(String(255), nullable=False, default="UNKNOWN_PERSON")
    person_identity_status: Any = Column(String(32), nullable=False, default="UNKNOWN_PERSON")  # VERIFIED_KNOWN, UNKNOWN_PERSON
    carrier_relation: Any = Column(String(32), nullable=False, default="standalone")  # carrying, transporting, near, loaded_to_vehicle, standalone
    packaging_type: Any = Column(String(64), nullable=False, default="loose_unit")  # case, box, pallet, bag, bundle, loose_unit
    package_quantity: Any = Column(Integer, nullable=False, default=0)
    units_per_package: Any = Column(Integer, nullable=False, default=1)
    unit_quantity: Any = Column(Integer, nullable=False, default=0)  # Total base inventory units
    defect_status: Any = Column(String(32), nullable=False, default="NORMAL")  # NORMAL, DAMAGED, DEFECTIVE, UNKNOWN_CONDITION
    defect_severity: Any = Column(String(32), nullable=False, default="NONE")  # NONE, LOW, MEDIUM, HIGH, CRITICAL
    confidence: Any = Column(Numeric(5, 4), nullable=False, default=0.9500)
    discrepancy_units: Any = Column(Integer, nullable=False, default=0)
    discrepancy_reason: Any = Column(String(255), nullable=True)
    source_frame_path: Any = Column(Text, nullable=True)
    timestamp: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('IN', 'OUT', 'ADJUSTMENT', 'TRANSFER_IN', 'TRANSFER_OUT', 'RETURN')",
            name="chk_ledger_tx_type",
        ),
        CheckConstraint(
            "direction IN ('ENTRY', 'EXIT', 'TRAVERSAL', 'UNKNOWN', 'IN', 'OUT')",
            name="chk_ledger_direction",
        ),
        CheckConstraint(
            "person_identity_status IN ('VERIFIED_KNOWN', 'UNKNOWN_PERSON', 'UNAVAILABLE')",
            name="chk_ledger_person_status",
        ),
        CheckConstraint(
            "defect_status IN ('NORMAL', 'DAMAGED', 'DEFECTIVE', 'UNKNOWN_CONDITION')",
            name="chk_ledger_defect_status",
        ),
        Index("idx_ledger_mat_ts", "material_id", "timestamp"),
        Index("idx_ledger_cam_ts", "camera_id", "timestamp"),
    )

    material = relationship("Material", back_populates="movement_ledgers")
    camera = relationship("Camera")
    employee = relationship("Employee", back_populates="movement_ledgers")
    tripwire = relationship("VirtualTripwireConfig")
    defect_events = relationship("MaterialDefectEvent", back_populates="ledger_entry")


class MaterialInventoryBalance(Base):
    """Real-time calculated on-hand stock and ledger balance per material and storage location.
    
    Enforces the atomic accounting identity:
    Opening Stock + Confirmed IN - Confirmed OUT + Adjustments == Current Stock
    """
    __tablename__ = "material_inventory_balance"

    balance_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    material_id: Any = Column(String(36), ForeignKey("material.material_id", ondelete="CASCADE"), nullable=False, index=True)
    location_id: Any = Column(String(64), nullable=False, default="MAIN_WAREHOUSE", index=True)
    opening_stock: Any = Column(Integer, nullable=False, default=0)
    incoming_confirmed: Any = Column(Integer, nullable=False, default=0)
    outgoing_confirmed: Any = Column(Integer, nullable=False, default=0)
    defective_stock: Any = Column(Integer, nullable=False, default=0)
    adjusted_stock: Any = Column(Integer, nullable=False, default=0)
    current_stock: Any = Column(Integer, nullable=False, default=0)
    last_reconciled_at: Any = Column(DateTime(timezone=True), nullable=True)
    last_transaction_id: Any = Column(String(36), nullable=True)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        Index("idx_balance_mat_loc", "material_id", "location_id", unique=True),
    )

    material = relationship("Material", back_populates="inventory_balances")


class MaterialDefectEvent(Base):
    """Evidence record for detected physical packaging or material damage."""
    __tablename__ = "material_defect_event"

    defect_event_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    ledger_id: Any = Column(String(36), ForeignKey("material_movement_ledger.ledger_id", ondelete="SET NULL"), nullable=True)
    material_id: Any = Column(String(36), ForeignKey("material.material_id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=True)
    defect_class: Any = Column(String(64), nullable=False)  # TORN_BAG, DENTED_CONTAINER, CRACKED_TILE, BENT_ROD, BROKEN_SEAL
    severity: Any = Column(String(32), nullable=False, default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    confidence: Any = Column(Numeric(5, 4), nullable=False, default=0.9500)
    affected_units: Any = Column(Integer, nullable=False, default=1)
    snapshot_url: Any = Column(Text, nullable=True)
    status: Any = Column(String(32), nullable=False, default="QUARANTINED")  # QUARANTINED, ACCEPTED_WITH_CONCESSION, REJECTED, SCRAPPED
    details: Any = Column(JSONType, nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)

    __table_args__ = (
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="chk_defect_evt_severity",
        ),
        CheckConstraint(
            "status IN ('QUARANTINED', 'ACCEPTED_WITH_CONCESSION', 'REJECTED', 'SCRAPPED')",
            name="chk_defect_evt_status",
        ),
    )

    material = relationship("Material")
    camera = relationship("Camera")
    ledger_entry = relationship("MaterialMovementLedger", back_populates="defect_events")




class EvidenceArtifact(Base):
    __tablename__ = "evidence_artifact"

    artifact_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    event_id: Any = Column(String(36), ForeignKey("exit_event.event_id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=True)
    artifact_type: Any = Column(String(32), nullable=False) # SNAPSHOT, CLIP, OCR_DOCUMENT, REPORT
    s3_key: Any = Column(String(512), nullable=False)
    cryptographic_hash: Any = Column(String(128), nullable=False) # SHA-256 for chain of custody
    captured_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    retention_expires_at: Any = Column(DateTime(timezone=True), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

class SmartWallLayout(Base):
    __tablename__ = "smart_wall_layout"

    layout_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    name: Any = Column(String(128), nullable=False)
    grid_type: Any = Column(String(16), nullable=False) # 1x1, 2x2, 3x3, 4x4, 1+5, 1+7
    camera_mappings: Any = Column(JSONType, nullable=False, default=dict) # {"0": "cam-1", "1": "cam-2"}
    is_default: Any = Column(Boolean, nullable=False, default=False)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

class AccessControlEvent(Base):
    __tablename__ = "access_control_event"

    access_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    door_id: Any = Column(String(64), nullable=False, index=True)
    employee_id: Any = Column(String(36), ForeignKey("employee.employee_id"), nullable=True)
    credential_type: Any = Column(String(32), nullable=False) # RFID_BADGE, FACE, PIN, BLUETOOTH
    access_status: Any = Column(String(32), nullable=False) # GRANTED, DENIED, ANTI_PASSBACK_VIOLATION
    denial_reason: Any = Column(String(128), nullable=True)
    event_time: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)

class VehicleDetection(Base):
    __tablename__ = "vehicle_detection"

    detection_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=False, index=True)
    license_plate: Any = Column(String(32), nullable=True, index=True)
    plate_confidence: Any = Column(Numeric(5, 4), nullable=True)
    vehicle_class: Any = Column(String(32), nullable=False) # CAR, TRUCK, VAN, MOTORCYCLE
    color: Any = Column(String(32), nullable=True)
    direction: Any = Column(String(32), nullable=True)
    watchlist_hit: Any = Column(Boolean, nullable=False, default=False)
    event_time: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)

