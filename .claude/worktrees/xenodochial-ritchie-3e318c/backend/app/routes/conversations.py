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
from app.models.user import User
from app.services.chat.service import ChatService

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class HumanMessageInput(BaseModel):
    text: str


class ImproveMessageInput(BaseModel):
    text: str


class ReleaseBody(BaseModel):
    note: Optional[str] = None
    trainable: bool = False
    resolution_summary: Optional[str] = None
    resolution_category: Optional[str] = None  # 'precio', 'financiamiento', 'objecion', etc.


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
        is_human = bool(lead.human_mode)
        assigned_to = lead.human_assigned_to

        # Visibility rule:
        # - AI-managed leads (human_mode=False) → visible to everyone
        # - Human-taken leads with an assigned agent → only visible to that agent
        # - Auto-escalated leads (human_mode=True, no assigned agent) → visible to everyone
        if is_human and assigned_to is not None and assigned_to != current_user_id:
            continue

        # Filter by mode
        if mode == "human" and not is_human:
            continue
        if mode == "ai" and is_human:
            continue

        name = meta.get("nombre") or meta.get("name") or lead.name
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
            human_assigned_to=assigned_to,
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

    raw_uid = current_user.get("user_id") or current_user.get("id")
    try:
        uid = int(raw_uid) if raw_uid is not None else None
    except (TypeError, ValueError):
        uid = raw_uid

    # Guard: warn caller if lead is already assigned to a different agent
    if lead.human_assigned_to is not None and lead.human_assigned_to != uid:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ALREADY_ASSIGNED",
                "message": "Este lead ya está siendo atendido por otro agente.",
                "assigned_to": lead.human_assigned_to,
            },
        )

    lead.human_mode = True
    lead.human_assigned_to = uid
    lead.human_taken_at = datetime.now(timezone.utc)

    # Mark as notified immediately so the AI never fires the "Entiendo tu frustración"
    # escalation message when the advisor manually takes control — the advisor will
    # write their own greeting. Without this, the next inbound message triggers the
    # generic handoff notice, which is confusing for leads that aren't frustrated.
    _meta = dict(lead.lead_metadata or {})
    _meta["human_mode_notified"] = True
    lead.lead_metadata = _meta

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
    body: ReleaseBody = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Human agent releases control — AI resumes.

    Optionally accepts a release note that Sofía injects into her context on
    the next turn, and a trainable resolution that gets added to the broker's
    knowledge base for future RAG retrieval.
    """
    if body is None:
        body = ReleaseBody()

    broker_id = current_user.get("broker_id")
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.broker_id == broker_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    now = datetime.now(timezone.utc)

    lead.human_mode = False
    lead.human_assigned_to = None
    lead.human_taken_at = None
    lead.human_released_at = now
    lead.human_release_note = body.note  # May be None — clears the previous note if omitted

    # Capture escalated_reason BEFORE clearing the metadata (it's wiped below).
    _escalated_reason = (lead.lead_metadata or {}).get("sentiment", {}).get("escalated_reason")

    # Reset human_mode_notified flag and frustration score atomically via jsonb_set
    # so Sofía resumes without the old escalation state and fires the handoff
    # message again if re-escalated later.
    from sqlalchemy import text as _sa_text
    import json as _json
    from app.services.sentiment.scorer import empty_sentiment as _empty_sent
    _new_meta = dict(lead.lead_metadata or {})
    _new_meta.pop("human_mode_notified", None)
    _new_meta.pop("human_mode", None)
    _new_meta.pop("human_assigned_to", None)
    _new_meta.pop("human_taken_at", None)
    lead.lead_metadata = _new_meta
    await db.execute(
        _sa_text(
            "UPDATE leads SET metadata = jsonb_set("
            "COALESCE(metadata,'{}'), '{sentiment}', CAST(:val AS jsonb), true)"
            " WHERE id = :lid"
        ),
        {"val": _json.dumps(_empty_sent()), "lid": lead.id},
    )
    await db.commit()

    # Feedback loop — create a knowledge-base entry so Sofía can handle
    # similar cases autonomously in the future.
    if body.trainable and body.resolution_summary:
        try:
            from app.services.knowledge.rag_service import RAGService
            await RAGService.add_document(
                db=db,
                broker_id=broker_id,
                title=f"Resolución: {body.resolution_category or 'caso_escalado'}",
                content=body.resolution_summary,
                source_type="custom",
                metadata={
                    "source_subtype": "resolution",
                    "lead_id": lead_id,
                    "agent_id": current_user.get("id"),
                    "escalated_reason": _escalated_reason,
                    "date": now.isoformat(),
                },
            )
        except Exception as _kb_exc:
            logger.warning("release_lead: failed to add KB entry: %s", _kb_exc)

    try:
        from app.core.websocket_manager import ws_manager
        await ws_manager.broadcast(broker_id, "human_mode_changed", {
            "lead_id": lead_id,
            "human_mode": False,
            "release_note": body.note,
        })
    except Exception:
        pass

    return {"ok": True, "human_mode": False}


@router.post("/leads/{lead_id}/do-not-reply")
async def enable_do_not_reply(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Activate do-not-reply mode: AI sends a fixed fallback instead of processing messages."""
    from sqlalchemy import text

    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.broker_id == current_user.get("broker_id"))
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    await db.execute(
        text("""
            UPDATE leads
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'),
                '{do_not_reply}',
                CAST('true' AS jsonb),
                true
            )
            WHERE id = :lead_id
        """),
        {"lead_id": lead_id},
    )
    await db.commit()

    try:
        from app.core.websocket_manager import ws_manager
        await ws_manager.broadcast(current_user.get("broker_id"), "do_not_reply_changed", {
            "lead_id": lead_id,
            "do_not_reply": True,
        })
    except Exception:
        pass

    return {"ok": True, "do_not_reply": True}


@router.delete("/leads/{lead_id}/do-not-reply")
async def disable_do_not_reply(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Deactivate do-not-reply mode: AI resumes normal processing."""
    from sqlalchemy import text

    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.broker_id == current_user.get("broker_id"))
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    await db.execute(
        text("""
            UPDATE leads
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'),
                '{do_not_reply}',
                CAST('false' AS jsonb),
                true
            )
            WHERE id = :lead_id
        """),
        {"lead_id": lead_id},
    )
    await db.commit()

    try:
        from app.core.websocket_manager import ws_manager
        await ws_manager.broadcast(current_user.get("broker_id"), "do_not_reply_changed", {
            "lead_id": lead_id,
            "do_not_reply": False,
        })
    except Exception:
        pass

    return {"ok": True, "do_not_reply": False}



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

    if not lead.human_mode:
        raise HTTPException(status_code=400, detail="Lead is not in human mode")

    provider_name, channel_user_id = await _get_lead_channel(db, lead_id)

    # Resolve the sending agent's name for WhatsApp attribution
    agent_display_name = None
    try:
        user_id = current_user.get("user_id")
        if user_id:
            user_result = await db.execute(select(User).where(User.id == int(user_id)))
            agent = user_result.scalars().first()
            if agent:
                agent_display_name = agent.name or agent.email.split("@")[0].title()
    except Exception:
        pass

    # Format message with agent attribution for WhatsApp (*Name:*\n prefix).
    # NOTE: The ChatService branch (Telegram / other channels) intentionally
    # omits the attribution prefix — ChatService may also write the message to
    # the DB, and we want the plain text stored there. Telegram's own chat UI
    # already shows the sender name, so the prefix is unnecessary.
    def _format_with_agent(text: str) -> str:
        if not agent_display_name:
            return text
        return f"*{agent_display_name}:*\n{text}"

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
            await wa.send_text_message(channel_user_id, _format_with_agent(body.text))
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


@router.post("/improve-message")
async def improve_message(
    body: ImproveMessageInput,
    current_user=Depends(get_current_user),
):
    """Use AI to correct grammar, punctuation and style of a human agent message (Spanish)."""
    from app.services.llm.facade import LLMServiceFacade

    if not body.text.strip():
        return {"improved": body.text}

    prompt = (
        "Eres un asistente de redacción para asesores inmobiliarios en Chile. "
        "Tu única tarea es corregir ortografía, puntuación, acentos y mayúsculas del mensaje que te doy, "
        "manteniendo exactamente el mismo tono y contenido. "
        "Reglas: usa signos de interrogación y exclamación de apertura (¿ ¡) cuando corresponda, "
        "respeta el tuteo o ustedeo original, no agregues ni quites información, no cambies el vocabulario ni el estilo. "
        "Responde ÚNICAMENTE con el mensaje corregido, sin explicaciones ni comillas.\n\n"
        f"Mensaje: {body.text}"
    )

    try:
        import time as _time
        _t0 = _time.monotonic()
        improved = await LLMServiceFacade.generate_response(prompt)
        _latency_ms = int((_time.monotonic() - _t0) * 1000)
        # Track LLM cost so it appears in the observability dashboard
        try:
            from app.services.llm.call_logger import log_llm_call
            # Spanish text averages ~3.5 chars/token; use // 3 as a conservative
            # over-estimate rather than the English-biased // 4 heuristic.
            await log_llm_call(
                provider="unknown",
                model="unknown",
                call_type="improve_message",
                input_tokens=max(1, len(prompt) // 3),
                output_tokens=max(1, len(improved) // 3),
                latency_ms=_latency_ms,
                broker_id=current_user.get("broker_id"),
                lead_id=None,
                used_fallback=False,
            )
        except Exception:
            pass
        return {"improved": improved.strip()}
    except Exception as exc:
        logger.warning("improve_message LLM call failed: %s", exc)
        return {"improved": body.text}


@router.get("/leads/{lead_id}/escalation-brief")
async def get_escalation_brief(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return the most recent LLM-generated escalation brief for this lead.

    The brief is shown to the human agent when they open a conversation that
    was escalated from AI. It includes the escalation reason, lead profile,
    collected data, conversation summary, emotional context, and a suggested
    action — all pre-generated at escalation time.
    """
    broker_id = current_user.get("broker_id")
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.broker_id == broker_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from app.services.handoff.brief_generator import get_latest_brief
    brief = await get_latest_brief(db, lead_id)
    return brief or {"brief_text": None}
