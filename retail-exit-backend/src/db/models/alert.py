from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

class AppUser(Base):
    __tablename__ = "app_user"

    user_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    email: Any = Column(String(255), unique=True, nullable=False, index=True)
    username: Any = Column(String(64), unique=True, nullable=True, index=True)
    password_hash: Any = Column(String(255), nullable=False)
    role: Any = Column(String(32), nullable=False)
    store_id: Any = Column(String(36), ForeignKey("store.store_id"), nullable=True)
    mfa_enabled: Any = Column(Boolean, nullable=False, default=False)
    is_active: Any = Column(Boolean, nullable=False, default=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("role IN ('SUPERVISOR', 'ADMIN', 'VIEWER')", name="chk_app_user_role"),
    )

    store = relationship("Store", back_populates="users")

    @property
    def id(self) -> str:
        """Compatibility alias for primary key user_id."""
        return self.user_id

    @property
    def hashed_password(self) -> str:
        """Compatibility alias for password_hash."""
        return self.password_hash

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

