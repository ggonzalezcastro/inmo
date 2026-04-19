from fastapi import APIRouter, HTTPException, Request, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.tasks import telegram_tasks
from app.services.chat import ChatService
import hmac
import hashlib
import json
import logging


router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# G6 + G12: Webhook deduplication & per-sender rate limiting helpers
# ---------------------------------------------------------------------------
_DEDUP_TTL_SECONDS = 300       # 5 min — covers Meta/Telegram retry windows
_RATE_LIMIT_WINDOW = 10        # seconds
_RATE_LIMIT_MAX_MSGS = 5       # max messages per sender per window


async def _is_duplicate_webhook(provider: str, message_id: str) -> bool:
    """Return True if this webhook was already processed (Redis SET NX)."""
    if not message_id:
        return False
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        key = f"webhook_dedup:{provider}:{message_id}"
        was_set = await redis.set(key, "1", nx=True, ex=_DEDUP_TTL_SECONDS)
        return not was_set  # None means key already existed → duplicate
    except Exception as exc:
        logger.debug("Dedup check unavailable (allowing): %s", exc)
        return False


async def _is_rate_limited(provider: str, sender_id: str) -> bool:
    """Return True if sender exceeded per-sender rate limit (Redis INCR)."""
    if not sender_id:
        return False
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        key = f"webhook_rate:{provider}:{sender_id}"
        # Use a Lua script to atomically INCR + set TTL only on first create,
        # avoiding the race where key expires between INCR and EXPIRE.
        _lua = """
            local c = redis.call('INCR', KEYS[1])
            if c == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
            return c
        """
        count = await redis.eval(_lua, 1, key, _RATE_LIMIT_WINDOW)
        if count > _RATE_LIMIT_MAX_MSGS:
            logger.warning("Rate limit exceeded for %s:%s (%d/%d)", provider, sender_id, count, _RATE_LIMIT_MAX_MSGS)
            return True
        return False
    except Exception as exc:
        logger.debug("Rate limit check unavailable (allowing): %s", exc)
        return False


async def _clear_dedup_key(provider: str, message_id: str) -> None:
    """Remove a dedup key so provider retries can succeed after a failure."""
    if not message_id:
        return
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        await redis.delete(f"webhook_dedup:{provider}:{message_id}")
    except Exception:
        pass


def verify_webhook_signature(
    body: bytes,
    secret_token: str,
    x_telegram_bot_api_secret_hash: str
) -> bool:
    """Verify Telegram webhook signature"""
    calculated_hash = hmac.new(
        secret_token.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(
        calculated_hash,
        x_telegram_bot_api_secret_hash
    )


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_hash: str = Header(None)
):
    """Telegram webhook endpoint"""
    
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature
    from app.config import settings
    if not verify_webhook_signature(
        body,
        settings.TELEGRAM_WEBHOOK_SECRET,
        x_telegram_bot_api_secret_hash or ""
    ):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Parse update
    update = await request.json()
    
    # Extract message info
    # G11: Handle edited_message updates gracefully; log and skip unknown types.
    if "message" not in update:
        if "edited_message" in update:
            message = update["edited_message"]
        else:
            _unknown_keys = [k for k in update if k != "update_id"]
            logger.info("Telegram webhook: ignoring unsupported update type(s): %s", _unknown_keys)
            return {"ok": True}
    else:
        message = update["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    username = message["from"].get("username", f"user_{user_id}")
    message_text = message.get("text", "")
    tg_message_id = str(message.get("message_id", ""))
    # Dedup key includes chat_id (message_id is only unique within a chat)
    # and update type so edited_message retries are handled separately.
    _update_type = "edited" if "edited_message" in update else "msg"
    _tg_dedup_id = f"{chat_id}:{tg_message_id}:{_update_type}" if tg_message_id else ""

    # G6: Deduplicate — Telegram may retry the webhook on timeout.
    if await _is_duplicate_webhook("telegram", _tg_dedup_id):
        logger.info("Telegram webhook: duplicate message_id=%s ignored", _tg_dedup_id)
        return {"ok": True}

    # G12: Per-sender rate limiting (max 5 msgs / 10 s).
    if await _is_rate_limited("telegram", str(user_id)):
        return {"ok": True}

    logger.info(f"Received message from {username}: {message_text}")
    
    # Enqueue Celery task (don't block).
    # If enqueue fails, remove the dedup key so the provider retry succeeds.
    try:
        telegram_tasks.process_telegram_message.delay(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            message_text=message_text
        )
    except Exception as _enq_exc:
        logger.error("Telegram task enqueue failed: %s", _enq_exc)
        await _clear_dedup_key("telegram", _tg_dedup_id)
    
    return {"ok": True}


@router.post("/chat/{broker_id}/{provider_name}")
async def chat_webhook(
    broker_id: int,
    provider_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    """
    Unified chat webhook: POST /webhooks/{broker_id}/{provider_name}.
    Supports telegram, whatsapp, etc. Verifies signature when available and processes via ChatService.
    """
    body = await request.body()
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        payload = {}

    # G10: Inject raw body bytes so the WhatsApp provider can use the original
    # bytes for HMAC verification instead of re-serializing the parsed dict.
    if provider_name.lower() == "whatsapp" and body:
        payload["__raw_body__"] = body

    # Provider-specific signature header
    signature = None
    if provider_name.lower() == "whatsapp":
        signature = x_hub_signature_256
    elif provider_name.lower() == "telegram":
        signature = x_telegram_bot_api_secret_token

    # Verify signature FIRST — before any Redis writes (dedup/rate-limit) so
    # an attacker cannot poison Redis keys with forged requests.
    chat_message = await ChatService.handle_webhook(
        db=db,
        broker_id=broker_id,
        provider_name=provider_name.lower().strip(),
        payload=payload,
        signature=signature or "",
        # G6 + G12: pass helpers so handle_webhook can dedup/rate-limit AFTER
        # signature verification but BEFORE processing.
        dedup_fn=_is_duplicate_webhook,
        rate_limit_fn=_is_rate_limited,
    )
    if not chat_message:
        return {"ok": True}

    try:
        logger.info("Chat webhook processed lead_id=%s provider=%s", chat_message.lead_id, provider_name)
    except Exception as e:
        logger.warning("Chat webhook post-process: %s", e)

    return {"ok": True}

