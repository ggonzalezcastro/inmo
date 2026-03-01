"""
Voice call routes for managing phone calls
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, Any
from pydantic import BaseModel
from app.core.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.voice import VoiceCallService
from app.services.voice.call_service import handle_tool_call
from app.services.voice.types import CallEventType
from app.schemas.voice_call import (
    VoiceCallResponse,
    VoiceCallListResponse,
    CallInitiateRequest
)
from app.models.broker_voice_config import BrokerVoiceConfig
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


async def _handle_vapi_webhook(
    payload: dict,
    db: AsyncSession,
    provider: Any,
    headers: Optional[dict] = None,
) -> dict:
    """
    Shared VAPI webhook dispatch. Returns a dict to be returned as JSON.
    Always return HTTP 200 to VAPI; use dict for body.
    """
    # C1: Verify Vapi webhook signature when secret is configured.
    if settings.VAPI_WEBHOOK_SECRET:
        token = (headers or {}).get("x-vapi-secret") or ""
        if token != settings.VAPI_WEBHOOK_SECRET:
            logger.warning("Vapi webhook: invalid secret, rejecting request")
            return {"error": "Unauthorized"}

    try:
        raw_event = await provider.handle_webhook(payload, headers=headers or {})

        if not raw_event.external_call_id and raw_event.event_type != CallEventType.ASSISTANT_REQUEST:
            return {"ok": True}

        if raw_event.event_type == CallEventType.TOOL_CALLS:
            tool_calls_data = raw_event.tool_calls_data or []
            results = []
            for item in tool_calls_data:
                name = item.get("name") or ""
                tool_call_id = item.get("tool_call_id") or item.get("toolCall", {}).get("id") or ""
                params = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
                result_str = await handle_tool_call(name, tool_call_id, params)
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
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    from app.services.voice.factory import get_voice_provider as get_provider_async
    provider = await get_provider_async(provider_type=provider_name, db=db)
    body = await _handle_vapi_webhook(
        payload, db, provider, headers=dict(request.headers)
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
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    from app.services.voice.factory import get_voice_provider as get_provider_async
    provider = await get_provider_async(provider_type="vapi", db=db)
    body = await _handle_vapi_webhook(payload, db, provider, headers=dict(request.headers))
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



