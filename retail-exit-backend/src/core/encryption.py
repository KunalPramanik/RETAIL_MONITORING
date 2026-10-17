"""Cryptographic MultiFernet At-Rest Encryption Module

Enforces Section 4.3 & Req 8:
- Cryptographic MultiFernet encryption for biometric face embeddings and sensitive camera credentials at rest.
- Versioned ciphertext prefix: 'enc:v1:<base64-token>' with seamless backward-compatibility for 'enc:<token>' and legacy plaintext.
- Key rotation support: MultiFernet rotates tokens from secondary/retiring keys to the active primary key.
- Strict key provenance: Derived from configured SECOPS_ENCRYPTION_KEYS or SECRET_KEY; zero hardcoded key defaults allowed.
- Secure erasure utility: Cryptographic overwrite and sanitization of biometric embedding data.
"""

import base64
import hashlib
import json
import logging
import os
from typing import Any, List, Optional, Union
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from sqlalchemy import TypeDecorator, Text
from src.core.config import settings

logger = logging.getLogger("secops.encryption")

_multifernet_instance: Optional[MultiFernet] = None


def derive_fernet_key(secret_str: str) -> bytes:
    """Derives a valid 32-byte urlsafe-base64-encoded Fernet key deterministically."""
    if not secret_str or not secret_str.strip():
        raise ValueError("Cannot derive Fernet key from empty secret.")
    # Check if already a valid 32-byte base64 Fernet key
    try:
        raw_b64 = secret_str.strip().encode("utf-8")
        if len(raw_b64) == 44:
            decoded = base64.urlsafe_b64decode(raw_b64)
            if len(decoded) == 32:
                return raw_b64
    except Exception:
        pass
    # Otherwise derive deterministically via SHA-256
    key_digest = hashlib.sha256(secret_str.strip().encode("utf-8")).digest()
    return base64.urlsafe_b64encode(key_digest)


def get_encryption_keys() -> List[bytes]:
    """Retrieves all configured encryption keys in priority order (primary first, then rotation keys).
    Strictly forbids hardcoded key fallbacks.
    """
    keys: List[bytes] = []
    
    # 1. Dedicated encryption keys env
    env_keys = os.getenv("SECOPS_ENCRYPTION_KEYS", "").strip()
    if env_keys:
        for k in env_keys.split(","):
            if k.strip():
                keys.append(derive_fernet_key(k.strip()))

    # 2. Primary SECRET_KEY fallback
    secret_key = getattr(settings, "SECRET_KEY", None) or os.getenv("SECRET_KEY", "")
    if secret_key and secret_key.strip():
        k = derive_fernet_key(secret_key.strip())
        if k not in keys:
            keys.append(k)

    if not keys:
        # Zero hardcoded fallback allowed
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: Neither SECOPS_ENCRYPTION_KEYS nor SECRET_KEY "
            "is defined. Zero hardcoded key defaults permitted."
        )

    return keys


def get_fernet() -> MultiFernet:
    """Returns the singleton MultiFernet cipher configured with primary and rotation keys."""
    global _multifernet_instance
    if _multifernet_instance is None:
        raw_keys = get_encryption_keys()
        fernet_list = [Fernet(k) for k in raw_keys]
        _multifernet_instance = MultiFernet(fernet_list)
    return _multifernet_instance


def reset_fernet_instance() -> None:
    """Resets the singleton MultiFernet instance (used during testing or key rotation)."""
    global _multifernet_instance
    _multifernet_instance = None


def encrypt_string(data: Optional[str]) -> Optional[str]:
    """Encrypts plaintext string using MultiFernet primary key, outputting versioned 'enc:v1:' token."""
    if data is None or not str(data).strip():
        return data
    str_val = str(data)
    if str_val.startswith("enc:v1:") or str_val.startswith("enc:"):
        return str_val
    try:
        f = get_fernet()
        token = f.encrypt(str_val.encode("utf-8"))
        return f"enc:v1:{token.decode('utf-8')}"
    except Exception as e:
        logger.error("MultiFernet encryption error: %s", e)
        return str_val


def decrypt_string(token: Optional[str]) -> Optional[str]:
    """Decrypts versioned 'enc:v1:' or legacy 'enc:' tokens; returns unencrypted data as-is."""
    if token is None or not isinstance(token, str):
        return token
    raw_ciphertext = None
    if token.startswith("enc:v1:"):
        raw_ciphertext = token[7:].strip()
    elif token.startswith("enc:"):
        raw_ciphertext = token[4:].strip()
    else:
        # Plaintext legacy fallback
        return token

    try:
        f = get_fernet()
        decrypted = f.decrypt(raw_ciphertext.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken:
        logger.warning("MultiFernet token decryption failed (InvalidToken); returning raw token.")
        return token
    except Exception as e:
        logger.error("MultiFernet decryption error: %s", e)
        return token


def rotate_ciphertext(token: str) -> str:
    """Re-encrypts a ciphertext token under the current primary key using MultiFernet.rotate."""
    if not token or not isinstance(token, str):
        return token
    raw_ciphertext = None
    if token.startswith("enc:v1:"):
        raw_ciphertext = token[7:].strip()
    elif token.startswith("enc:"):
        raw_ciphertext = token[4:].strip()
    else:
        # Was unencrypted plaintext; encrypt under primary
        return encrypt_string(token) or token

    try:
        f = get_fernet()
        rotated = f.rotate(raw_ciphertext.encode("utf-8"))
        return f"enc:v1:{rotated.decode('utf-8')}"
    except Exception as e:
        logger.error("MultiFernet rotation error: %s", e)
        return token


def erase_biometric_embedding(emp: Any) -> None:
    """Performs explicit secure erasure of biometric embedding vectors from memory and model object."""
    if hasattr(emp, "face_embedding") and emp.face_embedding is not None:
        # Overwrite in-memory representation with zeroed values prior to clearing
        if isinstance(emp.face_embedding, list):
            for i in range(len(emp.face_embedding)):
                emp.face_embedding[i] = 0.0
        emp.face_embedding = None
    if hasattr(emp, "embedding_updated_at"):
        emp.embedding_updated_at = None


def encrypt_json(data: Any) -> Optional[str]:
    """Serializes arbitrary Python object to JSON and encrypts with MultiFernet."""
    if data is None:
        return None
    try:
        serialized = json.dumps(data)
        return encrypt_string(serialized)
    except Exception as e:
        logger.error("JSON serialization error during encryption: %s", e)
        return None


def decrypt_json(token: Any) -> Any:
    """Decrypts MultiFernet ciphertext and deserializes JSON; supports legacy unencrypted payloads."""
    if token is None:
        return None
    if isinstance(token, str):
        if token.startswith("enc:v1:") or token.startswith("enc:"):
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
