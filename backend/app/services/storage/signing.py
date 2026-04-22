import base64
import hashlib
import hmac
import json
import time

from app.core.config import settings


def _get_secret() -> bytes:
    secret = settings.STORAGE_SIGNING_SECRET or settings.SECRET_KEY
    return secret.encode()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    # Restore padding
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def sign_download_token(key: str, broker_id: int, ttl: int | None = None) -> str:
    """Return a URL-safe token encoding {key, broker_id, exp}."""
    if ttl is None:
        ttl = settings.STORAGE_PRESIGN_TTL_SEC

    payload = json.dumps({"k": key, "b": broker_id, "e": int(time.time()) + ttl}).encode()
    sig = hmac.new(_get_secret(), payload, hashlib.sha256).digest()

    return _b64url_encode(payload) + "." + _b64url_encode(sig)


def verify_download_token(token: str) -> dict:
    """Return {'key': ..., 'broker_id': ...} or raise ValueError if invalid/expired."""
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        raise ValueError("Malformed token")

    payload_bytes = _b64url_decode(payload_b64)
    expected_sig = hmac.new(_get_secret(), payload_bytes, hashlib.sha256).digest()
    provided_sig = _b64url_decode(sig_b64)

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise ValueError("Invalid token signature")

    try:
        data = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise ValueError("Malformed token payload")

    if int(time.time()) > data["e"]:
        raise ValueError("Token expired")

    return {"key": data["k"], "broker_id": data["b"]}
