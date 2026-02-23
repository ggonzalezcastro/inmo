from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import Optional, List, Dict
import logging

from app.models.lead import Lead
from app.models.telegram_message import TelegramMessage
from app.models.chat_message import ChatMessage
from app.core.cache import cache_get_json, cache_set_json

LEAD_CONTEXT_CACHE_PREFIX = "lead_context:"
LEAD_CONTEXT_CACHE_TTL = 300  # 5 minutes
logger = logging.getLogger(__name__)


class LeadContextService:
    """Service for building lead context for LLM"""

    @staticmethod
    async def get_or_create_lead(
        db: AsyncSession,
        telegram_user_id: int,
        username: str
    ) -> Lead:
        """Get or create lead by Telegram ID"""

        # Try to find by telegram_user_id in metadata
        # Using JSONB cast for PostgreSQL
        from sqlalchemy import cast, String
        from sqlalchemy.dialects.postgresql import JSONB

        result = await db.execute(
            select(Lead).where(
                cast(Lead.lead_metadata, JSONB)['telegram_user_id'].astext == str(telegram_user_id)
            )
        )
        lead = result.scalars().first()

        if lead:
            return lead

        # Create new lead with telegram ID as phone
        from app.models.lead import LeadStatus
        new_lead = Lead(
            phone=f"telegram_{telegram_user_id}",
            name=username,
            lead_metadata={"telegram_user_id": telegram_user_id, "username": username},
            status=LeadStatus.COLD,
            lead_score=0.0
        )

        db.add(new_lead)
        await db.commit()
        await db.refresh(new_lead)

        return new_lead

    @staticmethod
    async def get_lead_context(db: AsyncSession, lead_id: int) -> Dict:
        """Get lead context for LLM prompt. Uses Redis cache (TTL 5 min)."""
        cache_key = f"{LEAD_CONTEXT_CACHE_PREFIX}{lead_id}"
        cached = await cache_get_json(cache_key)
        if cached is not None:
            logger.debug("Lead context cache HIT for lead_id=%s", lead_id)
            return cached

        # Get lead
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalars().first()

        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        # Get last 20 messages from chat_messages (new unified table) + telegram_messages (legacy)
        chat_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.lead_id == lead_id)
            .order_by(ChatMessage.created_at)
            .limit(20)
        )
        chat_msgs = chat_result.scalars().all()

        tg_result = await db.execute(
            select(TelegramMessage)
            .where(TelegramMessage.lead_id == lead_id)
            .order_by(TelegramMessage.created_at)
            .limit(20)
        )
        tg_msgs = tg_result.scalars().all()

        # Merge both sources, sorted by created_at, take last 20
        all_msgs = sorted(
            [(m.created_at, m.direction.value if hasattr(m.direction, 'value') else m.direction, m.message_text) for m in chat_msgs] +
            [(m.created_at, m.direction.value if hasattr(m.direction, 'value') else m.direction, m.message_text) for m in tg_msgs],
            key=lambda x: x[0]
        )[-20:]

        message_history = []
        for _, direction, text in all_msgs:
            role = "user" if direction == "in" else "assistant"
            message_history.append({"role": role, "content": text})

        legacy_message_history = []
        for _, direction, text in reversed(all_msgs[-10:]):
            d = "U" if direction == "in" else "B"
            clean_text = text.replace("|", "‖").replace("\n", " ")
            legacy_message_history.append(f"{d}:{clean_text}")

        # Get phone, handling different formats
        phone_number = lead.phone if lead.phone and not lead.phone.startswith("web_chat_") and not lead.phone.startswith("whatsapp_") and not lead.phone.startswith("+569999") else None

        # Decrypt sensitive fields before using metadata
        from app.core.encryption import decrypt_metadata_fields
        raw_metadata = lead.lead_metadata or {}
        metadata = decrypt_metadata_fields(raw_metadata) if isinstance(raw_metadata, dict) else raw_metadata

        # Convert metadata to TOON format if it's a dict
        if isinstance(metadata, dict):
            # Format: key:value|key:value (compact)
            metadata_toon = "|".join([f"{k}:{v}" for k, v in metadata.items() if v])
        else:
            metadata_toon = str(metadata)

        # ── Context window compression (TASK-008) ────────────────────────────
        existing_summary = metadata.get("conversation_summary") if isinstance(metadata, dict) else None
        from app.services.chat.context_manager import compress_context
        conversation_summary, message_history = await compress_context(
            message_history,
            existing_summary=existing_summary,
            lead_id=lead.id,
            db=db,
        )

        context = {
            "lead_id": lead.id,
            "name": lead.name or "User",
            "phone": phone_number,
            "email": lead.email if lead.email else None,
            "status": lead.status,
            "score": lead.lead_score,
            "metadata": metadata,  # Keep as dict for internal use
            "metadata_toon": metadata_toon,  # TOON format for display
            "message_history": message_history,  # Structured array format (compressed if needed)
            "message_history_legacy": "|".join(legacy_message_history),  # Legacy format for backward compatibility
            "conversation_summary": conversation_summary,  # TASK-009: session recovery
        }
        await cache_set_json(cache_key, context, LEAD_CONTEXT_CACHE_TTL)
        return context
