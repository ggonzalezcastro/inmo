"""
Pipeline advancement: move lead to stage, auto-advance, update stage from lead data.
"""
from datetime import datetime
from typing import Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc

from app.models.lead import Lead
from app.models.campaign import Campaign, CampaignTrigger
from app.services.shared import ActivityService
from app.services.pipeline.constants import PIPELINE_STAGES

logger = logging.getLogger(__name__)


async def move_lead_to_stage(
    db: AsyncSession,
    lead_id: int,
    new_stage: str,
    reason: Optional[str] = None,
    triggered_by_campaign: Optional[int] = None,
) -> Lead:
    """
    Move a lead to a new pipeline stage.
    """
    if new_stage not in PIPELINE_STAGES:
        raise ValueError(
            f"Invalid pipeline stage: {new_stage}. Valid stages: {list(PIPELINE_STAGES.keys())}"
        )

    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalars().first()
    if not lead:
        raise ValueError(f"Lead {lead_id} not found")

    old_stage = lead.pipeline_stage
    lead.pipeline_stage = new_stage
    lead.stage_entered_at = datetime.now().replace(tzinfo=lead.created_at.tzinfo)
    await db.commit()

    await ActivityService.log_activity(
        db,
        lead_id=lead_id,
        action_type="stage_change",
        details={
            "old_stage": old_stage,
            "new_stage": new_stage,
            "reason": reason or "Manual update",
            "triggered_by_campaign": triggered_by_campaign,
            "stage_entered_at": lead.stage_entered_at.isoformat(),
        },
    )
    logger.info(f"Lead {lead_id} moved from {old_stage} to {new_stage}. Reason: {reason}")

    # Broadcast stage_changed via WebSocket (TASK-027)
    if lead.broker_id and old_stage != new_stage:
        try:
            from app.core.websocket_manager import ws_manager
            await ws_manager.broadcast(lead.broker_id, "stage_changed", {
                "lead_id": lead_id,
                "old_stage": old_stage,
                "new_stage": new_stage,
                "reason": reason,
            })
        except Exception as _ws_exc:
            logger.debug("[WS] stage_changed broadcast error: %s", _ws_exc)

    await _trigger_stage_campaigns(db, lead, new_stage)
    await db.refresh(lead)
    return lead


async def _trigger_stage_campaigns(
    db: AsyncSession,
    lead: Lead,
    new_stage: str,
) -> None:
    """Trigger campaigns configured for stage_change trigger."""
    try:
        campaigns_result = await db.execute(
            select(Campaign).where(
                and_(
                    Campaign.status == "active",
                    Campaign.triggered_by == CampaignTrigger.STAGE_CHANGE,
                )
            )
        )
        campaigns = campaigns_result.scalars().all()

        for campaign in campaigns:
            condition = campaign.trigger_condition or {}
            target_stage = condition.get("stage")
            if target_stage != new_stage:
                continue

            from app.services.campaigns import CampaignService

            campaign_history = lead.campaign_history or []
            already_applied = any(
                log.get("campaign_id") == campaign.id for log in campaign_history
            )
            if already_applied:
                continue

            try:
                await CampaignService.apply_campaign_to_lead(db, campaign.id, lead.id)
                if not isinstance(campaign_history, list):
                    campaign_history = []
                campaign_history.append({
                    "campaign_id": campaign.id,
                    "applied_at": datetime.now().isoformat(),
                    "trigger": "stage_change",
                    "stage": new_stage,
                })
                lead.campaign_history = campaign_history
                await db.commit()
                logger.info(
                    f"Campaign {campaign.id} triggered for lead {lead.id} due to stage change to {new_stage}"
                )
            except Exception as e:
                logger.error(
                    f"Error applying campaign {campaign.id} to lead {lead.id}: {str(e)}"
                )
    except Exception as e:
        logger.error(f"Error triggering stage campaigns: {str(e)}")


async def auto_advance_stage(
    db: AsyncSession,
    lead_id: int,
) -> Optional[Lead]:
    """
    Automatically advance lead stage based on conditions.
    Returns updated Lead if advanced, None if no advancement.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalars().first()
    if not lead:
        raise ValueError(f"Lead {lead_id} not found")

    current_stage = lead.pipeline_stage
    metadata = lead.lead_metadata or {}
    new_stage = None
    reason = None

    if current_stage == "perfilamiento":
        has_budget = metadata.get("budget") is not None and metadata.get("budget") != ""
        has_location = (
            metadata.get("location") is not None and metadata.get("location") != ""
        )
        has_name = lead.name and lead.name not in ["User", "Test User"]
        if has_budget and has_location and has_name:
            new_stage = "calificacion_financiera"
            reason = "Auto-advance: Complete profile information collected"

    elif current_stage == "calificacion_financiera":
        from app.models.appointment import Appointment, AppointmentStatus

        appointment_result = await db.execute(
            select(Appointment).where(
                and_(
                    Appointment.lead_id == lead_id,
                    Appointment.status.in_(
                        [AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]
                    ),
                )
            )
        )
        appointment = appointment_result.scalars().first()
        if appointment:
            new_stage = "agendado"
            reason = "Auto-advance: Appointment scheduled"

    elif current_stage == "agendado":
        from app.models.appointment import Appointment, AppointmentStatus

        appointment_result = await db.execute(
            select(Appointment)
            .where(
                and_(
                    Appointment.lead_id == lead_id,
                    Appointment.status == AppointmentStatus.COMPLETED,
                )
            )
            .order_by(desc(Appointment.start_time))
        )
        appointment = appointment_result.scalars().first()
        if appointment:
            new_stage = "seguimiento"
            reason = "Auto-advance: Appointment completed"

    if new_stage:
        return await move_lead_to_stage(db, lead_id, new_stage, reason)
    return None


def days_in_stage(lead: Lead) -> int:
    """Calcula días que lleva el lead en su etapa actual."""
    if not lead.stage_entered_at:
        if lead.created_at:
            delta = datetime.now(lead.created_at.tzinfo) - lead.created_at
            return delta.days
        return 0
    delta = datetime.now(lead.stage_entered_at.tzinfo) - lead.stage_entered_at
    return delta.days


async def actualizar_pipeline_stage(
    db: AsyncSession,
    lead: Lead,
) -> Optional[Lead]:
    """
    Actualiza automáticamente el pipeline_stage según datos del lead.
    """
    from app.services.broker import BrokerConfigService

    metadata = lead.lead_metadata or {}
    current_stage = lead.pipeline_stage

    if not lead.name or lead.name in ["User", "Test User"]:
        if current_stage != "entrada":
            return await move_lead_to_stage(db, lead.id, "entrada", "Auto: Sin nombre")
        return None

    has_basic_data = (
        lead.name
        and lead.name not in ["User", "Test User"]
        and (lead.phone or metadata.get("location") or metadata.get("budget"))
    )
    if has_basic_data and current_stage in [None, "entrada"]:
        return await move_lead_to_stage(
            db, lead.id, "perfilamiento", "Auto: Datos básicos recopilados"
        )

    if lead.lead_score >= 40 and current_stage == "perfilamiento":
        has_budget = metadata.get("budget") is not None and metadata.get("budget") != ""
        has_location = (
            metadata.get("location") is not None and metadata.get("location") != ""
        )
        if has_budget and has_location:
            return await move_lead_to_stage(
                db,
                lead.id,
                "calificacion_financiera",
                "Auto: Score >= 40 con datos básicos",
            )

    monthly_income = metadata.get("monthly_income")
    dicom_status = metadata.get("dicom_status")
    if monthly_income and dicom_status and current_stage == "calificacion_financiera":
        broker_id = lead.broker_id
        calificacion = await BrokerConfigService.calcular_calificacion_financiera(
            db, lead, broker_id
        )
        if not isinstance(metadata, dict):
            metadata = {}
        metadata["calificacion"] = calificacion
        lead.lead_metadata = metadata

        if calificacion == "CALIFICADO":
            from app.models.appointment import Appointment, AppointmentStatus

            appointment_result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.lead_id == lead.id,
                        Appointment.status.in_(
                            [
                                AppointmentStatus.SCHEDULED,
                                AppointmentStatus.CONFIRMED,
                            ]
                        ),
                    )
                )
            )
            appointment = appointment_result.scalars().first()
            if appointment and current_stage != "agendado":
                return await move_lead_to_stage(
                    db, lead.id, "agendado", "Auto: CALIFICADO con cita agendada"
                )

        elif calificacion == "POTENCIAL":
            if current_stage != "seguimiento":
                return await move_lead_to_stage(
                    db, lead.id, "seguimiento", "Auto: POTENCIAL - requiere seguimiento"
                )

        elif calificacion == "NO_CALIFICADO":
            if current_stage != "perdido":
                return await move_lead_to_stage(
                    db, lead.id, "perdido", "Auto: NO_CALIFICADO"
                )

        await db.commit()
        await db.refresh(lead)

    return None
