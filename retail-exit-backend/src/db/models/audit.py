from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

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

