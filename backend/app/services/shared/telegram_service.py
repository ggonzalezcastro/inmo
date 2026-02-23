import httpx
import logging
from typing import Optional, Dict, Any
from app.config import settings
from app.core.circuit_breakers import telegram_breaker


logger = logging.getLogger(__name__)


class TelegramService:
    """Service for interacting with Telegram Bot API"""
    
    BASE_URL = "https://api.telegram.org"
    
    def __init__(self, token: str = settings.TELEGRAM_TOKEN):
        self.token = token
        self.api_url = f"{self.BASE_URL}/bot{token}"
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """Send message to user (protected by telegram_breaker)."""
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}

        async def _call():
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    logger.error(f"Failed to send message: {response.text}")
                    raise Exception(f"Telegram API error: {response.text}")
                return response.json()

        return await telegram_breaker.call_async(_call)

    async def get_chat(self, chat_id: int) -> Dict[str, Any]:
        """Get chat info (protected by telegram_breaker)."""
        url = f"{self.api_url}/getChat"

        async def _call():
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"chat_id": chat_id})
                if response.status_code != 200:
                    raise Exception(f"Failed to get chat: {response.text}")
                return response.json()

        return await telegram_breaker.call_async(_call)
    
    async def set_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """Register webhook with Telegram"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/setWebhook",
                json={
                    "url": webhook_url,
                    "secret_token": settings.TELEGRAM_WEBHOOK_SECRET
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to set webhook: {response.text}")
                raise Exception(f"Telegram API error: {response.text}")
            
            logger.info(f"Webhook registered: {webhook_url}")
            return response.json()
    
    async def delete_webhook(self) -> Dict[str, Any]:
        """Delete webhook"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/deleteWebhook"
            )
            
            return response.json()
    
    async def get_webhook_info(self) -> Dict[str, Any]:
        """Get webhook info"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/getWebhookInfo"
            )
            
            return response.json()
