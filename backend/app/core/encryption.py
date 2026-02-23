"""
At-rest encryption for sensitive lead_metadata fields.

Uses Fernet (AES-128-CBC + HMAC-SHA256) with a 32-byte key derived from
SECRET_KEY via PBKDF2-HMAC-SHA256.  All encryption is transparent: the
service layer calls encrypt_metadata_fields() before writing to the DB and
decrypt_metadata_fields() after reading.

Sensitive fields (SENSITIVE_FIELDS) are stored as base64-encoded Fernet tokens.
A field is recognized as encrypted when its value starts with the prefix "enc:".

If SECRET_KEY is not set, fields are stored in plain text with a warning.

Usage:
    from app.core.encryption import encrypt_metadata_fields, decrypt_metadata_fields

    # Before DB write:
    safe_meta = encrypt_metadata_fields(raw_metadata)
    lead.lead_metadata = safe_meta

    # After DB read:
    decrypted = decrypt_metadata_fields(lead.lead_metadata)
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

# Fields in lead_metadata that must be encrypted at rest
SENSITIVE_FIELDS: Set[str] = {
    "salary",
    "monthly_income",
    "morosidad_amount",
    "dicom_status",
}

_ENCRYPTED_PREFIX = "enc:"
_fernet_instance = None


def _get_fernet():
    """
    Return a Fernet instance derived from SECRET_KEY (lazy singleton).
    Returns None if SECRET_KEY is empty (plain-text fallback).
    """
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend

        secret_key = os.getenv("SECRET_KEY", "")
        if not secret_key or len(secret_key) < 16:
            logger.warning(
                "[Encryption] SECRET_KEY is empty or too short — "
                "sensitive fields will NOT be encrypted"
            )
            return None

        # Derive a 32-byte Fernet key from SECRET_KEY
        salt = b"inmo-lead-agent-v1"  # fixed salt — key is secret
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend(),
        )
        key_bytes = kdf.derive(secret_key.encode())
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        _fernet_instance = Fernet(fernet_key)
        return _fernet_instance

    except Exception as exc:
        logger.warning("[Encryption] Fernet init failed: %s — encryption disabled", exc)
        return None


# ── Field-level helpers ───────────────────────────────────────────────────────

def encrypt_value(value: Any) -> str:
    """
    Encrypt a single value.  Returns "enc:<base64-fernet-token>" on success,
    or the original value as a string if encryption is unavailable.
    """
    fernet = _get_fernet()
    if fernet is None:
        return str(value)

    try:
        plain = str(value).encode()
        token = fernet.encrypt(plain).decode()
        return f"{_ENCRYPTED_PREFIX}{token}"
    except Exception as exc:
        logger.warning("[Encryption] encrypt_value failed: %s", exc)
        return str(value)


def decrypt_value(encrypted: str) -> str:
    """
    Decrypt a value previously encrypted with encrypt_value.
    Returns the original string, or the input unchanged if not encrypted / error.
    """
    if not isinstance(encrypted, str) or not encrypted.startswith(_ENCRYPTED_PREFIX):
        return encrypted  # plain-text or non-string

    fernet = _get_fernet()
    if fernet is None:
        # Return without prefix — best-effort
        return encrypted[len(_ENCRYPTED_PREFIX):]

    try:
        token = encrypted[len(_ENCRYPTED_PREFIX):].encode()
        return fernet.decrypt(token).decode()
    except Exception as exc:
        logger.warning("[Encryption] decrypt_value failed: %s", exc)
        return encrypted  # return as-is rather than crash


# ── Metadata dict helpers ─────────────────────────────────────────────────────

def encrypt_metadata_fields(
    metadata: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Return a copy of the metadata dict with SENSITIVE_FIELDS encrypted.
    Non-sensitive fields and already-encrypted values are left untouched.
    """
    if not isinstance(metadata, dict):
        return metadata

    result = dict(metadata)
    for field in SENSITIVE_FIELDS:
        value = result.get(field)
        if value is None:
            continue
        # Don't double-encrypt
        if isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX):
            continue
        result[field] = encrypt_value(value)

    return result


def decrypt_metadata_fields(
    metadata: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Return a copy of the metadata dict with SENSITIVE_FIELDS decrypted.
    Fields that are not encrypted are returned unchanged.
    """
    if not isinstance(metadata, dict):
        return metadata

    result = dict(metadata)
    for field in SENSITIVE_FIELDS:
        value = result.get(field)
        if value is None:
            continue
        if isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX):
            result[field] = decrypt_value(value)

    return result
