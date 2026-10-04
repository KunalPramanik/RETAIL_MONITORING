from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

class Shift(Base):
    __tablename__ = "shift"

    shift_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    label: Any = Column(String(128), nullable=False)
    starts_at: Any = Column(String(8), nullable=False)  # HH:MM:SS
    ends_at: Any = Column(String(8), nullable=False)    # HH:MM:SS

    employees = relationship("Employee", back_populates="shift")

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

