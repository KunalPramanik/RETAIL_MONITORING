from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

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

    linked_events = relationship("ExitEvent", foreign_keys="[ExitEvent.invoice_id]", back_populates="invoice")

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
        CheckConstraint("decision IN ('MATCHED', 'NO_MATCH', 'LOW_CONFIDENCE', 'DISABLED', 'BYPASS')", name="chk_face_decision"),
    )

    event = relationship("ExitEvent", back_populates="face_matches")
    employee = relationship("Employee", back_populates="face_matches")

