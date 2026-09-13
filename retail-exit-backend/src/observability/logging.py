"""Structured JSON Logging Configuration Module with Credential Masking & Correlation Tracking"""

import logging
import json
import sys
import re
from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Optional

# Async request-scoped correlation ID
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
camera_id_ctx: ContextVar[Optional[str]] = ContextVar("camera_id", default=None)
event_id_ctx: ContextVar[Optional[str]] = ContextVar("event_id", default=None)


def sanitize_sensitive_data(text: str) -> str:
    """Masks camera passwords, RTSP credentials, tokens, and secret hashes in log outputs."""
    if not text:
        return text

    # Mask rtsp://user:pass@host -> rtsp://***:***@host
    sanitized = re.sub(r"rtsp://([^:/@]+):([^/@]+)@", r"rtsp://***:***@", text)

    # Mask HTTP Basic Auth URLs http://user:pass@host -> http://***:***@host
    sanitized = re.sub(r"http(s?)://([^:/@]+):([^/@]+)@", r"http\1://***:***@", sanitized)

    # Mask JSON password/token/credentials keys
    sanitized = re.sub(
        r'("?(?:password|credentials|secret_key|api_key|token)"?\s*[:=]\s*)"[^"]+"',
        r'\1"***"',
        sanitized,
        flags=re.IGNORECASE,
    )

    return sanitized


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        raw_msg = record.getMessage()
        clean_msg = sanitize_sensitive_data(raw_msg)

        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": clean_msg,
        }

        # Inject request-level or record-level correlation and entity IDs
        corr_id = getattr(record, "correlation_id", None) or correlation_id_ctx.get()
        if corr_id:
            log_obj["correlation_id"] = corr_id

        cam_id = getattr(record, "camera_id", None) or camera_id_ctx.get()
        if cam_id:
            log_obj["camera_id"] = cam_id

        ev_id = getattr(record, "event_id", None) or event_id_ctx.get()
        if ev_id:
            log_obj["event_id"] = ev_id

        if hasattr(record, "lane_id"):
            log_obj["lane_id"] = getattr(record, "lane_id")

        if record.exc_info:
            clean_exc = sanitize_sensitive_data(self.formatException(record.exc_info))
            log_obj["exception"] = clean_exc

        return json.dumps(log_obj)


def configure_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [handler]
