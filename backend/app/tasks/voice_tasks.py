"""
Voice call processing tasks for Celery.

POOL REQUIREMENT: These tasks use asyncio.run() to run async SQLAlchemy sessions.
This is compatible ONLY with Celery's prefork pool (default).
Do NOT run these workers with --pool=gevent or --pool=eventlet.

Start workers with:
    celery -A app.celery_app worker --pool=prefork --loglevel=info
"""
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from datetime import datetime
import logging
from app.config import settings
from app.models.voice_call import VoiceCall
from app.services.voice import CallAgentService, VoiceCallService
from app.services.pipeline import PipelineService
from app.tasks.base import DLQTask

logger = logging.getLogger(__name__)

# Engine created per-task inside _process() to avoid asyncpg loop mismatch on Celery fork.


@shared_task(name="app.tasks.voice_tasks.generate_call_transcript_and_summary")
def generate_call_transcript_and_summary(voice_call_id: int):
    """DEPRECATED: Vapi sends the full transcript in the end-of-call-report webhook.
    Use process_end_of_call_report instead. This task is a no-op."""
    logger.warning(
        "generate_call_transcript_and_summary is deprecated and does nothing. "
        "Transcript is received via end-of-call-report webhook. voice_call_id=%s",
        voice_call_id,
    )
    return {"status": "deprecated", "voice_call_id": voice_call_id}


@shared_task(
    base=DLQTask,
    bind=True,
    max_retries=3,
    name="app.tasks.voice_tasks.process_end_of_call_report",
)
def process_end_of_call_report(
    self,
    external_call_id: str,
    transcript: str,
    artifact_messages: list,
    ended_reason,
    recording_url,
):
    """
    Process VAPI end-of-call-report: update transcript, generate summary, update lead.
    Called when VAPI sends end-of-call-report webhook with full transcript and artifact.
    """
    import asyncio

    async def _process():
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as db:
                result = await db.execute(
                    select(VoiceCall).where(
                        VoiceCall.external_call_id == external_call_id
                    )
                )
                voice_call = result.scalars().first()

                if not voice_call:
                    logger.error(
                        "Voice call not found for external_call_id=%s",
                        external_call_id,
                    )
                    return

                if voice_call.post_processed:
                    logger.info(
                        "Call %s already processed, skipping.", external_call_id
                    )
                    return

                MAX_TRANSCRIPT_CHARS = 12_000
                effective_transcript = transcript or ""
                if len(effective_transcript) > MAX_TRANSCRIPT_CHARS:
                    logger.warning(
                        "Transcript for call %s exceeds %d chars (%d), truncating.",
                        external_call_id,
                        MAX_TRANSCRIPT_CHARS,
                        len(effective_transcript),
                    )
                    effective_transcript = (
                        effective_transcript[:MAX_TRANSCRIPT_CHARS] + "\n[TRANSCRIPT TRUNCADO]"
                    )

                await VoiceCallService.update_call_transcript(
                    db=db,
                    voice_call_id=voice_call.id,
                    transcript=effective_transcript,
                )

                await VoiceCallService.store_transcript_lines(
                    db=db,
                    voice_call_id=voice_call.id,
                    artifact_messages=artifact_messages or [],
                    transcript_text=effective_transcript,
                )

                if recording_url:
                    voice_call.recording_url = recording_url
                    await db.commit()
                    await db.refresh(voice_call)

                from app.models.lead import Lead

                lead_result = await db.execute(
                    select(Lead).where(Lead.id == voice_call.lead_id)
                )
                lead = lead_result.scalars().first()

                if not lead:
                    logger.error("Lead %s not found", voice_call.lead_id)
                    return

                lead_context = {
                    "id": lead.id,
                    "name": lead.name,
                    "phone": lead.phone,
                    "email": lead.email,
                    "lead_score": lead.lead_score,
                    "pipeline_stage": lead.pipeline_stage,
                    "lead_metadata": lead.lead_metadata or {},
                }

                summary_data = await CallAgentService.generate_call_summary(
                    full_transcript=effective_transcript,
                    lead_context=lead_context,
                )

                await VoiceCallService.update_call_summary(
                    db=db,
                    voice_call_id=voice_call.id,
                    summary=summary_data.get("summary", ""),
                    score_delta=summary_data.get("score_delta", 0),
                    stage_after_call=summary_data.get("stage_to_move"),
                )

                # IMPORTANT: merge with existing call_output — live tool-call data
                # (written by handle_tool_call during the call) takes priority over
                # LLM-extracted fallback values. Never overwrite non-null fields.
                if voice_call.call_purpose:
                    extracted = _extract_call_output(
                        voice_call.call_purpose, summary_data, effective_transcript
                    )
                    existing_output = dict(voice_call.call_output or {})
                    existing_output.pop("_processed_tool_calls", None)
                    merged_output = {
                        **extracted,
                        **{k: v for k, v in existing_output.items() if v is not None},
                    }
                    voice_call.call_output = merged_output
                    await db.commit()
                    await db.refresh(voice_call)

                if summary_data.get("budget"):
                    if not isinstance(lead.lead_metadata, dict):
                        lead.lead_metadata = {}
                    lead.lead_metadata["budget"] = summary_data["budget"]

                if summary_data.get("timeline"):
                    if not isinstance(lead.lead_metadata, dict):
                        lead.lead_metadata = {}
                    lead.lead_metadata["timeline"] = summary_data["timeline"]

                if summary_data.get("score_delta"):
                    old_score = lead.lead_score
                    new_score = max(
                        0,
                        min(100, old_score + summary_data["score_delta"]),
                    )
                    lead.lead_score = new_score

                if summary_data.get("stage_to_move"):
                    try:
                        await PipelineService.move_lead_to_stage(
                            db=db,
                            lead_id=lead.id,
                            new_stage=summary_data["stage_to_move"],
                            reason="Call summary recommendation",
                            triggered_by_campaign=voice_call.campaign_id,
                        )
                    except Exception as e:
                        logger.error(
                            "Error moving lead to stage: %s", str(e)
                        )

                voice_call.post_processed = True
                await db.commit()
                logger.info(
                    "End-of-call-report processed for external_call_id=%s",
                    external_call_id,
                )
        except Exception as e:
            logger.error(
                "Error in process_end_of_call_report: %s",
                str(e),
                exc_info=True,
            )
            raise
        finally:
            await engine.dispose()

    try:
        asyncio.run(_process())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(
    base=DLQTask,
    bind=True,
    max_retries=3,
    name="app.tasks.voice_tasks.generate_pipecat_call_summary",
)
def generate_pipecat_call_summary(self, voice_call_id: int):
    """
    Post-call processing for Pipecat-based calls.

    Triggered after a Pipecat call ends (Twilio status=completed or manual /end).
    Assembles full transcript from call_transcripts lines, calls LLM for summary,
    then updates voice_calls.summary / extracted_data / call_metrics and lead record.
    """
    import asyncio

    async def _process():
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as db:
                voice_call = await db.get(VoiceCall, voice_call_id)
                if not voice_call:
                    logger.error("[PipecatSummary] VoiceCall %s not found", voice_call_id)
                    return
                if voice_call.post_processed:
                    logger.info("[PipecatSummary] Call %s already processed, skipping", voice_call_id)
                    return

                from app.models.voice_call import CallTranscript, SpeakerType
                from sqlalchemy import asc as _asc
                result = await db.execute(
                    select(CallTranscript)
                    .where(CallTranscript.voice_call_id == voice_call_id)
                    .order_by(_asc(CallTranscript.timestamp))
                )
                lines = result.scalars().all()

                if not lines:
                    logger.warning("[PipecatSummary] No transcript lines for call %s", voice_call_id)
                    voice_call.post_processed = True
                    await db.commit()
                    return

                _speaker_label = {
                    SpeakerType.CUSTOMER: "Lead",
                    SpeakerType.BOT: "IA",
                    SpeakerType.AGENT: "Agente",
                }
                transcript_text = "\n".join(
                    f"{_speaker_label.get(l.speaker, 'Desconocido')}: {l.text}"
                    for l in lines
                )
                MAX_CHARS = 12_000
                if len(transcript_text) > MAX_CHARS:
                    logger.warning(
                        "[PipecatSummary] Truncating transcript call=%s (%d chars)",
                        voice_call_id, len(transcript_text),
                    )
                    transcript_text = transcript_text[:MAX_CHARS] + "\n[TRANSCRIPT TRUNCADO]"

                voice_call.transcript = transcript_text
                await db.commit()
                await db.refresh(voice_call)

                from app.models.lead import Lead
                lead = await db.get(Lead, voice_call.lead_id)
                if not lead:
                    logger.error("[PipecatSummary] Lead %s not found", voice_call.lead_id)
                    return

                lead_context = {
                    "id": lead.id,
                    "name": lead.name,
                    "phone": lead.phone,
                    "email": lead.email,
                    "lead_score": lead.lead_score,
                    "pipeline_stage": lead.pipeline_stage,
                    "lead_metadata": lead.lead_metadata or {},
                }

                summary_data = await CallAgentService.generate_call_summary(
                    full_transcript=transcript_text,
                    lead_context=lead_context,
                )

                await VoiceCallService.update_call_summary(
                    db=db,
                    voice_call_id=voice_call_id,
                    summary=summary_data.get("summary", ""),
                    score_delta=summary_data.get("score_delta", 0),
                    stage_after_call=summary_data.get("stage_to_move"),
                )

                voice_call.extracted_data = {
                    "sentiment": summary_data.get("sentiment"),
                    "interest_level": summary_data.get("interest_level"),
                    "objections": summary_data.get("objections"),
                    "commitments": summary_data.get("commitments"),
                    "next_steps": summary_data.get("next_steps"),
                    "budget": summary_data.get("budget"),
                    "timeline": summary_data.get("timeline"),
                }

                metrics = dict(voice_call.call_metrics or {})
                metrics.update({
                    "tts_provider": "pipecat",
                    "transcript_lines": len(lines),
                    "ai_lines": sum(1 for l in lines if l.speaker == SpeakerType.BOT),
                    "lead_lines": sum(1 for l in lines if l.speaker == SpeakerType.CUSTOMER),
                    "human_lines": sum(1 for l in lines if l.speaker == SpeakerType.AGENT),
                })
                voice_call.call_metrics = metrics
                await db.commit()
                await db.refresh(voice_call)

                from sqlalchemy.orm.attributes import flag_modified
                if summary_data.get("score_delta"):
                    lead.lead_score = max(0, min(100, lead.lead_score + summary_data["score_delta"]))
                if summary_data.get("budget"):
                    if not isinstance(lead.lead_metadata, dict):
                        lead.lead_metadata = {}
                    lead.lead_metadata["budget"] = summary_data["budget"]
                    flag_modified(lead, "lead_metadata")
                if summary_data.get("timeline"):
                    if not isinstance(lead.lead_metadata, dict):
                        lead.lead_metadata = {}
                    lead.lead_metadata["timeline"] = summary_data["timeline"]
                    flag_modified(lead, "lead_metadata")

                if summary_data.get("stage_to_move"):
                    try:
                        await PipelineService.move_lead_to_stage(
                            db=db,
                            lead_id=lead.id,
                            new_stage=summary_data["stage_to_move"],
                            reason="Pipecat call summary",
                            triggered_by_campaign=voice_call.campaign_id,
                        )
                    except Exception as exc:
                        logger.error("[PipecatSummary] Stage move failed: %s", exc)

                voice_call.post_processed = True
                await db.commit()
                logger.info("[PipecatSummary] Call %s processed successfully", voice_call_id)
        except Exception as exc:
            logger.error("[PipecatSummary] Error: %s", exc, exc_info=True)
            raise
        finally:
            await engine.dispose()

    try:
        asyncio.run(_process())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


def _extract_call_output(call_purpose: str, summary: dict, transcript: str) -> dict:
    """
    Map LLM summary fields to a structured JSONB shape keyed by call_purpose.
    The LLM summary (CallAgentService.generate_call_summary) already extracts
    most data; this normalises it into a consistent schema per purpose.
    """
    base = {
        "summary": summary.get("summary"),
        "interest_level": summary.get("interest_level"),
        "next_steps": summary.get("next_steps"),
    }

    if call_purpose == "calificacion_inicial":
        return {
            **base,
            "presupuesto": summary.get("budget"),
            "zona": None,
            "tipo_propiedad": None,
            "disponibilidad_visita": None,
        }

    if call_purpose == "calificacion_financiera":
        return {
            **base,
            "ingresos": None,
            "capacidad_pago": None,
            "pre_aprobacion": None,
        }

    if call_purpose in ("confirmacion_visita", "confirmacion_reunion"):
        return {
            **base,
            "confirmo_asistencia": None,
            "nueva_fecha_propuesta": None,
            "motivo_rechazo": None,
        }

    if call_purpose == "seguimiento_post_visita":
        return {
            **base,
            "nivel_interes_actualizado": summary.get("interest_level"),
            "objeciones": None,
        }

    if call_purpose == "reactivacion":
        return {
            **base,
            "respondio_llamada": None,
            "sigue_interesado": None,
            "nuevo_contexto": None,
        }

    return base
