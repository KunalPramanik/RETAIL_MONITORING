from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

class Store(Base):
    __tablename__ = "store"

    store_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    name: Any = Column(String(255), nullable=False)
    address: Any = Column(Text, nullable=True)
    timezone: Any = Column(String(64), nullable=False, default="UTC")

    lanes = relationship("Lane", back_populates="store", cascade="all, delete-orphan")
    users = relationship("AppUser", back_populates="store")
    threshold_configs = relationship("ThresholdConfig", back_populates="store")

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

