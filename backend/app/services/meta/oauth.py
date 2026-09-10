"""One-time signed OAuth state for Meta connection flows."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt

from app.core.config import settings
from app.core.redis_client import get_redis


class MetaOAuthStateError(ValueError):
    pass


class MetaOAuthStateService:
    TTL_SECONDS = 600
    KEY_PREFIX = "meta:oauth-state:"
    _ATOMIC_GETDEL_LUA = """
local value = redis.call('GET', KEYS[1])
if value then
  redis.call('DEL', KEYS[1])
end
return value
""".strip()

    @classmethod
    async def issue(
        cls,
        *,
        broker_id: int,
        user_id: int,
        channel: str,
        owner_type: str,
        redis_client=None,
    ) -> str:
        nonce = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        claims = {
            "purpose": "meta_oauth",
            "broker_id": int(broker_id),
            "user_id": int(user_id),
            "channel": channel,
            "owner_type": owner_type,
            "nonce": nonce,
            "iat": now,
            "exp": now + timedelta(seconds=cls.TTL_SECONDS),
        }
        token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        redis = redis_client or await get_redis()
        await redis.setex(
            f"{cls.KEY_PREFIX}{nonce}",
            cls.TTL_SECONDS,
            json.dumps({
                "broker_id": int(broker_id),
                "user_id": int(user_id),
                "channel": channel,
                "owner_type": owner_type,
            }),
        )
        return token

    @classmethod
    async def consume(cls, token: str, redis_client=None) -> Dict[str, Any]:
        try:
            claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError as exc:
            raise MetaOAuthStateError("OAuth state inválido o vencido") from exc
        if claims.get("purpose") != "meta_oauth" or not claims.get("nonce"):
            raise MetaOAuthStateError("OAuth state con propósito inválido")

        redis = redis_client or await get_redis()
        key = f"{cls.KEY_PREFIX}{claims['nonce']}"
        raw: Optional[str]
        getdel = getattr(redis, "getdel", None)
        if callable(getdel):
            raw = await getdel(key)
        else:
            eval_command = getattr(redis, "eval", None)
            if not callable(eval_command):
                raise MetaOAuthStateError(
                    "OAuth state no puede validarse de forma segura en este momento"
                )
            raw = await eval_command(cls._ATOMIC_GETDEL_LUA, 1, key)
        if not raw:
            raise MetaOAuthStateError("OAuth state ya fue utilizado o venció")
        stored = json.loads(raw)
        for field in ("broker_id", "user_id", "channel", "owner_type"):
            if stored.get(field) != claims.get(field):
                raise MetaOAuthStateError("OAuth state no coincide con la sesión original")
        return claims
