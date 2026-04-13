"""
Voice call routes for managing phone calls
"""
import hashlib
import hmac
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List, Optional, Any
from pydantic import BaseModel
from app.core.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserRole
from app.services.voice import VoiceCallService
from app.services.voice.call_service import handle_tool_call
from app.services.voice.orchestration_service import VapiOrchestrationService
from app.services.voice.types import CallEventType
from app.schemas.voice_call import (
    VoiceCallResponse,
    VoiceCallListResponse,
    CallInitiateRequest,
    CallStartRequest,
    CallStartResponse,
    AgentVoiceProfileResponse,
    AgentVoiceProfileUpdate,
    AgentVoiceTemplateCreate,
    AgentVoiceTemplateUpdate,
    AgentVoiceTemplateResponse,
    CallMetricsResponse,
)
from app.models.broker_voice_config import BrokerVoiceConfig
from app.models.agent_voice_template import AgentVoiceTemplate
from app.models.agent_voice_profile import AgentVoiceProfile
from app.models.voice_call import VoiceCall, CallStatus
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_current_user_obj(
    current_user: dict,
    db: AsyncSession,
) -> User:
    """Resolve the full User ORM object from the JWT dict."""
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _verify_vapi_signature(raw_body: bytes, headers: dict, secret: str) -> bool:
    """Verify HMAC-SHA256 webhook signature from Vapi."""
    sig = headers.get("x-vapi-signature") or headers.get("X-Vapi-Signature") or ""
    ts = headers.get("x-vapi-timestamp") or headers.get("X-Vapi-Timestamp") or ""
    if not sig or not ts:
        return False
    try:
        if abs(time.time() - float(ts)) > 300:
            return False
    except ValueError:
        return False
    expected = hmac.new(
        secret.encode(),
        (ts + "." + raw_body.decode("utf-8", errors="replace")).encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected)


async def _handle_vapi_webhook(
    payload: dict,
    db: AsyncSession,
    provider: Any,
    headers: Optional[dict] = None,
    raw_body: Optional[bytes] = None,
) -> dict:
    """
    Shared VAPI webhook dispatch. Returns a dict to be returned as JSON.
    Always return HTTP 200 to VAPI; use dict for body.
    """
    # Verify Vapi webhook signature.
    # VAPI_WEBHOOK_SECRET must be set; if not configured we reject all webhooks
    # to avoid processing unauthenticated requests in production.
    if not settings.VAPI_WEBHOOK_SECRET:
        logger.error(
            "Vapi webhook received but VAPI_WEBHOOK_SECRET is not configured — rejecting. "
            "Set VAPI_WEBHOOK_SECRET in your environment variables."
        )
        return {"error": "Webhook secret not configured"}

    h = headers or {}
    # Prefer HMAC signature (replay-resistant); fall back to shared secret.
    if (h.get("x-vapi-signature") or h.get("X-Vapi-Signature")):
        if raw_body is None or not _verify_vapi_signature(
            raw_body, h, settings.VAPI_WEBHOOK_SECRET
        ):
            logger.warning("Vapi webhook: invalid HMAC signature, rejecting request")
            return {"error": "Unauthorized"}
    else:
        token = h.get("x-vapi-secret") or ""
        if token != settings.VAPI_WEBHOOK_SECRET:
            logger.warning("Vapi webhook: invalid secret, rejecting request")
            return {"error": "Unauthorized"}

    try:
        raw_event = await provider.handle_webhook(payload, headers=headers or {})

        if (
            not raw_event.external_call_id
            and not raw_event.call_id_from_metadata
            and raw_event.event_type != CallEventType.ASSISTANT_REQUEST
        ):
            return {"ok": True}

        if raw_event.event_type == CallEventType.TOOL_CALLS:
            tool_calls_data = raw_event.tool_calls_data or []
            results = []
            for item in tool_calls_data:
                name = item.get("name") or ""
                tool_call_id = item.get("tool_call_id") or item.get("toolCall", {}).get("id") or ""
                params = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
                result_str = await handle_tool_call(
                    name,
                    tool_call_id,
                    params,
                    db=db,
                    external_call_id=raw_event.external_call_id or None,
                )
                results.append({
                    "name": name,
                    "toolCallId": tool_call_id,
                    "result": result_str,
                })
            return {"results": results}

        if raw_event.event_type == CallEventType.ASSISTANT_REQUEST:
            message = payload.get("message") or {}
            call = message.get("call") or {}
            phone_number_id = call.get("phoneNumberId")
            if not phone_number_id:
                return {"error": "No assistant configured"}
            result = await db.execute(
                select(BrokerVoiceConfig).where(
                    BrokerVoiceConfig.phone_number_id == phone_number_id
                )
            )
            config = result.scalars().first()
            if config and getattr(config, "assistant_id_default", None):
                return {"assistantId": config.assistant_id_default}
            return {"error": "No assistant configured"}

        if raw_event.event_type == CallEventType.END_OF_CALL_REPORT:
            from app.tasks.voice_tasks import process_end_of_call_report
            transcript = raw_event.transcript or ""
            artifact_messages = raw_event.artifact_messages or []
            ended_reason = raw_event.ended_reason
            recording_url = raw_event.recording_url
            process_end_of_call_report.delay(
                raw_event.external_call_id,
                transcript,
                artifact_messages,
                ended_reason,
                recording_url,
            )
            return {"ok": True}

        if raw_event.event_type in (
            CallEventType.CALL_ENDED,
            CallEventType.STATUS_UPDATE,
            CallEventType.TRANSCRIPT_UPDATE,
            CallEventType.CALL_STARTED,
            CallEventType.CALL_RINGING,
            CallEventType.CALL_ANSWERED,
            CallEventType.CALL_FAILED,
        ):
            await VoiceCallService.handle_normalized_event(db, raw_event)

            # Push real-time events to the initiating agent via WebSocket
            if raw_event.external_call_id:
                try:
                    call_result = await db.execute(
                        select(VoiceCall).where(
                            VoiceCall.external_call_id == raw_event.external_call_id
                        )
                    )
                    vc = call_result.scalars().first()
                    if vc and vc.agent_user_id:
                        from app.core.websocket_manager import ws_manager
                        from app.models.user import User as _User
                        user_result = await db.execute(
                            select(_User).where(_User.id == vc.agent_user_id)
                        )
                        agent = user_result.scalars().first()
                        broker_id = agent.broker_id if agent else None
                        if broker_id:
                            event_name = (
                                "call_transcript"
                                if raw_event.event_type == CallEventType.TRANSCRIPT_UPDATE
                                else "call_status"
                            )
                            event_data: dict = {"call_id": vc.id}
                            if raw_event.event_type == CallEventType.TRANSCRIPT_UPDATE:
                                event_data["transcript"] = getattr(raw_event, "transcript", None)
                            else:
                                event_data["status"] = raw_event.event_type.value
                            await ws_manager.send_to_user(
                                broker_id=broker_id,
                                user_id=str(vc.agent_user_id),
                                event=event_name,
                                data=event_data,
                            )
                except Exception as ws_err:
                    logger.warning("WS push failed for call event: %s", ws_err)

            return {"ok": True}

        if raw_event.event_type == CallEventType.HANG:
            logger.warning(
                "VAPI hang event for call_id=%s",
                raw_event.external_call_id,
            )
            return {"ok": True}

        logger.info("Unrecognized VAPI webhook event type: %s", raw_event.event_type)
        return {"status": "ignored"}

    except Exception as e:
        logger.error("Error handling voice webhook: %s", str(e), exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/initiate", response_model=VoiceCallResponse, status_code=201)
async def initiate_call(
    request: CallInitiateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate an outbound call to a lead"""

    try:
        broker_id = current_user.get("id")

        # Rate limiting: max 5 simultaneous active calls per broker
        from app.models.voice_call import VoiceCall, CallStatus
        from sqlalchemy import func
        active_statuses = [CallStatus.INITIATED, CallStatus.RINGING, CallStatus.ANSWERED]
        count_result = await db.execute(
            select(func.count()).select_from(VoiceCall).where(
                VoiceCall.broker_id == broker_id,
                VoiceCall.status.in_(active_statuses),
            )
        )
        active_count = count_result.scalar_one()
        if active_count >= 5:
            raise HTTPException(
                status_code=429,
                detail="Máximo 5 llamadas activas simultáneas por broker."
            )

        voice_call = await VoiceCallService.initiate_call(
            db=db,
            lead_id=request.lead_id,
            campaign_id=request.campaign_id,
            broker_id=broker_id,
            agent_type=request.agent_type
        )
        
        return VoiceCallResponse.model_validate(voice_call)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error initiating call: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhooks/voice/{provider_name}")
async def voice_webhook_by_provider(
    provider_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook endpoint for voice callbacks by provider (vapi, bland, retell).
    """
    raw_body = await request.body()
    try:
        import json as _json
        payload = _json.loads(raw_body)
    except Exception:
        payload = {}
    from app.services.voice.factory import get_voice_provider as get_provider_async
    provider = await get_provider_async(provider_type=provider_name, db=db)
    body = await _handle_vapi_webhook(
        payload, db, provider, headers=dict(request.headers), raw_body=raw_body
    )
    return JSONResponse(status_code=200, content=body)


@router.post("/webhooks/voice")
async def voice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook endpoint for voice callbacks (default provider: vapi).
    Use POST /webhooks/voice/{provider} for explicit provider routing.
    """
    raw_body = await request.body()
    try:
        import json as _json
        payload = _json.loads(raw_body)
    except Exception:
        payload = {}
    from app.services.voice.factory import get_voice_provider as get_provider_async
    provider = await get_provider_async(provider_type="vapi", db=db)
    body = await _handle_vapi_webhook(
        payload, db, provider, headers=dict(request.headers), raw_body=raw_body
    )
    return JSONResponse(status_code=200, content=body)


@router.get("/leads/{lead_id}", response_model=VoiceCallListResponse)
async def get_call_history(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get call history for a lead"""
    
    try:
        broker_id = current_user.get("id")
        
        calls = await VoiceCallService.get_call_history(
            db=db,
            lead_id=lead_id,
            broker_id=broker_id
        )
        
        return VoiceCallListResponse(
            data=[VoiceCallResponse.model_validate(call) for call in calls]
        )
        
    except Exception as e:
        logger.error(f"Error getting call history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{call_id}")
async def get_call_details(
    call_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get call details including transcript and summary"""
    
    try:
        broker_id = current_user.get("id")
        
        from app.models.voice_call import VoiceCall
        from sqlalchemy.future import select
        
        query = select(VoiceCall).where(VoiceCall.id == call_id)
        
        if broker_id:
            query = query.where(VoiceCall.broker_id == broker_id)
        
        result = await db.execute(query)
        voice_call = result.scalars().first()
        
        if not voice_call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Get transcript lines
        from app.models.voice_call import CallTranscript
        transcript_result = await db.execute(
            select(CallTranscript)
            .where(CallTranscript.voice_call_id == call_id)
            .order_by(CallTranscript.timestamp)
        )
        transcript_lines = transcript_result.scalars().all()
        
        return {
            "call": VoiceCallResponse.model_validate(voice_call),
            "transcript_lines": [
                {
                    "speaker": line.speaker.value,
                    "text": line.text,
                    "timestamp": line.timestamp,
                    "confidence": line.confidence
                }
                for line in transcript_lines
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── CRM-initiated calls (Phase 1 — Transcriptor) ─────────────────────────────

@router.post("/calls/start", response_model=CallStartResponse, status_code=201)
async def start_call(
    request: CallStartRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a CRM-initiated voice call (Transcriptor or AI Agent mode)."""
    agent_user = await _get_current_user_obj(current_user, db)

    # Rate limiting: max 3 simultaneous active calls per agent
    active_statuses = [CallStatus.INITIATED, CallStatus.RINGING, CallStatus.ANSWERED]
    count_result = await db.execute(
        select(func.count()).select_from(VoiceCall).where(
            VoiceCall.agent_user_id == agent_user.id,
            VoiceCall.status.in_(active_statuses),
        )
    )
    if (count_result.scalar_one() or 0) >= 3:
        raise HTTPException(
            status_code=429,
            detail="Máximo 3 llamadas activas simultáneas por agente.",
        )

    try:
        result = await VapiOrchestrationService.start_call(
            db=db,
            agent_user=agent_user,
            lead_id=request.lead_id,
            call_mode=request.call_mode,
            call_purpose=request.call_purpose,
        )
        return CallStartResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error starting call: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/calls/{voice_call_id}/external-id")
async def link_external_call_id(
    voice_call_id: int,
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Link the VAPI-assigned call ID to an existing VoiceCall row.

    Called by the frontend immediately after the @vapi-ai/web SDK fires
    the 'call-start' event, which includes the VAPI call ID. Without this
    link, webhook lookups by external_call_id would fail.
    """
    external_id = (body.get("external_call_id") or "").strip()
    if not external_id:
        raise HTTPException(status_code=422, detail="external_call_id required")

    agent_user = await _get_current_user_obj(current_user, db)
    result = await db.execute(
        select(VoiceCall).where(
            VoiceCall.id == voice_call_id,
            VoiceCall.agent_user_id == agent_user.id,
        )
    )
    voice_call = result.scalars().first()
    if not voice_call:
        raise HTTPException(status_code=404, detail="Call not found")

    # Guard: don't overwrite an already-linked ID (race condition / duplicate call)
    if voice_call.external_call_id and voice_call.external_call_id != external_id:
        raise HTTPException(
            status_code=409,
            detail=f"Call already linked to external_call_id={voice_call.external_call_id}",
        )

    voice_call.external_call_id = external_id
    if not voice_call.started_at:
        from datetime import datetime, timezone
        voice_call.started_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "external_call_id": external_id}


@router.post("/calls/{voice_call_id}/end")
async def end_call(
    voice_call_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel / end an in-progress CRM-initiated call."""
    agent_user = await _get_current_user_obj(current_user, db)
    result = await db.execute(
        select(VoiceCall).where(
            VoiceCall.id == voice_call_id,
            VoiceCall.agent_user_id == agent_user.id,
        )
    )
    voice_call = result.scalars().first()
    if not voice_call:
        raise HTTPException(status_code=404, detail="Call not found")

    if voice_call.external_call_id:
        try:
            from app.services.voice.factory import get_voice_provider as get_provider_async
            provider = await get_provider_async(provider_type="vapi", db=db)
            await provider.cancel_call(voice_call.external_call_id)
        except Exception as e:
            logger.warning("Could not cancel VAPI call %s: %s", voice_call.external_call_id, e)

    voice_call.status = CallStatus.CANCELLED
    voice_call.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.get("/calls/{voice_call_id}/status", response_model=VoiceCallResponse)
async def get_call_status(
    voice_call_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get status of a CRM-initiated call."""
    agent_user = await _get_current_user_obj(current_user, db)
    result = await db.execute(
        select(VoiceCall).where(
            VoiceCall.id == voice_call_id,
            VoiceCall.agent_user_id == agent_user.id,
        )
    )
    voice_call = result.scalars().first()
    if not voice_call:
        raise HTTPException(status_code=404, detail="Call not found")
    return VoiceCallResponse.model_validate(voice_call)


@router.get("/calls/metrics", response_model=CallMetricsResponse)
async def get_call_metrics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate call metrics. Agents see own calls; admins see broker-wide."""
    agent_user = await _get_current_user_obj(current_user, db)

    base_filter = [VoiceCall.agent_user_id == agent_user.id]
    if agent_user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        from app.models.user import User as UserModel
        users_result = await db.execute(
            select(UserModel.id).where(UserModel.broker_id == agent_user.broker_id)
        )
        user_ids = [row[0] for row in users_result.all()]
        base_filter = [VoiceCall.agent_user_id.in_(user_ids)]

    total_result = await db.execute(
        select(func.count()).select_from(VoiceCall).where(*base_filter)
    )
    total = total_result.scalar_one() or 0

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_result = await db.execute(
        select(func.count()).select_from(VoiceCall).where(
            *base_filter,
            VoiceCall.created_at >= month_start,
        )
    )
    this_month = this_month_result.scalar_one() or 0

    avg_result = await db.execute(
        select(func.avg(VoiceCall.duration)).where(*base_filter)
    )
    avg_duration = avg_result.scalar_one()

    purpose_result = await db.execute(
        select(VoiceCall.call_purpose, func.count()).where(*base_filter).group_by(VoiceCall.call_purpose)
    )
    by_purpose = {row[0] or "unknown": row[1] for row in purpose_result.all()}

    mode_result = await db.execute(
        select(VoiceCall.call_mode, func.count()).where(*base_filter).group_by(VoiceCall.call_mode)
    )
    by_mode = {row[0] or "unknown": row[1] for row in mode_result.all()}

    return CallMetricsResponse(
        total=total,
        by_purpose=by_purpose,
        by_mode=by_mode,
        avg_duration_seconds=float(avg_duration) if avg_duration else None,
        this_month=this_month,
    )


# ── Agent voice profile (own profile only) ───────────────────────────────────

@router.get("/agents/me/voice-profile", response_model=AgentVoiceProfileResponse)
async def get_my_voice_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current agent's voice profile."""
    agent_user = await _get_current_user_obj(current_user, db)
    result = await db.execute(
        select(AgentVoiceProfile).where(AgentVoiceProfile.user_id == agent_user.id)
    )
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Voice profile not configured")
    return AgentVoiceProfileResponse.model_validate(profile)


@router.put("/agents/me/voice-profile", response_model=AgentVoiceProfileResponse)
async def update_my_voice_profile(
    body: AgentVoiceProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current agent's voice profile preferences."""
    agent_user = await _get_current_user_obj(current_user, db)
    result = await db.execute(
        select(AgentVoiceProfile).where(AgentVoiceProfile.user_id == agent_user.id)
    )
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Voice profile not configured — ask your admin to assign a template first",
        )

    template_result = await db.execute(
        select(AgentVoiceTemplate).where(AgentVoiceTemplate.id == profile.template_id)
    )
    template = template_result.scalars().first()

    if body.selected_voice_id is not None:
        allowed = (template.available_voice_ids or []) if template else []
        if body.selected_voice_id and body.selected_voice_id not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"selected_voice_id '{body.selected_voice_id}' not in template's available_voice_ids",
            )
        profile.selected_voice_id = body.selected_voice_id

    if body.selected_tone is not None:
        allowed_tones = (template.available_tones or []) if template else []
        if body.selected_tone and body.selected_tone not in allowed_tones:
            raise HTTPException(
                status_code=422,
                detail=f"selected_tone '{body.selected_tone}' not in template's available_tones",
            )
        profile.selected_tone = body.selected_tone

    if body.assistant_name is not None:
        profile.assistant_name = body.assistant_name
    if body.opening_message is not None:
        profile.opening_message = body.opening_message
    if body.preferred_call_mode is not None:
        profile.preferred_call_mode = body.preferred_call_mode

    await db.commit()
    await db.refresh(profile)
    return AgentVoiceProfileResponse.model_validate(profile)


# ── Broker voice template management (ADMIN only) ────────────────────────────

def _require_admin(user: User) -> None:
    if user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(status_code=403, detail="Admin role required")


@router.get("/brokers/voice-templates", response_model=List[AgentVoiceTemplateResponse])
async def list_voice_templates(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all voice templates for this broker."""
    agent_user = await _get_current_user_obj(current_user, db)
    result = await db.execute(
        select(AgentVoiceTemplate).where(
            AgentVoiceTemplate.broker_id == agent_user.broker_id
        )
    )
    return [AgentVoiceTemplateResponse.model_validate(t) for t in result.scalars().all()]


@router.post("/brokers/voice-templates", response_model=AgentVoiceTemplateResponse, status_code=201)
async def create_voice_template(
    body: AgentVoiceTemplateCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a voice template for this broker. ADMIN only."""
    agent_user = await _get_current_user_obj(current_user, db)
    _require_admin(agent_user)

    template = AgentVoiceTemplate(
        broker_id=agent_user.broker_id,
        **body.model_dump(),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return AgentVoiceTemplateResponse.model_validate(template)


@router.get("/brokers/voice-templates/{template_id}", response_model=AgentVoiceTemplateResponse)
async def get_voice_template(
    template_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single voice template."""
    agent_user = await _get_current_user_obj(current_user, db)
    result = await db.execute(
        select(AgentVoiceTemplate).where(
            AgentVoiceTemplate.id == template_id,
            AgentVoiceTemplate.broker_id == agent_user.broker_id,
        )
    )
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return AgentVoiceTemplateResponse.model_validate(template)


@router.put("/brokers/voice-templates/{template_id}", response_model=AgentVoiceTemplateResponse)
async def update_voice_template(
    template_id: int,
    body: AgentVoiceTemplateUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a voice template. ADMIN only."""
    agent_user = await _get_current_user_obj(current_user, db)
    _require_admin(agent_user)
    result = await db.execute(
        select(AgentVoiceTemplate).where(
            AgentVoiceTemplate.id == template_id,
            AgentVoiceTemplate.broker_id == agent_user.broker_id,
        )
    )
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    await db.commit()
    await db.refresh(template)
    return AgentVoiceTemplateResponse.model_validate(template)


@router.delete("/brokers/voice-templates/{template_id}", status_code=204)
async def delete_voice_template(
    template_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a voice template. ADMIN only."""
    agent_user = await _get_current_user_obj(current_user, db)
    _require_admin(agent_user)
    result = await db.execute(
        select(AgentVoiceTemplate).where(
            AgentVoiceTemplate.id == template_id,
            AgentVoiceTemplate.broker_id == agent_user.broker_id,
        )
    )
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(template)
    await db.commit()


@router.get("/brokers/voice-templates/{template_id}/available-voices")
async def list_available_voices(
    template_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List allowed voice IDs for agent dropdown."""
    agent_user = await _get_current_user_obj(current_user, db)
    result = await db.execute(
        select(AgentVoiceTemplate).where(
            AgentVoiceTemplate.id == template_id,
            AgentVoiceTemplate.broker_id == agent_user.broker_id,
        )
    )
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"voice_ids": template.available_voice_ids or []}


@router.get("/brokers/voice-templates/{template_id}/available-tones")
async def list_available_tones(
    template_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List allowed tones for agent dropdown."""
    agent_user = await _get_current_user_obj(current_user, db)
    result = await db.execute(
        select(AgentVoiceTemplate).where(
            AgentVoiceTemplate.id == template_id,
            AgentVoiceTemplate.broker_id == agent_user.broker_id,
        )
    )
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"tones": template.available_tones or []}


@router.get("/brokers/voice-catalog")
async def list_vapi_voice_catalog(
    current_user: dict = Depends(get_current_user),
):
    """
    Proxy to VAPI voice library — returns available TTS voices for selection.
    Broker admin uses this to populate available_voice_ids on a template.
    """
    import aiohttp
    api_key = settings.VAPI_API_KEY
    if not api_key:
        raise HTTPException(status_code=503, detail="VAPI_API_KEY not configured")

    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.vapi.ai/voice-library",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("VAPI voice-library error %s: %s", response.status, error_text)
                    raise HTTPException(status_code=502, detail="Failed to fetch voice catalog from VAPI")
                data = await response.json()
    except aiohttp.ClientError as e:
        logger.error("VAPI voice-library connection error: %s", e)
        raise HTTPException(status_code=502, detail="Could not reach VAPI API")

    # Normalize — VAPI returns a list of voice objects
    voices = data if isinstance(data, list) else data.get("voices") or data.get("items") or []
    return {
        "voices": [
            {
                "id": v.get("voiceId") or v.get("id"),
                "name": v.get("name"),
                "provider": v.get("provider"),
                "language": v.get("language"),
                "gender": v.get("gender"),
                "preview_url": v.get("previewUrl") or v.get("preview_url"),
            }
            for v in voices
            if v.get("voiceId") or v.get("id")
        ]
    }


@router.put("/brokers/agents/{user_id}/voice-template", response_model=AgentVoiceProfileResponse)
async def assign_voice_template_to_agent(
    user_id: int,
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Assign a template to an agent (creates or updates AgentVoiceProfile).
    ADMIN only. Broker isolation enforced.
    """
    admin_user = await _get_current_user_obj(current_user, db)
    _require_admin(admin_user)

    template_id = body.get("template_id")
    if not template_id:
        raise HTTPException(status_code=422, detail="template_id required")

    agent_result = await db.execute(
        select(User).where(User.id == user_id, User.broker_id == admin_user.broker_id)
    )
    target_agent = agent_result.scalars().first()
    if not target_agent:
        raise HTTPException(status_code=404, detail="Agent not found in this broker")

    template_result = await db.execute(
        select(AgentVoiceTemplate).where(
            AgentVoiceTemplate.id == template_id,
            AgentVoiceTemplate.broker_id == admin_user.broker_id,
        )
    )
    template = template_result.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found in this broker")

    profile_result = await db.execute(
        select(AgentVoiceProfile).where(AgentVoiceProfile.user_id == user_id)
    )
    profile = profile_result.scalars().first()
    if profile:
        profile.template_id = template_id
    else:
        profile = AgentVoiceProfile(user_id=user_id, template_id=template_id)
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    return AgentVoiceProfileResponse.model_validate(profile)
