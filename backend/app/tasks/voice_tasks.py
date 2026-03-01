"""
Voice call processing tasks for Celery
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

# Create async engine for tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


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
        async with AsyncSessionLocal() as db:
            try:
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

                await VoiceCallService.update_call_transcript(
                    db=db,
                    voice_call_id=voice_call.id,
                    transcript=transcript or "",
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
                    full_transcript=transcript or "",
                    lead_context=lead_context,
                )

                await VoiceCallService.update_call_summary(
                    db=db,
                    voice_call_id=voice_call.id,
                    summary=summary_data.get("summary", ""),
                    score_delta=summary_data.get("score_delta", 0),
                    stage_after_call=summary_data.get("stage_to_move"),
                )

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

    try:
        asyncio.run(_process())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

