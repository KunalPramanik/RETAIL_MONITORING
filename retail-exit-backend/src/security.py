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
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
