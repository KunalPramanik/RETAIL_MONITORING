from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

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

