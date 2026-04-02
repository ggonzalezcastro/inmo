"""
Conversations routes — human takeover + inbox for human agents.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import logging

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.lead import Lead
from app.models.chat_message import ChatMessage, ChatProvider, MessageDirection, MessageStatus
from app.services.chat.service import ChatService

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class HumanMessageInput(BaseModel):
    text: str


class ConversationLeadItem(BaseModel):
    id: int
    name: Optional[str]
    phone: str
    pipeline_stage: Optional[str]
    status: Optional[str]
    human_mode: bool
    human_assigned_to: Optional[int]
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    last_message_direction: Optional[str]
    channel: Optional[str]
    unread_count: int


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_lead_channel(db: AsyncSession, lead_id: int):
    """Get most recent inbound channel provider + channel_user_id for lead."""
    result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.lead_id == lead_id,
            ChatMessage.direction == MessageDirection.INBOUND,
        )
        .order_by(desc(ChatMessage.id))
        .limit(1)
    )
    msg = result.scalar_one_or_none()
    if msg:
        return str(msg.provider.value if hasattr(msg.provider, "value") else msg.provider), msg.channel_user_id
    return None, None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=List[ConversationLeadItem])
async def list_conversations(
    mode: Optional[str] = None,  # "human" | "ai" | None = all
    search: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List leads with last message info for the conversations inbox."""
    broker_id = current_user.get("broker_id")
    current_user_id = current_user.get("user_id") or current_user.get("id")
    if current_user_id:
        try:
            current_user_id = int(current_user_id)
        except (TypeError, ValueError):
            pass

    # Get all leads for broker
    query = select(Lead).where(Lead.broker_id == broker_id).order_by(desc(Lead.updated_at)).limit(limit)
    result = await db.execute(query)
    leads = result.scalars().all()

    items: List[ConversationLeadItem] = []
    for lead in leads:
        meta = lead.lead_metadata or {}
        is_human = bool(meta.get("human_mode"))
        assigned_to = meta.get("human_assigned_to")

        # Visibility rule:
        # - AI-managed leads (human_mode=False) → visible to everyone
        # - Human-taken leads → only visible to the agent who took them
        if is_human and assigned_to != current_user_id:
            continue

        # Filter by mode
        if mode == "human" and not is_human:
            continue
        if mode == "ai" and is_human:
            continue

        name = meta.get("nombre") or meta.get("name")
        if search:
            haystack = f"{name or ''} {lead.phone}".lower()
            if search.lower() not in haystack:
                continue

        # Get last message
        msg_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.lead_id == lead.id)
            .order_by(desc(ChatMessage.id))
            .limit(1)
        )
        last_msg = msg_result.scalar_one_or_none()

        # Count unread (inbound messages after last outbound)
        unread = 0
        if last_msg and last_msg.direction == MessageDirection.INBOUND:
            last_out_result = await db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.lead_id == lead.id,
                    ChatMessage.direction == MessageDirection.OUTBOUND,
                )
                .order_by(desc(ChatMessage.id))
                .limit(1)
            )
            last_out = last_out_result.scalar_one_or_none()
            after_id = last_out.id if last_out else 0
            count_result = await db.execute(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.lead_id == lead.id,
                    ChatMessage.direction == MessageDirection.INBOUND,
                    ChatMessage.id > after_id,
                )
            )
            unread = count_result.scalar() or 0

        provider_val = None
        if last_msg:
            p = last_msg.provider
            provider_val = p.value if hasattr(p, "value") else str(p)

        items.append(ConversationLeadItem(
            id=lead.id,
            name=name,
            phone=lead.phone,
            pipeline_stage=lead.pipeline_stage,
            status=lead.status.value if lead.status and hasattr(lead.status, "value") else str(lead.status) if lead.status else None,
            human_mode=is_human,
            human_assigned_to=meta.get("human_assigned_to"),
            last_message=last_msg.message_text if last_msg else None,
            last_message_at=last_msg.created_at if last_msg else None,
            last_message_direction=last_msg.direction.value if last_msg and hasattr(last_msg.direction, "value") else None,
            channel=provider_val,
            unread_count=unread,
        ))

    return items


@router.post("/leads/{lead_id}/takeover")
async def takeover_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Human agent takes control of a lead — silences the AI."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.broker_id == current_user.get("broker_id"))
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    meta = dict(lead.lead_metadata or {})
    meta["human_mode"] = True
    raw_uid = current_user.get("user_id") or current_user.get("id")
    try:
        uid = int(raw_uid) if raw_uid is not None else None
    except (TypeError, ValueError):
        uid = raw_uid
    meta["human_assigned_to"] = uid
    meta["human_taken_at"] = datetime.now(timezone.utc).isoformat()
    lead.lead_metadata = meta
    await db.commit()

    # Broadcast to broker so kanban refreshes
    try:
        from app.core.websocket_manager import ws_manager
        await ws_manager.broadcast(current_user.get("broker_id"), "human_mode_changed", {
            "lead_id": lead_id,
            "human_mode": True,
            "taken_by": current_user.get("user_id") or current_user.get("id"),
        })
    except Exception:
        pass

    return {"ok": True, "human_mode": True}


@router.post("/leads/{lead_id}/release")
async def release_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Human agent releases control — AI resumes."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.broker_id == current_user.get("broker_id"))
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    meta = dict(lead.lead_metadata or {})
    meta["human_mode"] = False
    meta.pop("human_assigned_to", None)
    meta.pop("human_taken_at", None)
    meta.pop("human_mode_notified", None)  # Reset so handoff message fires again if re-escalated
    # Reset frustration score so Sofía resumes without the old escalation state
    if "sentiment" in meta:
        from app.services.sentiment.scorer import empty_sentiment
        meta["sentiment"] = empty_sentiment()
    lead.lead_metadata = meta
    await db.commit()

    try:
        from app.core.websocket_manager import ws_manager
        await ws_manager.broadcast(current_user.get("broker_id"), "human_mode_changed", {
            "lead_id": lead_id,
            "human_mode": False,
        })
    except Exception:
        pass

    return {"ok": True, "human_mode": False}


@router.post("/leads/{lead_id}/human-message")
async def send_human_message(
    lead_id: int,
    body: HumanMessageInput,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Human agent sends a message to the lead via their original channel."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.broker_id == current_user.get("broker_id"))
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    meta = lead.lead_metadata or {}
    if not meta.get("human_mode"):
        raise HTTPException(status_code=400, detail="Lead is not in human mode")

    provider_name, channel_user_id = await _get_lead_channel(db, lead_id)

    if not provider_name or provider_name in ("webchat", "ChatProvider.WEBCHAT") or channel_user_id == "0":
        # No real channel — just log the message without sending
        provider_name = "webchat"
        channel_user_id = "0"
        send_result = None
    elif provider_name == "whatsapp":
        # Use the global WhatsAppService (same credentials used by the AI reply path)
        from app.services.chat.whatsapp_service import WhatsAppService
        wa = WhatsAppService()
        try:
            await wa.send_text_message(channel_user_id, body.text)
            send_result = type("R", (), {"success": True, "error": None})()
        except Exception as exc:
            logger.warning("Failed to send WhatsApp human message: %s", exc)
            send_result = type("R", (), {"success": False, "error": str(exc)})()
    else:
        send_result = await ChatService.send_message(
            db=db,
            broker_id=current_user.get("broker_id"),
            provider_name=provider_name,
            channel_user_id=channel_user_id,
            message_text=body.text,
            lead_id=lead_id,
        )
        if not send_result.success:
            logger.warning("Failed to send human message: %s", send_result.error)

    # Always log the message to DB (even if send failed — agent wants the record)
    msg = ChatMessage(
        lead_id=lead_id,
        broker_id=current_user.get("broker_id"),
        provider=provider_name if not hasattr(ChatProvider, provider_name.upper()) else getattr(ChatProvider, provider_name.upper()),
        channel_user_id=channel_user_id or "0",
        message_text=body.text,
        direction=MessageDirection.OUTBOUND,
        status=MessageStatus.SENT,
        ai_response_used=False,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Broadcast to broker so chat panels update
    try:
        from app.core.websocket_manager import ws_manager
        await ws_manager.broadcast(current_user.get("broker_id"), "new_message", {
            "lead_id": lead_id,
            "message": body.text,
            "direction": "out",
            "human": True,
            "sent_by": current_user.get("user_id") or current_user.get("id"),
        })
    except Exception:
        pass

    return {"ok": True, "message_id": msg.id}
