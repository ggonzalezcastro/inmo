from fastapi import APIRouter, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.tasks import telegram_tasks
import hmac
import hashlib
import json
import logging


router = APIRouter()
logger = logging.getLogger(__name__)


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
    if "message" not in update:
        return {"ok": True}
    
    message = update["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    username = message["from"].get("username", f"user_{user_id}")
    message_text = message.get("text", "")
    
    logger.info(f"Received message from {username}: {message_text}")
    
    # Enqueue Celery task (don't block)
    telegram_tasks.process_telegram_message.delay(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        message_text=message_text
    )
    
    return {"ok": True}

