"""Dedicated authenticated encryption for Meta tokens and short-lived payloads."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "meta:v1:"


class MetaEncryptionError(RuntimeError):
    """Raised when a Meta secret cannot be safely encrypted or decrypted."""


@lru_cache(maxsize=4)
def _fernet_for_secret(secret: str) -> Fernet:
    digest = hashlib.sha256(f"inmo-meta-credentials-v1:{secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encryption_secret() -> str:
    secret = settings.META_CREDENTIAL_ENCRYPTION_KEY
    if not secret and settings.ENVIRONMENT != "production":
        secret = settings.SECRET_KEY
        logger.warning(
            "META_CREDENTIAL_ENCRYPTION_KEY is unset; using SECRET_KEY in non-production"
        )
    if not secret or len(secret) < 32:
        raise MetaEncryptionError(
            "META_CREDENTIAL_ENCRYPTION_KEY must contain at least 32 characters"
        )
    return secret


def encrypt_meta_secret(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise MetaEncryptionError("Meta secret must be a non-empty string")
    token = _fernet_for_secret(_encryption_secret()).encrypt(value.encode()).decode()
    return f"{_PREFIX}{token}"


def decrypt_meta_secret(value: str) -> str:
    if not isinstance(value, str) or not value.startswith(_PREFIX):
        raise MetaEncryptionError("Meta secret is not encrypted with a supported key version")
    try:
        return _fernet_for_secret(_encryption_secret()).decrypt(
            value[len(_PREFIX):].encode()
        ).decode()
    except InvalidToken as exc:
        raise MetaEncryptionError("Meta secret could not be decrypted") from exc


def encrypt_meta_json(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return encrypt_meta_secret(serialized)


def decrypt_meta_json(ciphertext: str) -> Any:
    try:
        return json.loads(decrypt_meta_secret(ciphertext))
    except json.JSONDecodeError as exc:
        raise MetaEncryptionError("Encrypted Meta payload is not valid JSON") from exc
