from celery import shared_task
from app.tasks.base import DLQTask
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.services.leads import ScoringService
from app.services.leads.response_metrics import (
    apply_fast_responder_tag,
    compute_response_metrics,
)
from app.services.shared import ActivityService
from app.models.lead import Lead, LeadStatus

logger = logging.getLogger(__name__)

# Create async engine for tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(
    name="app.tasks.scoring_tasks.recalculate_all_lead_scores",
    base=DLQTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def recalculate_all_lead_scores(self):
    """Recalculate scores for all leads - runs daily. Uses eager loading to avoid N+1."""
    
    import asyncio
    
    async def async_recalculate():
        async with AsyncSessionLocal() as db:
            try:
                logger.info("Starting daily score recalculation")
                
                # Load all active leads with messages and activities in one query (avoid N+1)
                result = await db.execute(
                    select(Lead)
                    .where(Lead.status != LeadStatus.CONVERTED)
                    .options(
                        selectinload(Lead.telegram_messages),
                        selectinload(Lead.activities),
                    )
                )
                leads = result.scalars().all()
                
                updated_count = 0
                activities_to_log = []
                hot_advanced_leads = []  # leads that just became HOT and may need stage advance
                # Per-lead response metrics to persist atomically AFTER batch commit
                # (avoid sobrescribir writes concurrentes a otras keys de lead_metadata).
                metrics_to_persist: list[dict] = []
                
                for lead in leads:
                    try:
                        broker_id = lead.broker_id
                        score_data = await ScoringService.calculate_lead_score_from_lead(
                            db, lead, broker_id
                        )
                        old_score = lead.lead_score
                        new_score = score_data["total"]
                        old_status = lead.status
                        
                        lead.lead_score = new_score
                        lead.lead_score_components = {
                            "base": score_data["base"],
                            "behavior": score_data["behavior"],
                            "engagement": score_data["engagement"]
                        }
                        
                        from app.services.broker import BrokerConfigService
                        
                        if broker_id:
                            status_str = await BrokerConfigService.determine_lead_status(
                                db, new_score, broker_id
                            )
                            if status_str == "cold":
                                lead.status = LeadStatus.COLD
                            elif status_str == "warm":
                                lead.status = LeadStatus.WARM
                            else:
                                lead.status = LeadStatus.HOT
                        else:
                            if new_score < 20:
                                lead.status = LeadStatus.COLD
                            elif new_score < 50:
                                lead.status = LeadStatus.WARM
                            else:
                                lead.status = LeadStatus.HOT
                        
                        # Track leads that just became HOT for pipeline auto-advance
                        if (lead.status == LeadStatus.HOT
                                and old_status != LeadStatus.HOT
                                and lead.pipeline_stage in ["perfilamiento", "calificacion_financiera"]):
                            hot_advanced_leads.append(lead.id)
                        
                        if new_score != old_score:
                            updated_count += 1
                            activities_to_log.append({
                                "lead_id": lead.id,
                                "old_score": old_score,
                                "new_score": new_score,
                                "score_data": score_data,
                            })

                        # Reconcile fast-responder metrics + tag (backfill
                        # for leads that existed before the on_message hook).
                        # IMPORTANT: persist metrics via jsonb_set AFTER batch commit
                        # to avoid clobbering concurrent writes (e.g. sentiment task)
                        # to other lead_metadata keys.
                        try:
                            metrics = compute_response_metrics(
                                list(lead.telegram_messages or [])
                            )
                            new_tags, tag_changed = apply_fast_responder_tag(
                                lead.tags, metrics
                            )
                            if tag_changed:
                                lead.tags = new_tags
                            metrics_to_persist.append({
                                "lead_id": lead.id,
                                "metrics": metrics,
                                "tag_changed": tag_changed,
                                "applied": new_tags and "respuesta_rapida" in new_tags,
                            })
                        except Exception as _rm_exc:
                            logger.error(
                                "Error computing response metrics for lead %s: %s",
                                lead.id, _rm_exc,
                            )
                    
                    except Exception as e:
                        logger.error(f"Error recalculating score for lead {lead.id}: {str(e)}")
                        continue
                
                # Single batch commit for all lead updates
                try:
                    await db.commit()
                except Exception as e:
                    logger.error(f"Batch commit failed: {str(e)}", exc_info=True)
                    await db.rollback()
                    return
                
                # Trigger pipeline auto-advance for leads that just became HOT
                if hot_advanced_leads:
                    from app.services.pipeline.advancement_service import auto_advance_stage
                    for lead_id in hot_advanced_leads:
                        try:
                            await auto_advance_stage(db, lead_id)
                        except Exception as e:
                            logger.error(f"Error auto-advancing HOT lead {lead_id}: {str(e)}")
                
                # Persist response_metrics atomically per-lead (jsonb_set) so we
                # don't clobber concurrent writes to other lead_metadata keys.
                if metrics_to_persist:
                    import json as _json_rm
                    from sqlalchemy import text as _sa_text_rm
                    for item in metrics_to_persist:
                        try:
                            await db.execute(
                                _sa_text_rm(
                                    "UPDATE leads SET metadata = "
                                    "jsonb_set(COALESCE(metadata, '{}'::jsonb), "
                                    "ARRAY['response_metrics'], CAST(:m AS jsonb), true) "
                                    "WHERE id = :lid"
                                ),
                                {"m": _json_rm.dumps(item["metrics"]), "lid": item["lead_id"]},
                            )
                        except Exception as _persist_exc:
                            logger.error(
                                "Error persisting response_metrics for lead %s: %s",
                                item["lead_id"], _persist_exc,
                            )
                    try:
                        await db.commit()
                    except Exception as _mc_exc:
                        logger.error(f"response_metrics commit failed: {_mc_exc}")
                        await db.rollback()
                
                # Log activities after commit (each log_activity may commit)
                for item in activities_to_log:
                    try:
                        await ActivityService.log_activity(
                            db,
                            lead_id=item["lead_id"],
                            action_type="score_update",
                            details={
                                "old_score": item["old_score"],
                                "new_score": item["new_score"],
                                "reason": "daily_recalculation",
                                "components": item["score_data"]
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error logging activity for lead {item['lead_id']}: {str(e)}")
                
                logger.info(f"Recalculation complete: {updated_count} leads updated")
                
            except Exception as e:
                logger.error(f"Error in recalculate_all_lead_scores: {str(e)}", exc_info=True)
                try:
                    await db.rollback()
                except Exception:
                    pass
    
    asyncio.run(async_recalculate())

