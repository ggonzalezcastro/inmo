"""Backward-compatible authentication exports.

New code imports from ``app.middleware.auth``. Older integrations and tests may
still import ``app.core.auth``; exporting the same callables keeps FastAPI
dependency overrides attached to the exact same function objects.
"""

from app.middleware.auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

__all__ = [
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "hash_password",
    "verify_password",
]
