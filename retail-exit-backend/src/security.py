"""Cryptographic Security & Password Hashing Module

Enforces secure password verification, bcrypt key derivation,
and JWT access token creation using secrets loaded strictly from Settings.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
from jose import jwt
import bcrypt
from src.core.config import settings

logger = logging.getLogger("secops.security")

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against a stored bcrypt hash with sanitized error logging."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
    except ValueError as val_err:
        logger.warning("Bcrypt verification failed due to malformed hash format.")
        return False
    except Exception as err:
        logger.warning("Unexpected non-fatal error during password verification.")
        return False

def get_password_hash(password: str) -> str:
    """Computes a cryptographically salted bcrypt hash for the provided password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")

def create_access_token(
    subject: Union[str, Any],
    role: Optional[str] = None,
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generates a signed JWT bearer token using the mandatory configured SECRET_KEY."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode: dict[str, Any] = {"exp": expire, "sub": str(subject)}
    if role:
        to_encode["role"] = str(role).upper().strip()
    if email:
        to_encode["email"] = str(email).lower().strip()
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    subject: Union[str, Any],
    role: Optional[str] = None,
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generates a cryptographically signed refresh JWT token with a unique jti."""
    import uuid
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=getattr(settings.security, "refresh_token_expire_days", 7))
    to_encode: dict[str, Any] = {
        "exp": expire,
        "sub": str(subject),
        "token_use": "refresh",
        "jti": str(uuid.uuid4()),
    }
    if role:
        to_encode["role"] = str(role).upper().strip()
    if email:
        to_encode["email"] = str(email).lower().strip()
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


_revoked_tokens: set = set()

def revoke_token(token: str) -> None:
    """Adds a token to the in-memory revocation blocklist."""
    if token:
        _revoked_tokens.add(token.strip())

def is_token_revoked(token: str) -> bool:
    """Checks whether the given token has been revoked."""
    if not token:
        return False
    return token.strip() in _revoked_tokens


# --- Login Attempt Tracking & Temporary Account Lockout ---
import time
_failed_login_history: dict[str, list[float]] = {}
_lockouts: dict[str, float] = {}

def record_failed_login(identifier: str) -> tuple[int, bool]:
    """Records a failed authentication attempt. Returns (total_attempts_in_window, is_now_locked)."""
    clean_id = identifier.strip().lower()
    now = time.time()
    lockout_sec = getattr(settings.security, "lockout_duration_seconds", 900)
    max_attempts = getattr(settings.security, "max_login_attempts", 5)

    history = _failed_login_history.setdefault(clean_id, [])
    # Evict attempts outside window
    history = [t for t in history if (now - t) < lockout_sec]
    history.append(now)
    _failed_login_history[clean_id] = history

    if len(history) >= max_attempts:
        _lockouts[clean_id] = now + lockout_sec
        return len(history), True
    return len(history), False

def is_account_locked(identifier: str) -> tuple[bool, int]:
    """Checks whether an account identifier is currently locked out.
    Returns (is_locked, remaining_seconds).
    """
    clean_id = identifier.strip().lower()
    now = time.time()
    unlock_time = _lockouts.get(clean_id, 0)
    if unlock_time > now:
        return True, int(unlock_time - now)
    if clean_id in _lockouts:
        del _lockouts[clean_id]
    return False, 0

def reset_failed_logins(identifier: str) -> None:
    """Clears failed login attempt history and lockout state upon successful authentication."""
    clean_id = identifier.strip().lower()
    _failed_login_history.pop(clean_id, None)
    _lockouts.pop(clean_id, None)
