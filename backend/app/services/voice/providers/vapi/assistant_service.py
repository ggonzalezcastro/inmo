"""
Vapi.ai Assistant Service - CRUD and create-for-broker.
"""
import logging
from typing import Dict, Any, Optional

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.broker import BrokerVoiceConfigService

logger = logging.getLogger(__name__)

BASE_URL = "https://api.vapi.ai"


class VapiAssistantService:
    """Service for Vapi.ai assistant API (CRUD and create from broker config)."""

    @staticmethod
    async def create_assistant_for_broker(
        db: AsyncSession,
        broker_id: int,
        agent_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Vapi assistant using broker configuration."""
        api_key = getattr(settings, "VAPI_API_KEY", None) or None
        if not api_key:
            raise ValueError("VAPI_API_KEY not configured")

        config = await BrokerVoiceConfigService.build_assistant_config(
            db, broker_id, agent_type
        )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/assistant",
                json=config,
                headers=headers,
            ) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    logger.error("Failed to create assistant: %s", error_text)
                    raise ValueError(f"Failed to create assistant: {error_text}")
                assistant = await response.json()
                logger.info(
                    "Created Vapi assistant for broker %s: %s",
                    broker_id,
                    assistant.get("id"),
                )
                return assistant

    @staticmethod
    async def get_assistant(assistant_id: str) -> Dict[str, Any]:
        """Get assistant details from Vapi."""
        api_key = getattr(settings, "VAPI_API_KEY", None) or None
        if not api_key:
            raise ValueError("VAPI_API_KEY not configured")
        headers = {"Authorization": f"Bearer {api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/assistant/{assistant_id}",
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Failed to get assistant: {error_text}")
                return await response.json()

    @staticmethod
    async def list_assistants() -> list:
        """List all assistants from Vapi."""
        api_key = getattr(settings, "VAPI_API_KEY", None) or None
        if not api_key:
            raise ValueError("VAPI_API_KEY not configured")
        headers = {"Authorization": f"Bearer {api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/assistant",
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Failed to list assistants: {error_text}")
                return await response.json()

    @staticmethod
    async def delete_assistant(assistant_id: str) -> bool:
        """Delete an assistant from Vapi."""
        api_key = getattr(settings, "VAPI_API_KEY", None) or None
        if not api_key:
            raise ValueError("VAPI_API_KEY not configured")
        headers = {"Authorization": f"Bearer {api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{BASE_URL}/assistant/{assistant_id}",
                headers=headers,
            ) as response:
                return response.status in [200, 204]

    @staticmethod
    async def update_assistant(
        assistant_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an assistant in Vapi."""
        api_key = getattr(settings, "VAPI_API_KEY", None) or None
        if not api_key:
            raise ValueError("VAPI_API_KEY not configured")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.patch(
                f"{BASE_URL}/assistant/{assistant_id}",
                json=updates,
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Failed to update assistant: {error_text}")
                return await response.json()
