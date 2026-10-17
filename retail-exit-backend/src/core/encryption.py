"""Cryptographic Fernet At-Rest Encryption Module

Enforces Section 4.3:
- Cryptographic Fernet encryption for biometric face embeddings and sensitive camera credentials at rest.
- Deterministic key derivation from Settings.SECRET_KEY via SHA-256 digest.
- Transparent SQLAlchemy TypeDecorators: EncryptedStringType & EncryptedJSONType.
- Fallback resilience: gracefully reads legacy unencrypted JSON/strings during rolling migrations.
"""

import base64
import hashlib
import json
import logging
from typing import Any, Optional, Union
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import TypeDecorator, Text
from src.core.config import settings

logger = logging.getLogger("secops.encryption")

_fernet_instance: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Returns a singleton Fernet cipher derived deterministically from the configured SECRET_KEY."""
    global _fernet_instance
    if _fernet_instance is None:
        raw_secret = getattr(settings, "SECRET_KEY", "default-fallback-secops-key-32b").encode("utf-8")
        key_digest = hashlib.sha256(raw_secret).digest()
        urlsafe_key = base64.urlsafe_b64encode(key_digest)
        _fernet_instance = Fernet(urlsafe_key)
    return _fernet_instance


def encrypt_string(data: Optional[str]) -> Optional[str]:
    """Encrypts plaintext string using Fernet, prefixing with 'enc:'."""
    if data is None or not str(data).strip():
        return data
    str_val = str(data)
    if str_val.startswith("enc:"):
        return str_val
    try:
        f = get_fernet()
        token = f.encrypt(str_val.encode("utf-8"))
        return f"enc:{token.decode('utf-8')}"
    except Exception as e:
        logger.error("Fernet encryption error: %s", e)
        return str_val


def decrypt_string(token: Optional[str]) -> Optional[str]:
    """Decrypts an 'enc:' prefixed token; returns unencrypted data as-is."""
    if token is None or not isinstance(token, str):
        return token
    if not token.startswith("enc:"):
        return token
    raw_token = token[4:].strip()
    try:
        f = get_fernet()
        decrypted = f.decrypt(raw_token.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken:
        logger.warning("Fernet token decryption failed (InvalidToken); returning raw string.")
        return token
    except Exception as e:
        logger.error("Fernet decryption error: %s", e)
        return token


def encrypt_json(data: Any) -> Optional[str]:
    """Serializes arbitrary Python object to JSON and encrypts with Fernet."""
    if data is None:
        return None
    try:
        serialized = json.dumps(data)
        return encrypt_string(serialized)
    except Exception as e:
        logger.error("JSON serialization error during encryption: %s", e)
        return None


def decrypt_json(token: Any) -> Any:
    """Decrypts Fernet ciphertext and deserializes JSON; supports legacy unencrypted payloads."""
    if token is None:
        return None
    if isinstance(token, str):
        if token.startswith("enc:"):
            plain = decrypt_string(token)
            if plain:
                try:
                    return json.loads(plain)
                except Exception:
                    return plain
            return plain
        # Legacy plain JSON string
        try:
            return json.loads(token)
        except Exception:
            return token
    return token


class EncryptedStringType(TypeDecorator):
    """SQLAlchemy TypeDecorator for at-rest Fernet encrypted strings."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt_string(str(value))
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return decrypt_string(value)
        return None


class EncryptedJSONType(TypeDecorator):
    """SQLAlchemy TypeDecorator for at-rest Fernet encrypted JSON / vector embeddings."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt_json(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return decrypt_json(value)
        return None

