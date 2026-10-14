"""Audit & Fail-Fast Secret Configuration Automated Test Suite

Verifies that SEC-OPS strictly refuses to start with missing environment credentials,
and enforces that zero hardcoded fallback secrets exist in the codebase.
"""

import os
import re
import pytest
from pathlib import Path
from src.core.config import validate_mandatory_env, MANDATORY_ENV_VARS


def test_missing_jwt_secret_fails_startup(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        validate_mandatory_env()
    assert "JWT_SECRET_KEY" in str(exc_info.value)
    assert "refuses to start with insecure fallback defaults" in str(exc_info.value)


def test_missing_database_url_fails_startup(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        validate_mandatory_env()
    assert "DATABASE_URL" in str(exc_info.value)
    assert "refuses to start with insecure fallback defaults" in str(exc_info.value)


def test_missing_mobile_hmac_secret_fails_startup(monkeypatch):
    monkeypatch.delenv("MOBILE_HMAC_SECRET", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        validate_mandatory_env()
    assert "MOBILE_HMAC_SECRET" in str(exc_info.value)
    assert "refuses to start with insecure fallback defaults" in str(exc_info.value)


def test_zero_insecure_hardcoded_defaults_in_source():
    """Scans all Python files in src/ to ensure zero hardcoded default credentials remain."""
    src_dir = Path(__file__).resolve().parent.parent / "src"
    forbidden_patterns = [
        re.compile(r"super-secret-key-change-in-production", re.IGNORECASE),
        re.compile(r"test-secret", re.IGNORECASE),
        re.compile(r"secops-enterprise-hmac-shared-key-2026", re.IGNORECASE),
        re.compile(r"DEFAULT_SECRET_KEY\s*=", re.IGNORECASE),
    ]

    violations = []
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        for pattern in forbidden_patterns:
            matches = pattern.findall(content)
            if matches:
                violations.append(f"{py_file.name}: matched forbidden pattern '{pattern.pattern}'")

    assert len(violations) == 0, f"Found hardcoded secret violations: {violations}"
