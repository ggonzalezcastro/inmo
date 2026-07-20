"""
Voice call routes for managing phone calls
"""
import asyncio
import os
import hashlib
import hmac
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_
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
    CallListItem,
    CallListResponse,
)
from app.models.broker_voice_config import BrokerVoiceConfig
from app.models.agent_voice_template import AgentVoiceTemplate
from app.models.agent_voice_profile import AgentVoiceProfile
from app.models.voice_call import VoiceCall, CallStatus, CallPurpose
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_current_user_obj(
    current_user: dict,
    db: AsyncSession,
) -> User:
    """Resolve the full User ORM object from the JWT dict."""
    result = await db.execute(select(User).where(User.id == int(current_user["user_id"])))
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


async def _verify_twilio_request(request: Request) -> dict:
    """
    Validate X-Twilio-Signature on a Twilio form-encoded webhook.

    Returns the parsed form as a dict on success; raises 403 otherwise.
    Rejects all requests when TWILIO_AUTH_TOKEN is not configured, mirroring
    the VAPI webhook policy (never process unauthenticated webhooks).
    """
    form = await request.form()
    if not settings.TWILIO_AUTH_TOKEN:
        logger.error(
            "Twilio webhook received but TWILIO_AUTH_TOKEN is not configured — rejecting. "
            "Set TWILIO_AUTH_TOKEN in your environment variables."
        )
        raise HTTPException(status_code=403, detail="Twilio auth token not configured")

    from twilio.request_validator import RequestValidator

    signature = request.headers.get("X-Twilio-Signature", "")
    # Twilio signs the exact public URL it was configured with (path + query).
    url = settings.WEBHOOK_BASE_URL.rstrip("/") + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    if not signature or not validator.validate(url, dict(form), signature):
        logger.warning(
            "Twilio webhook: invalid signature, rejecting. path=%s call_sid=%s",
            request.url.path, form.get("CallSid", ""),
        )
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    return dict(form)


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
            if raw_event.external_call_id:
                try:
                    hang_result = await db.execute(
                        select(VoiceCall).where(
                            VoiceCall.external_call_id == raw_event.external_call_id
                        )
                    )
                    hang_vc = hang_result.scalars().first()
                    if hang_vc and hang_vc.status not in (
                        CallStatus.COMPLETED,
                        CallStatus.FAILED,
                        CallStatus.CANCELLED,
                    ):
                        hang_vc.status = CallStatus.CANCELLED
                        if not hang_vc.completed_at:
                            hang_vc.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                except Exception as hang_err:
                    logger.warning("HANG cleanup failed for %s: %s", raw_event.external_call_id, hang_err)
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


def _own_calls_filter(agent_user: User) -> list:
    """
    Visibility filter for call lists/metrics.

    Agents see calls they started (legacy VAPI sets agent_user_id, Pipecat
    sets initiated_by_id); admins see everything in their broker.
    """
    if agent_user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        return [VoiceCall.broker_id == agent_user.broker_id]
    return [
        VoiceCall.broker_id == agent_user.broker_id,
        or_(
            VoiceCall.agent_user_id == agent_user.id,
            VoiceCall.initiated_by_id == agent_user.id,
        ),
    ]


@router.get("", response_model=CallListResponse)
async def list_calls(
    limit: int = 25,
    offset: int = 0,
    lead_id: Optional[int] = None,
    purpose: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Broker-scoped call list for the Llamadas page (newest first)."""
    from app.models.lead import Lead

    agent_user = await _get_current_user_obj(current_user, db)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    filters = _own_calls_filter(agent_user)
    if lead_id is not None:
        filters.append(VoiceCall.lead_id == lead_id)
    if purpose:
        filters.append(VoiceCall.call_purpose == purpose)

    total_result = await db.execute(
        select(func.count()).select_from(VoiceCall).where(*filters)
    )
    total = total_result.scalar_one() or 0

    rows_result = await db.execute(
        select(VoiceCall, Lead.name)
        .join(Lead, Lead.id == VoiceCall.lead_id, isouter=True)
        .where(*filters)
        .order_by(VoiceCall.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = []
    for call, lead_name in rows_result.all():
        item = CallListItem.model_validate(call)
        item.lead_name = lead_name
        items.append(item)

    return CallListResponse(data=items, total=total)


@router.get("/metrics", response_model=CallMetricsResponse)
async def get_call_metrics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate call metrics. Agents see own calls; admins see broker-wide."""
    agent_user = await _get_current_user_obj(current_user, db)

    base_filter = _own_calls_filter(agent_user)

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

    # Pipecat calls set pipecat_mode; legacy VAPI calls set call_mode.
    _mode_col = func.coalesce(VoiceCall.pipecat_mode, VoiceCall.call_mode)
    mode_result = await db.execute(
        select(_mode_col, func.count()).where(*base_filter).group_by(_mode_col)
    )
    by_mode = {row[0] or "unknown": row[1] for row in mode_result.all()}

    return CallMetricsResponse(
        total=total,
        by_purpose=by_purpose,
        by_mode=by_mode,
        avg_duration_seconds=float(avg_duration) if avg_duration else None,
        this_month=this_month,
    )


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

@router.post("/start", response_model=CallStartResponse, status_code=201)
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


@router.patch("/{voice_call_id}/external-id")
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


@router.post("/{voice_call_id}/end")
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


@router.get("/{voice_call_id}/status", response_model=VoiceCallResponse)
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


# ══════════════════════════════════════════════════════════════════════════════
# PIPECAT VOICE ENDPOINTS
# Base: /api/v1/calls/pipecat/...
# ══════════════════════════════════════════════════════════════════════════════

class PipecatCallRequest(BaseModel):
    lead_id: int
    agent_phone: Optional[str] = None
    agent_user_id: Optional[int] = None
    # CallPurpose is a str Enum — Pydantic rejects values outside the 6 purposes
    call_purpose: Optional[CallPurpose] = None


class PipecatTransferRequest(BaseModel):
    agent_phone: str


class PipecatCallResponse(BaseModel):
    voice_call_id: int
    pipecat_mode: str
    status: str = "initiated"


class PipecatBatchRequest(BaseModel):
    lead_ids: List[int]
    call_purpose: Optional[CallPurpose] = None


def _pipecat_ws_token(voice_call_id: int) -> str:
    """
    HMAC token authorising a Twilio MediaStream to attach to this call.

    The audio WebSocket cannot use the JWT auth dependency (Twilio is the
    client, not a logged-in user), so we sign the voice_call_id with
    SECRET_KEY and require the token back on connect. This stops anyone from
    guessing a sequential call id and hijacking a live call's audio pipeline.
    """
    msg = str(voice_call_id).encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def _verify_pipecat_ws_token(voice_call_id: int, token: str) -> bool:
    if not token:
        return False
    return hmac.compare_digest(token, _pipecat_ws_token(voice_call_id))


def _pipecat_ws_url(voice_call_id: int) -> str:
    """Build the WebSocket URL Twilio will connect to for audio streaming."""
    base = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8000")
    # Twilio needs wss:// (or ws:// for local dev)
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    token = _pipecat_ws_token(voice_call_id)
    return f"{ws_base}/api/v1/calls/pipecat/ws/{voice_call_id}?token={token}"


def _pipecat_status_url() -> str:
    """Twilio call status callback URL."""
    import os
    base = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8000")
    return f"{base}/api/v1/calls/pipecat/status"


async def _launch_pipecat_pipeline(
    call_id: int,
    pipecat_mode: str,
    lead_id: int,
    broker_id: int,
    agent_phone: Optional[str],
    agent_user_id: Optional[int],
    twilio_call_sid: str,
    websocket: Any,
    stream_sid: str = "",
    call_purpose: Optional[str] = None,
) -> None:
    """
    Build and run the Pipecat pipeline for an active call.
    Must be called from the WebSocket endpoint after Twilio connects,
    because FastAPIWebsocketTransport requires the live WebSocket object.
    """
    from app.core.database import AsyncSessionLocal
    from app.services.voice.pipecat.pipeline_manager import pipeline_manager
    from app.services.voice.pipecat.voice_config import CallSessionConfig

    config = CallSessionConfig(
        lead_id=lead_id,
        broker_id=broker_id,
        voice_call_id=call_id,
        pipecat_mode=pipecat_mode,
        agent_phone=agent_phone,
        agent_user_id=agent_user_id,
        call_purpose=call_purpose,
    )
    logger.info(
        "[Pipecat] launching mode=%s call_id=%s lead=%s broker=%s stream_sid=%s call_sid=%s",
        pipecat_mode, call_id, lead_id, broker_id, stream_sid, twilio_call_sid,
    )

    # Kick off context prewarmer in parallel with pipeline construction.
    # Cuts ~3.5 s off first-turn latency by pre-loading lead context, broker
    # config, and warming the DB pool before the lead utters anything.
    try:
        from app.services.voice.pipecat.processors.context_prewarmer import schedule as _prewarm_schedule
        _prewarm_schedule(call_id, lead_id, broker_id)
    except Exception as _pre_exc:
        logger.warning("[Pipecat] prewarm schedule failed call_id=%s: %s", call_id, _pre_exc)

    try:
        if pipecat_mode == "autonomous":
            from app.services.voice.pipecat.pipelines.autonomous import build_autonomous_pipeline
            task_obj = build_autonomous_pipeline(
                config=config,
                db_session_factory=AsyncSessionLocal,
                pipeline_manager=pipeline_manager,
                websocket=websocket,
                stream_sid=stream_sid,
                twilio_call_sid=twilio_call_sid,
            )
        elif pipecat_mode == "handoff":
            from app.services.voice.pipecat.pipelines.handoff import build_handoff_pipeline
            from app.services.voice.pipecat.telephony.twilio_handler import TwilioHandler
            task_obj = build_handoff_pipeline(
                config=config,
                db_session_factory=AsyncSessionLocal,
                pipeline_manager=pipeline_manager,
                websocket=websocket,
                stream_sid=stream_sid,
                twilio_call_sid=twilio_call_sid,
                twilio_handler=TwilioHandler(),
            )
        elif pipecat_mode == "copilot":
            from app.services.voice.pipecat.pipelines.copilot import build_copilot_pipeline
            task_obj = build_copilot_pipeline(
                config=config,
                db_session_factory=AsyncSessionLocal,
                websocket=websocket,
                stream_sid=stream_sid,
                twilio_call_sid=twilio_call_sid,
            )
        elif pipecat_mode == "coaching":
            from app.services.voice.pipecat.pipelines.coaching import build_coaching_pipeline
            task_obj = build_coaching_pipeline(
                config=config,
                db_session_factory=AsyncSessionLocal,
                websocket=websocket,
                stream_sid=stream_sid,
                twilio_call_sid=twilio_call_sid,
            )
        else:
            logger.error("[Pipecat] Unknown pipecat_mode=%s call_id=%s", pipecat_mode, call_id)
            return

        from pipecat.pipeline.base_task import PipelineTaskParams
        from pipecat.frames.frames import TextFrame
        params = PipelineTaskParams(loop=asyncio.get_event_loop())
        async_task = asyncio.ensure_future(task_obj.run(params))
        pipeline_manager.register(call_id, async_task)
        logger.info("[Pipecat] pipeline running call_id=%s mode=%s", call_id, pipecat_mode)

        # Send greeting for AI-speaks-first modes (autonomous, handoff).
        # Goal: speak as soon as possible — no artificial sleep, lead-name
        # lookup runs in parallel with TTS connection establishment, and
        # chat-history persistence is fire-and-forget (does not delay TTS).
        if pipecat_mode in ("autonomous", "handoff"):
            async def _send_greeting():
                # Tiny grace period so the FastAPIWebsocketTransport finishes
                # binding before we queue frames. Pipecat buffers frames if
                # services aren't fully connected, so we don't need to wait
                # for Fish Audio / Deepgram handshakes here.
                _wait_ms = int(os.getenv("VOICE_GREETING_DELAY_MS", "0") or "0")
                if _wait_ms > 0:
                    await asyncio.sleep(_wait_ms / 1000.0)
                try:
                    from app.core.database import AsyncSessionLocal
                    from app.models.lead import Lead
                    from app.services.chat.service import ChatService
                    from app.services.chat.base_provider import ChatMessageData
                    from pipecat.frames.frames import LLMFullResponseEndFrame

                    # Try the prewarmer cache first to avoid an extra DB roundtrip.
                    lead_name = ""
                    try:
                        from app.services.voice.pipecat.processors import context_prewarmer as _pw
                        _cached = _pw._PREWARMED.get(call_id)
                        if _cached and _cached.lead_name:
                            lead_name = _cached.lead_name
                    except Exception:
                        pass

                    if not lead_name:
                        try:
                            async with AsyncSessionLocal() as _db:
                                _lead = await _db.get(Lead, lead_id)
                                if _lead and _lead.name:
                                    lead_name = _lead.name.strip().split()[0]
                        except Exception:
                            pass

                    # Purpose-specific greeting when the call has an objective
                    # (CRM-initiated calls); generic fallback otherwise.
                    from app.services.agents.prompts.skills.voice.purpose_instructions import (
                        get_purpose_greeting,
                    )
                    greeting = get_purpose_greeting(call_purpose, lead_name) or (
                        f"Hola{', ' + lead_name if lead_name else ''}, "
                        "soy Sofia, asistente virtual, "
                        "como te puedo ayudar hoy?"
                    )
                    _t0 = asyncio.get_event_loop().time()
                    await task_obj.queue_frame(TextFrame(text=greeting))
                    await task_obj.queue_frame(LLMFullResponseEndFrame())
                    _queued_ms = int((asyncio.get_event_loop().time() - _t0) * 1000)
                    logger.info(
                        "[Pipecat] greeting queued call_id=%s queue_ms=%d delay_ms=%d text=%r",
                        call_id, _queued_ms, _wait_ms, greeting,
                    )

                    # Save greeting to chat history in background — does NOT
                    # delay TTS playback.
                    async def _save_history():
                        try:
                            async with AsyncSessionLocal() as _db2:
                                await ChatService.log_message(
                                    _db2,
                                    lead_id=lead_id,
                                    broker_id=broker_id,
                                    provider_name="voice",
                                    message_data=ChatMessageData(
                                        channel_user_id="voice",
                                        channel_username=None,
                                        channel_message_id=None,
                                        message_text=greeting,
                                        direction="out",
                                    ),
                                    ai_used=True,
                                )
                        except Exception as _save_e:
                            logger.warning("[Pipecat] greeting DB save failed call_id=%s: %s", call_id, _save_e)
                    asyncio.ensure_future(_save_history())

                except Exception as _e:
                    logger.warning("[Pipecat] greeting failed call_id=%s: %s", call_id, _e)
            asyncio.ensure_future(_send_greeting())

        logger.debug("[Pipecat] awaiting pipeline task call_id=%s", call_id)
        try:
            await async_task
        except asyncio.CancelledError:
            logger.info("[Pipecat] pipeline cancelled (call ended) call_id=%s", call_id)
        logger.info("[Pipecat] pipeline task completed call_id=%s", call_id)

    except Exception as exc:
        logger.error("[Pipecat] pipeline launch failed call_id=%s: %s", call_id, exc, exc_info=True)


# ── WebSocket endpoint (Twilio streams audio here) ────────────────────────────

@router.websocket("/pipecat/ws/{voice_call_id}")
async def pipecat_audio_websocket(
    websocket: WebSocket,
    voice_call_id: int,
):
    """
    WebSocket endpoint for Twilio MediaStream audio.

    Twilio connects here when a call becomes active and sends the 'connected'
    + 'start' messages, then streams μ-law audio. We parse the stream_sid from
    the 'start' event, then hand the live WebSocket to the Pipecat pipeline.

    Auth: the URL carries an HMAC ?token= tied to voice_call_id (Twilio can't
    send a JWT). We reject on mismatch so a guessed call id cannot hijack audio.

    The DB session is opened manually and closed as soon as the call row is
    read — a call runs for minutes, and holding a pooled connection open for
    the whole call would exhaust the pool under a handful of concurrent calls.
    """
    from app.core.database import AsyncSessionLocal
    from app.services.voice.pipecat.pipeline_manager import pipeline_manager
    from app.models.voice_call import VoiceCall
    import json as _json

    token = websocket.query_params.get("token", "")
    if not _verify_pipecat_ws_token(voice_call_id, token):
        logger.warning("[PipecatWS] invalid/missing token call_id=%s — rejecting", voice_call_id)
        await websocket.close(code=1008)  # policy violation
        return

    await websocket.accept()
    logger.info("[PipecatWS] Twilio connected call_id=%s", voice_call_id)

    # Load call record to get mode + lead/broker context, then release the
    # pooled connection immediately — the pipeline uses its own sessions.
    async with AsyncSessionLocal() as db:
        call = await db.get(VoiceCall, voice_call_id)
        if call is not None:
            call_pipecat_mode = call.pipecat_mode
            call_lead_id = call.lead_id
            call_broker_id = call.broker_id
            call_agent_phone = call.agent_phone
            call_initiated_by_id = call.initiated_by_id
            call_external_id = call.external_call_id
            call_purpose = call.call_purpose
    if call is None:
        logger.warning("[PipecatWS] VoiceCall %s not found — closing", voice_call_id)
        await websocket.close(code=1011)
        return

    logger.info(
        "[PipecatWS] call loaded call_id=%s mode=%s lead=%s broker=%s ext_sid=%s",
        voice_call_id, call_pipecat_mode, call_lead_id, call_broker_id, call_external_id,
    )

    # Parse stream_sid from Twilio's 'start' event
    stream_sid = ""
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        msg = _json.loads(raw)
        logger.debug("[PipecatWS] first message event=%s call_id=%s", msg.get("event"), voice_call_id)
        if msg.get("event") == "connected":
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            msg = _json.loads(raw)
            logger.debug("[PipecatWS] second message event=%s call_id=%s", msg.get("event"), voice_call_id)
        if msg.get("event") == "start":
            stream_sid = msg.get("streamSid", "") or msg.get("start", {}).get("streamSid", "")
            logger.info("[PipecatWS] stream_sid=%s call_id=%s", stream_sid, voice_call_id)
        else:
            logger.warning("[PipecatWS] unexpected event=%s call_id=%s — proceeding without stream_sid", msg.get("event"), voice_call_id)
    except Exception as exc:
        logger.warning("[PipecatWS] Could not parse start event call_id=%s: %s", voice_call_id, exc)

    try:
        await _launch_pipecat_pipeline(
            call_id=voice_call_id,
            pipecat_mode=call_pipecat_mode or "autonomous",
            lead_id=call_lead_id,
            broker_id=call_broker_id,
            agent_phone=call_agent_phone,
            agent_user_id=call_initiated_by_id,
            twilio_call_sid=call_external_id or "",
            websocket=websocket,
            stream_sid=stream_sid,
            call_purpose=call_purpose,
        )
    except WebSocketDisconnect:
        logger.info("[PipecatWS] Twilio disconnected call_id=%s", voice_call_id)
    except Exception as exc:
        logger.error("[PipecatWS] pipeline error call_id=%s: %s", voice_call_id, exc, exc_info=True)
    finally:
        logger.info("[PipecatWS] session ended call_id=%s — stopping pipeline", voice_call_id)
        await pipeline_manager.stop(voice_call_id)


# ── Twilio status callback ─────────────────────────────────────────────────────

@router.post("/pipecat/status")
async def pipecat_twilio_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Twilio call status webhook — updates VoiceCall status in DB."""
    from app.models.voice_call import VoiceCall, CallStatus

    form = await _verify_twilio_request(request)
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")

    status_map = {
        "initiated": CallStatus.INITIATED,
        "ringing": CallStatus.RINGING,
        "in-progress": CallStatus.ANSWERED,
        "completed": CallStatus.COMPLETED,
        "failed": CallStatus.FAILED,
        "no-answer": CallStatus.NO_ANSWER,
        "busy": CallStatus.BUSY,
        "canceled": CallStatus.CANCELLED,
    }
    mapped = status_map.get(call_status)
    if mapped and call_sid:
        # Load the row once and reuse it for update + summary dispatch + broadcast.
        vc_result = await db.execute(
            select(VoiceCall).where(VoiceCall.external_call_id == call_sid)
        )
        vc = vc_result.scalars().first()
        if vc:
            vc.status = mapped
            if mapped in (CallStatus.COMPLETED, CallStatus.FAILED, CallStatus.NO_ANSWER, CallStatus.CANCELLED):
                vc.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Dispatch post-call summary for Pipecat calls on terminal states
            if mapped in (CallStatus.COMPLETED, CallStatus.FAILED, CallStatus.NO_ANSWER):
                if vc.pipecat_mode and not vc.post_processed:
                    try:
                        from app.tasks.voice_tasks import generate_pipecat_call_summary
                        generate_pipecat_call_summary.delay(vc.id)
                        logger.info("[PipecatStatus] queued summary for call_id=%s", vc.id)
                    except Exception as summary_err:
                        logger.warning("[PipecatStatus] summary dispatch failed: %s", summary_err)

            # WS broadcast for answered/ended transitions
            if mapped in (CallStatus.ANSWERED, CallStatus.COMPLETED, CallStatus.FAILED,
                          CallStatus.NO_ANSWER, CallStatus.CANCELLED):
                try:
                    from app.core.websocket_manager import ws_manager
                    if mapped == CallStatus.ANSWERED:
                        await ws_manager.broadcast(
                            broker_id=vc.broker_id,
                            event="call_answered",
                            data={"voice_call_id": vc.id, "lead_id": vc.lead_id},
                        )
                    else:
                        await ws_manager.broadcast(
                            broker_id=vc.broker_id,
                            event="call_ended",
                            data={"voice_call_id": vc.id, "status": mapped.value},
                        )
                except Exception as ws_err:
                    logger.warning("[PipecatStatus] WS broadcast failed: %s", ws_err)

    logger.info("[PipecatStatus] call_sid=%s status=%s", call_sid, call_status)
    return {"ok": True}


# ── Call start endpoints ───────────────────────────────────────────────────────

async def _create_and_initiate_pipecat_call(
    pipecat_mode: str,
    request: "PipecatCallRequest",
    db: AsyncSession,
    current_user: dict,
) -> "PipecatCallResponse":
    """
    Shared implementation for the four call-start endpoints (autonomous,
    copilot, coaching, handoff). Only the `pipecat_mode` string differs, so
    the body lives here once — consistent 404/403 semantics, tenant check,
    Twilio dial and WS broadcast for every mode.
    """
    from app.models.lead import Lead
    from app.models.voice_call import VoiceCall, CallStatus
    from app.services.voice.pipecat.telephony.twilio_handler import TwilioHandler

    lead = await db.get(Lead, request.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.broker_id != current_user["broker_id"]:
        raise HTTPException(status_code=403, detail="Lead belongs to different broker")

    call = VoiceCall(
        lead_id=request.lead_id,
        broker_id=current_user["broker_id"],
        phone_number=lead.phone or "",
        lead_phone=lead.phone,
        pipecat_mode=pipecat_mode,
        call_direction="outbound",
        initiated_by_id=int(current_user["user_id"]),
        agent_phone=request.agent_phone,
        call_purpose=request.call_purpose.value if request.call_purpose else None,
        status=CallStatus.INITIATED,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    # Initiate Twilio call — connects audio to our WebSocket
    try:
        handler = TwilioHandler()
        call_sid = await handler.initiate_call(
            to_number=lead.phone or "",
            websocket_url=_pipecat_ws_url(call.id),
            status_callback_url=_pipecat_status_url(),
        )
        call.external_call_id = call_sid
        await db.commit()
    except Exception as exc:
        logger.error("[Pipecat] Twilio initiate failed call_id=%s: %s", call.id, exc)
        raise HTTPException(status_code=502, detail=f"Could not initiate call: {exc}")

    # Pipeline is launched from the WebSocket endpoint when Twilio connects
    from app.core.websocket_manager import ws_manager
    await ws_manager.broadcast(
        broker_id=current_user["broker_id"],
        event="call_started",
        data={"voice_call_id": call.id, "pipecat_mode": pipecat_mode, "lead_id": request.lead_id},
    )
    return PipecatCallResponse(voice_call_id=call.id, pipecat_mode=pipecat_mode)


@router.post("/pipecat/autonomous", response_model=PipecatCallResponse, status_code=201)
async def start_autonomous_call(
    request: PipecatCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Start an autonomous AI call — AI calls lead and runs full qualification."""
    return await _create_and_initiate_pipecat_call("autonomous", request, db, current_user)


@router.post("/pipecat/autonomous/batch", status_code=202)
async def start_autonomous_batch(
    request: PipecatBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Start autonomous calls for multiple leads in parallel."""
    from app.models.lead import Lead
    from app.models.voice_call import VoiceCall, CallStatus
    from app.services.voice.pipecat.telephony.twilio_handler import TwilioHandler

    # Single query instead of N+1
    result = await db.execute(
        select(Lead).where(
            Lead.id.in_(request.lead_ids),
            Lead.broker_id == current_user["broker_id"],
        )
    )
    valid_leads = {lead.id: lead for lead in result.scalars().all()}

    handler = TwilioHandler()
    results = []
    for lead_id in request.lead_ids:
        lead = valid_leads.get(lead_id)
        if not lead:
            results.append({"lead_id": lead_id, "error": "not found or unauthorized"})
            continue
        call = VoiceCall(
            lead_id=lead_id,
            broker_id=current_user["broker_id"],
            phone_number=lead.phone or "",
            lead_phone=lead.phone,
            pipecat_mode="autonomous",
            call_direction="outbound",
            initiated_by_id=int(current_user["user_id"]),
            call_purpose=request.call_purpose.value if request.call_purpose else None,
            status=CallStatus.INITIATED,
        )
        db.add(call)
        results.append({"lead_id": lead_id, "status": "queued", "_lead": lead, "_call": call})

    await db.commit()

    # Fire calls after commit so call.id is set
    for item in results:
        if item.get("status") != "queued":
            continue
        lead = item.pop("_lead")
        call = item.pop("_call")
        if call:
            try:
                call_sid = await handler.initiate_call(
                    to_number=lead.phone or "",
                    websocket_url=_pipecat_ws_url(call.id),
                    status_callback_url=_pipecat_status_url(),
                )
                call.external_call_id = call_sid
                # Pipeline launched from WS endpoint when Twilio connects
                item["call_id"] = call.id
            except Exception as exc:
                item["error"] = str(exc)
                item["status"] = "failed"

    await db.commit()
    return {"queued": len([r for r in results if r.get("status") == "queued"]), "results": results}


@router.post("/pipecat/copilot", response_model=PipecatCallResponse, status_code=201)
async def start_copilot_call(
    request: PipecatCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Start copilot call — human calls lead, AI listens and takes notes."""
    return await _create_and_initiate_pipecat_call("copilot", request, db, current_user)


@router.post("/pipecat/coaching", response_model=PipecatCallResponse, status_code=201)
async def start_coaching_call(
    request: PipecatCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Start coaching call — human calls lead, AI suggests to agent in real-time."""
    return await _create_and_initiate_pipecat_call("coaching", request, db, current_user)


@router.post("/pipecat/handoff", response_model=PipecatCallResponse, status_code=201)
async def start_handoff_call(
    request: PipecatCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Start handoff call — AI calls lead, transfers to human if hot."""
    return await _create_and_initiate_pipecat_call("handoff", request, db, current_user)


@router.post("/pipecat/{voice_call_id}/transfer", status_code=200)
async def transfer_call_to_human(
    voice_call_id: int,
    body: PipecatTransferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Transfer active call to human agent mid-call."""
    from app.services.voice.pipecat.pipeline_manager import pipeline_manager
    from app.services.voice.pipecat.telephony.twilio_handler import TwilioHandler
    from app.models.voice_call import VoiceCall

    call = await db.get(VoiceCall, voice_call_id)
    if not call or call.broker_id != current_user["broker_id"]:
        raise HTTPException(status_code=404, detail="Call not found")
    if not pipeline_manager.is_active(voice_call_id):
        raise HTTPException(status_code=409, detail="Call is not active in Pipecat")

    pipeline_manager.mute_tts(voice_call_id)

    if call.external_call_id:
        handler = TwilioHandler()
        transferred = await handler.transfer_call(call.external_call_id, body.agent_phone)
        if not transferred:
            raise HTTPException(status_code=502, detail="Twilio transfer failed")

    return {"voice_call_id": voice_call_id, "status": "transfer_initiated", "agent_phone": body.agent_phone}


@router.post("/pipecat/{voice_call_id}/end", status_code=200)
async def end_pipecat_call(
    voice_call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """End an active Pipecat call."""
    from app.services.voice.pipecat.pipeline_manager import pipeline_manager
    from app.models.voice_call import VoiceCall, CallStatus
    from app.services.voice.pipecat.telephony.twilio_handler import TwilioHandler
    from sqlalchemy import update as sa_update

    call = await db.get(VoiceCall, voice_call_id)
    if not call or call.broker_id != current_user["broker_id"]:
        raise HTTPException(status_code=404, detail="Call not found")

    stopped = await pipeline_manager.stop(voice_call_id)

    # End Twilio call if still active
    if call.external_call_id:
        try:
            await TwilioHandler().end_call(call.external_call_id)
        except Exception as exc:
            logger.warning("[Pipecat] end_call Twilio error call_id=%s: %s", voice_call_id, exc)

    await db.execute(
        sa_update(VoiceCall)
        .where(VoiceCall.id == voice_call_id)
        .values(status=CallStatus.COMPLETED, completed_at=datetime.now(timezone.utc))
    )
    await db.commit()

    from app.core.websocket_manager import ws_manager
    await ws_manager.broadcast(
        broker_id=current_user["broker_id"],
        event="call_ended",
        data={"voice_call_id": voice_call_id},
    )

    # Queue post-call summary if Pipecat call
    if call.pipecat_mode and not call.post_processed:
        try:
            from app.tasks.voice_tasks import generate_pipecat_call_summary
            generate_pipecat_call_summary.delay(voice_call_id)
        except Exception as exc:
            logger.warning("[Pipecat] summary dispatch failed call_id=%s: %s", voice_call_id, exc)

    return {"voice_call_id": voice_call_id, "stopped": stopped}


async def _assert_call_in_broker(voice_call_id: int, db: AsyncSession, current_user: dict) -> None:
    """Reject if the call doesn't exist or belongs to another broker.

    pipeline_manager keys tasks only by voice_call_id (no tenant info), so
    call-control endpoints must load the row and check broker_id themselves —
    otherwise a user could mute/unmute a live call in another tenant.
    """
    from app.models.voice_call import VoiceCall
    call = await db.get(VoiceCall, voice_call_id)
    if not call or call.broker_id != current_user["broker_id"]:
        raise HTTPException(status_code=404, detail="Call not found")


@router.post("/pipecat/{voice_call_id}/mute-ai", status_code=200)
async def mute_ai_voice(
    voice_call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mute AI TTS — AI stops responding but keeps listening."""
    from app.services.voice.pipecat.pipeline_manager import pipeline_manager
    await _assert_call_in_broker(voice_call_id, db, current_user)
    if not pipeline_manager.mute_tts(voice_call_id):
        raise HTTPException(status_code=404, detail="Active call not found")
    return {"voice_call_id": voice_call_id, "ai_muted": True}


@router.post("/pipecat/{voice_call_id}/unmute-ai", status_code=200)
async def unmute_ai_voice(
    voice_call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Unmute AI TTS — AI resumes responding."""
    from app.services.voice.pipecat.pipeline_manager import pipeline_manager
    await _assert_call_in_broker(voice_call_id, db, current_user)
    if not pipeline_manager.unmute_tts(voice_call_id):
        raise HTTPException(status_code=404, detail="Active call not found")
    return {"voice_call_id": voice_call_id, "ai_muted": False}


# ── Inbound call TwiML endpoint ────────────────────────────────────────────────

@router.post("/pipecat/twiml/inbound")
async def pipecat_twiml_inbound(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    TwiML webhook for inbound calls to the Twilio number.

    When someone calls the Twilio phone number, Twilio POSTs here.
    We create a VoiceCall record and return TwiML that connects the
    audio stream to the Pipecat WebSocket pipeline.

    Set this URL in your Twilio number:
        Voice → A call comes in → Webhook → POST
        {WEBHOOK_BASE_URL}/api/v1/calls/pipecat/twiml/inbound

    Twilio form fields used:
        - From: caller's phone number (used to find or create a lead)
        - To:   your Twilio number
        - CallSid: Twilio call SID
    """
    from fastapi.responses import Response as FastAPIResponse
    from app.models.voice_call import VoiceCall, CallStatus
    from app.models.lead import Lead
    from sqlalchemy.future import select as sa_select

    form = await _verify_twilio_request(request)
    caller_number = form.get("From", "")
    twilio_number = form.get("To", "")
    call_sid = form.get("CallSid", "")

    logger.info(
        "[InboundTwiML] call_sid=%s from=%s to=%s",
        call_sid, caller_number, twilio_number,
    )

    # Resolve broker from the called Twilio number (E.164); env var is fallback only.
    # Match on twilio_phone_number — NOT phone_number_id, which is a VAPI id.
    default_broker_id: Optional[int] = None
    if twilio_number:
        cfg_result = await db.execute(
            select(BrokerVoiceConfig).where(
                BrokerVoiceConfig.twilio_phone_number == twilio_number
            )
        )
        cfg = cfg_result.scalars().first()
        if cfg:
            default_broker_id = cfg.broker_id
    if default_broker_id is None:
        default_broker_id = int(os.getenv("TWILIO_DEFAULT_BROKER_ID", "1"))
        logger.warning(
            "[InboundTwiML] no BrokerVoiceConfig.twilio_phone_number for number=%s — "
            "falling back to TWILIO_DEFAULT_BROKER_ID=%s", twilio_number, default_broker_id,
        )

    # Try to find an existing lead by phone number, or create one
    lead_id: int = 0
    try:
        result = await db.execute(
            sa_select(Lead)
            .where(Lead.phone == caller_number, Lead.broker_id == default_broker_id)
            .limit(1)
        )
        lead = result.scalars().first()
        if lead:
            lead_id = lead.id
            logger.info("[InboundTwiML] matched lead_id=%s for phone=%s", lead_id, caller_number)
        else:
            # Create a new lead for the caller so the VoiceCall FK is satisfied
            new_lead = Lead(
                phone=caller_number,
                broker_id=default_broker_id,
                name=f"Llamada entrante {caller_number}",
                lead_metadata={"source": "inbound_call"},
            )
            db.add(new_lead)
            await db.flush()  # get the id without committing
            lead_id = new_lead.id
            logger.info("[InboundTwiML] created new lead_id=%s for phone=%s", lead_id, caller_number)
    except Exception as exc:
        logger.error("[InboundTwiML] lead lookup/create failed: %s", exc)
        twiml_error = '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="es-MX">Lo sentimos, hubo un error. Por favor intente más tarde.</Say><Hangup/></Response>'
        return FastAPIResponse(content=twiml_error, media_type="application/xml")

    # Create VoiceCall record
    call: Optional[VoiceCall] = None
    try:
        call = VoiceCall(
            lead_id=lead_id,
            broker_id=default_broker_id,
            phone_number=caller_number,
            lead_phone=caller_number,
            pipecat_mode="autonomous",
            call_direction="inbound",
            external_call_id=call_sid,
            status=CallStatus.RINGING,
        )
        db.add(call)
        await db.commit()
        await db.refresh(call)
        logger.info("[InboundTwiML] created VoiceCall id=%s call_sid=%s lead_id=%s", call.id, call_sid, lead_id)
    except Exception as exc:
        logger.error("[InboundTwiML] DB create failed: %s", exc)
        # Return hold music TwiML so caller doesn't hear silence
        twiml_error = '<?xml version="1.0" encoding="UTF-8"?><Response><Say language="es-MX">Lo sentimos, hubo un error. Por favor intente más tarde.</Say><Hangup/></Response>'
        return FastAPIResponse(content=twiml_error, media_type="application/xml")

    # Build WebSocket URL for this call
    ws_url = _pipecat_ws_url(call.id)

    logger.info("[InboundTwiML] ws_url=%s call_id=%s", ws_url, call.id)

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}">
      <Parameter name="call_id" value="{call.id}"/>
    </Stream>
  </Connect>
</Response>"""

    return FastAPIResponse(content=twiml, media_type="application/xml")


@router.get("/pipecat/{voice_call_id}/transcript")
async def get_pipecat_transcript(
    voice_call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get full transcript for a call."""
    from app.models.voice_call import VoiceCall, CallTranscript
    from sqlalchemy import asc

    call = await db.get(VoiceCall, voice_call_id)
    if not call or call.broker_id != current_user["broker_id"]:
        raise HTTPException(status_code=404, detail="Call not found")

    result = await db.execute(
        select(CallTranscript)
        .where(CallTranscript.voice_call_id == voice_call_id)
        .order_by(asc(CallTranscript.timestamp))
    )
    lines = result.scalars().all()

    return {
        "voice_call_id": voice_call_id,
        "pipecat_mode": call.pipecat_mode,
        "lines": [
            {
                "speaker": line.speaker.value,
                "text": line.text,
                "timestamp": line.timestamp,
                "emotion_tag_used": line.emotion_tag_used,
                "emotion_detected": line.emotion_detected,
            }
            for line in lines
        ],
    }


@router.get("/pipecat/{voice_call_id}/summary")
async def get_pipecat_call_summary(
    voice_call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get AI-generated summary and extracted data for a call."""
    from app.models.voice_call import VoiceCall

    call = await db.get(VoiceCall, voice_call_id)
    if not call or call.broker_id != current_user["broker_id"]:
        raise HTTPException(status_code=404, detail="Call not found")

    return {
        "voice_call_id": voice_call_id,
        "summary": call.summary,
        "extracted_data": call.extracted_data,
        "call_metrics": call.call_metrics,
        "handoff_occurred": call.handoff_occurred,
        "handoff_reason": call.handoff_reason,
    }


@router.get("/voices")
async def list_fish_voices(
    current_user: dict = Depends(get_current_user),
):
    """List Fish Audio cloned voices."""
    import os
    import aiohttp

    api_key = os.getenv("FISH_AUDIO_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="FISH_AUDIO_API_KEY not configured")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.fish.audio/model",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=502, detail="Fish Audio API error")
                data = await resp.json()
        return {"voices": data}
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=502, detail=f"Fish Audio API unreachable: {exc}")


@router.post("/voices/clone", status_code=201)
async def clone_fish_voice(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Clone a voice from a 15-30 second audio sample. Multipart: audio file + name."""
    import os
    import aiohttp

    api_key = os.getenv("FISH_AUDIO_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="FISH_AUDIO_API_KEY not configured")

    form = await request.form()
    audio_file = form.get("audio")
    voice_name = form.get("name", f"broker_{current_user['broker_id']}_voice")
    if not audio_file:
        raise HTTPException(status_code=400, detail="audio file required")

    audio_bytes = await audio_file.read()
    try:
        async with aiohttp.ClientSession() as session:
            form_data = aiohttp.FormData()
            form_data.add_field("title", str(voice_name))
            form_data.add_field(
                "voices",
                audio_bytes,
                filename=getattr(audio_file, "filename", "sample.wav") or "sample.wav",
                content_type=getattr(audio_file, "content_type", "audio/wav") or "audio/wav",
            )
            async with session.post(
                "https://api.fish.audio/model",
                headers={"Authorization": f"Bearer {api_key}"},
                data=form_data,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status not in (200, 201):
                    error = await resp.text()
                    raise HTTPException(status_code=502, detail=f"Fish Audio clone failed: {error}")
                result = await resp.json()
        return {"voice_id": result.get("_id"), "name": voice_name, "status": "cloned"}
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=502, detail=f"Fish Audio API error: {exc}")
