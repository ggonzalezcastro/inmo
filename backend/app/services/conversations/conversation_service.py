"""
ConversationService — manages the lifecycle of Conversation records.

Each chat session between a lead and the CRM is tracked as a Conversation.
One lead can have multiple conversations (one per channel, or after re-opening).

Responsibilities:
  - Auto-create a Conversation on the first message from a lead
  - Update last_message_at and message_count on each message
  - Maintain a compact context_summary JSON for token-efficient agent context
  - Link ChatMessages to their Conversation
  - Close/archive conversations when appropriate
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.chat_message import ChatMessage

logger = logging.getLogger(__name__)


class ConversationService:
    """Manages Conversation lifecycle."""

    @staticmethod
    async def get_or_create(
        db: AsyncSession,
        lead_id: int,
        broker_id: int,
        channel: str,
    ) -> Conversation:
        """
        Return the active conversation for this lead+channel, creating one if needed.
        """
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.lead_id == lead_id,
                Conversation.broker_id == broker_id,
                Conversation.channel == channel,
                Conversation.status.in_(["active", "human_mode"]),
            )
            .order_by(Conversation.started_at.desc())
            .limit(1)
        )
        conv = result.scalar_one_or_none()

        if conv is None:
            conv = Conversation(
                lead_id=lead_id,
                broker_id=broker_id,
                channel=channel,
                status="active",
                started_at=datetime.now(timezone.utc),
            )
            db.add(conv)
            await db.flush()  # get the ID without committing
            logger.info(
                "Created new conversation %d for lead %d channel=%s",
                conv.id, lead_id, channel,
            )

        return conv

    @staticmethod
    async def on_message(
        db: AsyncSession,
        conversation_id: int,
        message_id: Optional[int] = None,
    ) -> None:
        """Update conversation stats after a new message is processed."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return

        conv.last_message_at = now
        conv.message_count = (conv.message_count or 0) + 1
        db.add(conv)

    @staticmethod
    async def update_context_summary(
        db: AsyncSession,
        conversation_id: int,
        lead_data: Dict[str, Any],
        current_agent: Optional[str],
        missing_fields: list,
    ) -> None:
        """
        Update the compact context_summary after an agent turn.

        This summary is used for token-efficient context passing
        (~200-500 tokens vs 5K-20K from full history).
        """
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return

        existing = conv.context_summary or {}
        collected = {
            k: lead_data.get(k)
            for k in ["name", "phone", "email", "salary", "budget", "location", "dicom_status"]
            if lead_data.get(k)
        }
        conv.context_summary = {
            **existing,
            "collected_fields": collected,
            "missing_fields": missing_fields,
            "interests": lead_data.get("interests", existing.get("interests", [])),
            "budget_uf": lead_data.get("budget"),
            "property_preferences": lead_data.get("property_preferences", {}),
            "last_agent": current_agent,
            "last_agent_note": lead_data.get("last_agent_note"),
            "human_release_note": lead_data.get("human_release_note"),
        }
        db.add(conv)

    @staticmethod
    async def set_human_mode(
        db: AsyncSession,
        conversation_id: int,
        human_mode: bool,
        assigned_to: Optional[int] = None,
    ) -> None:
        """Sync human_mode state on the Conversation record."""
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return

        conv.human_mode = human_mode
        conv.status = "human_mode" if human_mode else "active"
        now = datetime.now(timezone.utc)

        if human_mode:
            conv.human_assigned_to = assigned_to
            conv.human_taken_at = now
        else:
            conv.human_assigned_to = None
            conv.human_released_at = now

        db.add(conv)

    @staticmethod
    async def update_agent_state(
        db: AsyncSession,
        conversation_id: int,
        current_agent: Optional[str],
        conversation_state: Optional[str],
    ) -> None:
        """Persist routing state to the Conversation after an agent turn."""
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return

        if current_agent is not None:
            conv.current_agent = current_agent
        if conversation_state is not None:
            conv.conversation_state = conversation_state
        db.add(conv)

    @staticmethod
    async def close(
        db: AsyncSession,
        conversation_id: int,
        reason: str = "completed",
    ) -> None:
        """Mark a conversation as closed."""
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return

        conv.status = "closed"
        conv.close_reason = reason
        conv.closed_at = datetime.now(timezone.utc)
        db.add(conv)

    @staticmethod
    async def link_message(
        db: AsyncSession,
        message_id: int,
        conversation_id: int,
    ) -> None:
        """Link a ChatMessage to a Conversation."""
        result = await db.execute(
            select(ChatMessage).where(ChatMessage.id == message_id)
        )
        msg = result.scalar_one_or_none()
        if msg is None:
            return
        if msg.conversation_id is None:
            msg.conversation_id = conversation_id
            db.add(msg)
