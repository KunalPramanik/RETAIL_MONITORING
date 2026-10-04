from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

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

