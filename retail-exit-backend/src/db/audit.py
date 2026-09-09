"""Append-Only Audit Log Helper Module

Ensures immutable, transactional audit logging for all critical system state mutations.
"""

from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import AuditLog, get_utc_now


async def log_audit_entry(
    session: AsyncSession,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_type: str = "SYSTEM",
    actor_id: Optional[str] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Writes an immutable audit log entry within the caller's active database transaction."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        actor_type=actor_type,
        before_state=before_state,
        after_state=after_state,
        created_at=get_utc_now(),
    )
    session.add(entry)
    return entry

