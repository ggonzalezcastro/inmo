from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.telegram_service import TelegramService
from app.config import settings


router = APIRouter()


class WebhookSetup(BaseModel):
    webhook_url: str


@router.post("/webhook/setup")
async def setup_webhook(
    data: WebhookSetup,
    current_user: dict = Depends(get_current_user)
):
    """Setup Telegram webhook"""
    
    telegram = TelegramService()
    
    try:
        result = await telegram.set_webhook(data.webhook_url)
        return {"status": "ok", "message": "Webhook registered", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/webhook/info")
async def get_webhook_info(
    current_user: dict = Depends(get_current_user)
):
    """Get webhook info"""
    
    telegram = TelegramService()
    
    try:
        info = await telegram.get_webhook_info()
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

