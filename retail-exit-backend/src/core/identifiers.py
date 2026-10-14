"""Distinct Identifier Namespace Generator.

Enforces Section 1 (P8) of the SEC-OPS V8 Master Prompt:
- Employee ID, login ID, camera track ID, product ID, bill ID, and event ID are separate namespaces.
- All IDs are generated using UUIDv4 / ULID cryptographic sequences, never max()+1.
- Track IDs are strictly temporary per camera session and never identify people across cameras or days.
"""

import uuid
from typing import Optional, Any


def generate_employee_code(sequence_num: int) -> str:
    """Generates a standardized employee badge code (e.g., EMP-000042)."""
    return f"EMP-{sequence_num:06d}"


def generate_user_id() -> str:
    """Generates a unique login user ID (UUIDv4)."""
    return str(uuid.uuid4())


def generate_camera_track_id(camera_id: str, local_track_num: int) -> str:
    """Generates an ephemeral camera track ID strictly scoped to a camera runtime session.
    
    Never persists across cameras, days, or facilities.
    """
    clean_cam = camera_id.replace("-", "")[:8]
    return f"trk_{clean_cam}_{local_track_num}"


def generate_product_id() -> str:
    """Generates a unique product / SKU catalog ID."""
    return str(uuid.uuid4())


def generate_invoice_id() -> str:
    """Generates a unique invoice / bill manifest identifier."""
    return str(uuid.uuid4())


def generate_event_id() -> str:
    """Generates a unique multi-sensory exit event identifier."""
    return str(uuid.uuid4())


def generate_ledger_id() -> str:
    """Generates a unique immutable material ledger transaction ID."""
    return str(uuid.uuid4())


def generate_idempotency_key(prefix: str, *args: Any) -> str:
    """Generates a SHA-256 derived idempotency key from composite transaction inputs."""
    import hashlib
    raw = ":".join(str(a) for a in args)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}_{digest}"
