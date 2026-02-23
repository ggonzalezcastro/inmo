from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, Field, field_validator
from typing import Optional, AsyncGenerator
import json
import asyncio
import logging

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.leads import LeadService
from app.services.chat import ChatOrchestratorService
from app.services.shared import ActivityService
from app.schemas.lead import sanitize_html
from app.models.chat_message import ChatMessage as ChatMessageModel, ChatProvider

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatMessageInput(BaseModel):
    """Input model for chat messages with validation"""
    message: str = Field(..., min_length=1, max_length=4000, description="Chat message content")
    lead_id: Optional[int] = Field(None, gt=0, description="Optional lead ID, must be positive")
    provider: Optional[str] = Field(None, description="Chat provider (webchat, telegram, whatsapp, etc.)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Hola, me interesa un departamento de 2 dormitorios en Las Condes",
                "lead_id": None,
                "provider": "webchat",
            }
        }
    }

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """XSS sanitization: strip all HTML/scripts from chat message."""
        cleaned = sanitize_html(v, max_length=4000)
        if not cleaned or len(cleaned.strip()) < 1:
            raise ValueError("Message is required and cannot be empty after sanitization")
        return cleaned


# Keep alias for backward compatibility
ChatMessage = ChatMessageInput


class ChatResponse(BaseModel):
    response: str
    lead_id: int
    lead_score: float
    lead_status: str


@router.post(
    "/test",
    response_model=ChatResponse,
    summary="Send a message and receive Sofía's AI response",
    responses={
        200: {
            "description": "AI response generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "response": "¡Hola! Soy Sofía. ¿Cuál es tu nombre?",
                        "lead_id": 42,
                        "lead_score": 15.0,
                        "lead_status": "cold",
                    }
                }
            },
        },
        404: {"description": "lead_id not found"},
        422: {"description": "message empty or too long (max 4000 chars)"},
    },
)
async def test_chat(
    chat_message: ChatMessageInput,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    provider: Optional[str] = Query(None, description="Chat provider (webchat, telegram, whatsapp)"),
):
    """
    Send a lead message to Sofía and receive an AI-generated response.

    - If `lead_id` is omitted a **new lead** is created automatically.
    - The response includes the updated `lead_score` (0–100) and `lead_status`
      (`cold` / `warm` / `hot` / `converted` / `lost`).
    - Internally runs RAG KB search and optionally uses Gemini context caching.
    """
    provider_name = chat_message.provider or provider or "webchat"
    logger.info(
        "[CHAT] test_chat called - message length=%s, lead_id=%s, provider=%s",
        len(chat_message.message),
        chat_message.lead_id,
        provider_name,
    )
    try:
        result = await ChatOrchestratorService.process_chat_message(
            db=db,
            current_user=current_user,
            message=chat_message.message,
            lead_id=chat_message.lead_id,
            provider_name=provider_name,
        )
        return ChatResponse(
            response=result.response,
            lead_id=result.lead_id,
            lead_score=result.lead_score,
            lead_status=getattr(result.lead_status, "value", str(result.lead_status)) or "cold",
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            await db.rollback()
            raise HTTPException(status_code=404, detail=str(e))
        logger.error("ValueError in test_chat: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error("Error in test chat: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{lead_id}/messages")
async def get_chat_messages(
    lead_id: int,
    skip: int = 0,
    limit: int = 100,
    provider: Optional[str] = Query(None, description="Filter by provider; if omitted, returns chat_messages then fallback to telegram_messages"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get chat messages for a lead. Prefers chat_messages (generic) when available; falls back to telegram_messages."""
    try:
        lead = await LeadService.get_lead(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Prefer ChatMessage (chat_messages table) when we have rows
        q = select(ChatMessageModel).where(ChatMessageModel.lead_id == lead_id)
        if provider:
            try:
                q = q.where(ChatMessageModel.provider == ChatProvider(provider))
            except ValueError:
                pass
        q = q.order_by(ChatMessageModel.created_at).offset(skip).limit(limit)
        messages_result = await db.execute(q)
        chat_msgs = messages_result.scalars().all()

        if chat_msgs:
            return {
                "lead_id": lead_id,
                "provider": "chat_messages",
                "messages": [
                    {
                        "id": msg.id,
                        "direction": getattr(msg.direction, "value", str(msg.direction)),
                        "message_text": msg.message_text,
                        "sender_type": "bot" if (getattr(msg.direction, "value", str(msg.direction)) == "out") else "customer",
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                        "ai_response_used": msg.ai_response_used or False,
                        "provider": getattr(msg.provider, "value", str(msg.provider)),
                    }
                    for msg in chat_msgs
                ],
                "total": len(chat_msgs),
                "skip": skip,
                "limit": limit,
            }

        # Fallback: telegram_messages
        from app.models.telegram_message import TelegramMessage

        messages_result = await db.execute(
            select(TelegramMessage)
            .where(TelegramMessage.lead_id == lead_id)
            .order_by(TelegramMessage.created_at)
            .offset(skip)
            .limit(limit)
        )
        messages = messages_result.scalars().all()
        return {
            "lead_id": lead_id,
            "provider": "telegram_messages",
            "messages": [
                {
                    "id": msg.id,
                    "direction": msg.direction.value,
                    "message_text": msg.message_text,
                    "sender_type": "bot" if msg.direction.value == "out" else "customer",
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "ai_response_used": msg.ai_response_used or False,
                }
                for msg in messages
            ],
            "total": len(messages),
            "skip": skip,
            "limit": limit,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting chat messages: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/verify/{lead_id}")
async def verify_lead_data(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify that lead data and messages are being saved correctly. Uses chat_messages when available, else telegram_messages."""
    from sqlalchemy import desc
    from app.models.activity_log import ActivityLog

    try:
        lead = await LeadService.get_lead(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Prefer chat_messages
        messages_result = await db.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.lead_id == lead_id)
            .order_by(desc(ChatMessageModel.created_at))
        )
        chat_msgs = messages_result.scalars().all()

        if chat_msgs:
            dir_val = lambda m: getattr(m.direction, "value", str(m.direction))
            messages_payload = [
                {
                    "id": msg.id,
                    "direction": dir_val(msg),
                    "message_text": msg.message_text,
                    "toon_format": f"{'U' if dir_val(msg) == 'in' else 'B'}:{msg.message_text}",
                    "user_id": msg.channel_user_id,
                    "provider": getattr(msg.provider, "value", str(msg.provider)),
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "ai_response_used": msg.ai_response_used,
                }
                for msg in chat_msgs
            ]
            messages_toon = "|".join(
                f"{'U' if dir_val(m) == 'in' else 'B'}:{m.message_text.replace('|', '‖')}"
                for m in reversed(chat_msgs)
            )
            total_messages = len(chat_msgs)
            inbound = len([m for m in chat_msgs if dir_val(m) == "in"])
            outbound = len([m for m in chat_msgs if dir_val(m) == "out"])
        else:
            from app.models.telegram_message import TelegramMessage

            messages_result = await db.execute(
                select(TelegramMessage)
                .where(TelegramMessage.lead_id == lead_id)
                .order_by(desc(TelegramMessage.created_at))
            )
            messages = messages_result.scalars().all()
            messages_payload = [
                {
                    "id": msg.id,
                    "direction": msg.direction.value,
                    "message_text": msg.message_text,
                    "toon_format": f"{'U' if msg.direction.value == 'in' else 'B'}:{msg.message_text}",
                    "user_id": msg.telegram_user_id,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "ai_response_used": msg.ai_response_used,
                }
                for msg in messages
            ]
            messages_toon = "|".join(
                f"{'U' if m.direction.value == 'in' else 'B'}:{m.message_text.replace('|', '‖')}"
                for m in reversed(messages)
            )
            total_messages = len(messages)
            inbound = len([m for m in messages if m.direction.value == "in"])
            outbound = len([m for m in messages if m.direction.value == "out"])

        activities_result = await db.execute(
            select(ActivityLog)
            .where(ActivityLog.lead_id == lead_id)
            .order_by(desc(ActivityLog.timestamp))
            .limit(20)
        )
        activities = activities_result.scalars().all()

        return {
            "lead": {
                "id": lead.id,
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "status": lead.status,
                "lead_score": lead.lead_score,
                "metadata": lead.lead_metadata if lead.lead_metadata else {},
                "metadata_toon": "|".join([f"{k}:{v}" for k, v in (lead.lead_metadata or {}).items() if v]),
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            },
            "messages": messages_payload,
            "messages_toon": messages_toon,
            "activities": [
                {
                    "id": act.id,
                    "action_type": act.action_type,
                    "details": act.details if act.details else {},
                    "details_toon": ActivityService.details_to_toon(act.details) if act.details else "",
                    "timestamp": act.timestamp.isoformat() if act.timestamp else None,
                }
                for act in activities
            ],
            "summary": {
                "total_messages": total_messages,
                "inbound_messages": inbound,
                "outbound_messages": outbound,
                "total_activities": len(activities),
                "has_name": bool(lead.name and lead.name not in ("User", "Test User")),
                "has_phone": bool(
                    lead.phone
                    and not str(lead.phone).startswith("web_chat_")
                    and not str(lead.phone).startswith("whatsapp_")
                ),
                "has_location": bool(lead.lead_metadata and lead.lead_metadata.get("location")),
                "has_budget": bool(lead.lead_metadata and lead.lead_metadata.get("budget")),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error verifying lead data: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── SSE streaming endpoint ────────────────────────────────────────────────────

@router.post("/stream")
async def stream_chat(
    chat_message: ChatMessageInput,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream LLM response tokens via SSE (Server-Sent Events).

    Each event has the form:
        data: {"token": "<chunk>"}\\n\\n
    A final event signals completion:
        data: {"done": true, "lead_id": <int>, "lead_score": <float>, "conversation_state": "<str>"}\\n\\n

    Frontend usage (Fetch API):
        const resp = await fetch('/api/v1/chat/stream', {method:'POST', ...});
        const reader = resp.body.getReader();
        // read chunks and display progressively
    """
    provider_name = chat_message.provider or "webchat"

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # ── Phase 1: Run full orchestration (DB, scoring, prompt building) ──
            # Use the same orchestrator but we need access to the built prompt.
            # We import the facade here to call build_llm_prompt after orchestration.
            from app.services.llm import LLMServiceFacade
            from app.services.llm.factory import get_llm_provider
            from app.services.leads import LeadContextService
            from app.core.cache import cache_delete

            # Run orchestration steps that don't involve the final LLM response
            result = await ChatOrchestratorService.process_chat_message(
                db=db,
                current_user=current_user,
                message=chat_message.message,
                lead_id=chat_message.lead_id,
                provider_name=provider_name,
            )

            # ── Phase 2: Stream the already-computed response ──────────────────
            # The orchestrator already generated the full response. For a true
            # streaming experience, we stream it word-by-word with a small delay.
            # For providers with native streaming (Gemini), yield from stream_generate.
            provider = get_llm_provider()
            full_response = result.response

            if hasattr(provider, "stream_generate") and len(full_response) > 50:
                # Re-build prompt for streaming (uses cached context)
                await cache_delete(f"lead_context:{result.lead_id}")
                context = await LeadContextService.get_lead_context(db, result.lead_id)
                broker_id = (current_user or {}).get("broker_id")
                system_prompt, messages = await LLMServiceFacade.build_llm_prompt(
                    context, chat_message.message, db=db, broker_id=broker_id
                )
                try:
                    async for chunk in provider.stream_generate(messages, system_prompt=system_prompt):
                        if chunk:
                            payload = json.dumps({"token": chunk}, ensure_ascii=False)
                            yield f"data: {payload}\n\n"
                    # done event uses the orchestrated metadata (score, state)
                    done_payload = json.dumps({
                        "done": True,
                        "lead_id": result.lead_id,
                        "lead_score": result.lead_score,
                        "lead_status": getattr(result.lead_status, "value", str(result.lead_status)),
                        "conversation_state": result.conversation_state,
                    })
                    yield f"data: {done_payload}\n\n"
                    return
                except Exception as stream_exc:
                    logger.warning("[SSE] Streaming failed, falling back to word stream: %s", stream_exc)

            # Fallback: stream the pre-computed response word by word
            words = full_response.split(" ")
            for i, word in enumerate(words):
                text = word if i == 0 else " " + word
                payload = json.dumps({"token": text}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.015)  # ~15ms per word ≈ natural typing speed

            done_payload = json.dumps({
                "done": True,
                "lead_id": result.lead_id,
                "lead_score": result.lead_score,
                "lead_status": getattr(result.lead_status, "value", str(result.lead_status)),
                "conversation_state": result.conversation_state,
            })
            yield f"data: {done_payload}\n\n"

        except ValueError as exc:
            error_payload = json.dumps({"error": str(exc), "code": "validation_error"})
            yield f"data: {error_payload}\n\n"
        except Exception as exc:
            logger.error("[SSE] Unhandled error in stream_chat: %s", exc, exc_info=True)
            error_payload = json.dumps({"error": "Internal server error", "code": "server_error"})
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable Nginx buffering
        },
    )

