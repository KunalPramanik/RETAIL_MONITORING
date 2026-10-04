from datetime import datetime, timezone
from typing import Optional, List, Any
import uuid
import json
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
    Index,
    JSON,
    TypeDecorator,
)
from sqlalchemy.orm import declarative_base, relationship
Base = declarative_base()

def generate_uuid() -> str:
    return str(uuid.uuid4())

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

class JSONType(TypeDecorator):
    """Platform-independent JSON type."""
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return value
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value
        return None

