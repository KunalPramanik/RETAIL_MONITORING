from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

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

# Canonical User model is AppUser in alert.py (prevents duplicate user/app_user tables)
from .alert import AppUser as User

