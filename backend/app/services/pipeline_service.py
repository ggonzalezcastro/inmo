"""
Pipeline service for managing lead pipeline stages
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
from app.models.lead import Lead, LeadStatus
from app.services.activity_service import ActivityService
from app.models.campaign import Campaign, CampaignTrigger

logger = logging.getLogger(__name__)


# Pipeline stages
PIPELINE_STAGES = {
    "entrada": "Lead inicial - recién recibido",
    "perfilamiento": "Recopilando información del cliente",
    "calificacion_financiera": "Validando capacidad financiera",
    "agendado": "Cita agendada",
    "seguimiento": "Seguimiento post-reunión",
    "referidos": "Esperando referidos",
    "ganado": "Cliente convertido",
    "perdido": "Oportunidad perdida"
}


class PipelineService:
    """Service for managing lead pipeline stages"""
    
    @staticmethod
    async def move_lead_to_stage(
        db: AsyncSession,
        lead_id: int,
        new_stage: str,
        reason: Optional[str] = None,
        triggered_by_campaign: Optional[int] = None
    ) -> Lead:
        """
        Move a lead to a new pipeline stage
        
        Args:
            db: Database session
            lead_id: Lead ID
            new_stage: New pipeline stage name
            reason: Reason for stage change
            triggered_by_campaign: Campaign ID if triggered by campaign
        
        Returns:
            Updated Lead instance
        """
        
        if new_stage not in PIPELINE_STAGES:
            raise ValueError(f"Invalid pipeline stage: {new_stage}. Valid stages: {list(PIPELINE_STAGES.keys())}")
        
        # Get lead
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalars().first()
        
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        old_stage = lead.pipeline_stage
        
        # Update stage
        lead.pipeline_stage = new_stage
        lead.stage_entered_at = datetime.now().replace(tzinfo=lead.created_at.tzinfo)
        
        await db.commit()
        
        # Log activity
        await ActivityService.log_activity(
            db,
            lead_id=lead_id,
            action_type="stage_change",
            details={
                "old_stage": old_stage,
                "new_stage": new_stage,
                "reason": reason or "Manual update",
                "triggered_by_campaign": triggered_by_campaign,
                "stage_entered_at": lead.stage_entered_at.isoformat()
            }
        )
        
        logger.info(f"Lead {lead_id} moved from {old_stage} to {new_stage}. Reason: {reason}")
        
        # Trigger stage_change campaigns
        await PipelineService._trigger_stage_campaigns(db, lead, new_stage)
        
        await db.refresh(lead)
        return lead
    
    @staticmethod
    async def _trigger_stage_campaigns(
        db: AsyncSession,
        lead: Lead,
        new_stage: str
    ) -> None:
        """Trigger campaigns configured for stage_change trigger"""
        
        try:
            # Find active campaigns triggered by stage_change
            campaigns_result = await db.execute(
                select(Campaign).where(and_(
                    Campaign.status == "active",
                    Campaign.triggered_by == CampaignTrigger.STAGE_CHANGE
                ))
            )
            campaigns = campaigns_result.scalars().all()
            
            for campaign in campaigns:
                # Check if campaign condition matches this stage
                condition = campaign.trigger_condition or {}
                target_stage = condition.get("stage")
                
                if target_stage == new_stage:
                    # Check if campaign already applied to this lead
                    from app.services.campaign_service import CampaignService
                    
                    existing_logs_result = await db.execute(
                        select(Campaign).where(and_(
                            Campaign.id == campaign.id
                        ))
                    )
                    
                    # Check campaign history in lead
                    campaign_history = lead.campaign_history or []
                    already_applied = any(
                        log.get("campaign_id") == campaign.id 
                        for log in campaign_history
                    )
                    
                    if not already_applied:
                        try:
                            await CampaignService.apply_campaign_to_lead(db, campaign.id, lead.id)
                            
                            # Update campaign history
                            if not isinstance(campaign_history, list):
                                campaign_history = []
                            
                            campaign_history.append({
                                "campaign_id": campaign.id,
                                "applied_at": datetime.now().isoformat(),
                                "trigger": "stage_change",
                                "stage": new_stage
                            })
                            lead.campaign_history = campaign_history
                            await db.commit()
                            
                            logger.info(f"Campaign {campaign.id} triggered for lead {lead.id} due to stage change to {new_stage}")
                        except Exception as e:
                            logger.error(f"Error applying campaign {campaign.id} to lead {lead.id}: {str(e)}")
                            # Continue with other campaigns
        except Exception as e:
            logger.error(f"Error triggering stage campaigns: {str(e)}")
    
    @staticmethod
    async def auto_advance_stage(
        db: AsyncSession,
        lead_id: int
    ) -> Optional[Lead]:
        """
        Automatically advance lead stage based on conditions
        
        Rules:
        - If in "perfilamiento" and has budget → move to "calificacion_financiera"
        - If in "calificacion_financiera" and approved → move to "agendado"
        - If in "agendado" and meeting confirmed → move to "seguimiento"
        
        Returns:
            Updated Lead if advanced, None if no advancement
        """
        
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalars().first()
        
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        current_stage = lead.pipeline_stage
        metadata = lead.lead_metadata or {}
        
        new_stage = None
        reason = None
        
        # Rule 1: perfilamiento → calificacion_financiera
        if current_stage == "perfilamiento":
            has_budget = metadata.get("budget") is not None and metadata.get("budget") != ""
            has_location = metadata.get("location") is not None and metadata.get("location") != ""
            has_name = lead.name and lead.name not in ["User", "Test User"]
            
            if has_budget and has_location and has_name:
                new_stage = "calificacion_financiera"
                reason = "Auto-advance: Complete profile information collected"
        
        # Rule 2: calificacion_financiera → agendado
        elif current_stage == "calificacion_financiera":
            # Check if there's an appointment
            from app.models.appointment import Appointment, AppointmentStatus
            
            appointment_result = await db.execute(
                select(Appointment).where(and_(
                    Appointment.lead_id == lead_id,
                    Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED])
                ))
            )
            appointment = appointment_result.scalars().first()
            
            if appointment:
                new_stage = "agendado"
                reason = "Auto-advance: Appointment scheduled"
        
        # Rule 3: agendado → seguimiento (if appointment completed)
        elif current_stage == "agendado":
            from app.models.appointment import Appointment, AppointmentStatus
            
            appointment_result = await db.execute(
                select(Appointment).where(and_(
                    Appointment.lead_id == lead_id,
                    Appointment.status == AppointmentStatus.COMPLETED
                )).order_by(desc(Appointment.start_time))
            )
            appointment = appointment_result.scalars().first()
            
            if appointment:
                new_stage = "seguimiento"
                reason = "Auto-advance: Appointment completed"
        
        if new_stage:
            return await PipelineService.move_lead_to_stage(
                db, lead_id, new_stage, reason
            )
        
        return None
    
    @staticmethod
    async def get_leads_by_stage(
        db: AsyncSession,
        stage: str,
        broker_id: Optional[int] = None,
        treatment_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[List[Lead], int]:
        """
        Get leads in a specific pipeline stage
        
        For "entrada" stage: includes leads with pipeline_stage IS NULL or pipeline_stage = "entrada"
        For other stages: includes only leads with pipeline_stage = stage
        """
        
        if stage not in PIPELINE_STAGES:
            raise ValueError(f"Invalid pipeline stage: {stage}")
        
        # Build base query condition
        # Para "entrada", incluir leads con pipeline_stage NULL o "entrada"
        if stage == "entrada":
            stage_condition = or_(
                Lead.pipeline_stage.is_(None),
                Lead.pipeline_stage == "entrada"
            )
        else:
            stage_condition = Lead.pipeline_stage == stage
        
        # Build query with filters
        query = select(Lead).where(stage_condition)
        count_query = select(func.count(Lead.id)).where(stage_condition)
        
        # Filter by broker_id if provided (through assigned_to or campaign association)
        if broker_id:
            # For now, we filter by assigned_to if it matches broker_id
            # If your schema has direct broker_id on leads, use: Lead.broker_id == broker_id
            query = query.where(Lead.assigned_to == broker_id)
            count_query = count_query.where(Lead.assigned_to == broker_id)
        
        # Filter by treatment_type if provided
        if treatment_type:
            query = query.where(Lead.treatment_type == treatment_type)
            count_query = count_query.where(Lead.treatment_type == treatment_type)
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination and ordering
        # For "entrada" stage with NULL values, order by created_at as fallback
        if stage == "entrada":
            query = query.order_by(
                desc(Lead.stage_entered_at).nulls_last(),
                desc(Lead.created_at)
            ).offset(skip).limit(limit)
        else:
            query = query.order_by(desc(Lead.stage_entered_at)).offset(skip).limit(limit)
        
        result = await db.execute(query)
        leads = result.scalars().all()
        
        return leads, total
    
    @staticmethod
    async def get_stage_metrics(
        db: AsyncSession,
        broker_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get conversion metrics between stages"""
        
        # Get lead counts per stage
        stages = list(PIPELINE_STAGES.keys())
        stage_counts = {}
        
        for stage in stages:
            # For "entrada", include leads with NULL pipeline_stage
            if stage == "entrada":
                query = select(func.count(Lead.id)).where(
                    or_(
                        Lead.pipeline_stage.is_(None),
                        Lead.pipeline_stage == "entrada"
                    )
                )
            else:
                query = select(func.count(Lead.id)).where(Lead.pipeline_stage == stage)
            
            # Filter by broker if provided
            if broker_id:
                query = query.where(Lead.assigned_to == broker_id)
            
            result = await db.execute(query)
            count = result.scalar() or 0
            stage_counts[stage] = count
        
        # Calculate conversion rates (simple for now)
        total_leads = sum(stage_counts.values())
        
        # Calculate days in stage averages (if stage_entered_at is set)
        stage_avg_days = {}
        for stage in stages:
            # For "entrada", include leads with NULL pipeline_stage
            if stage == "entrada":
                stage_condition = or_(
                    Lead.pipeline_stage.is_(None),
                    Lead.pipeline_stage == "entrada"
                )
            else:
                stage_condition = Lead.pipeline_stage == stage
            
            query = select(Lead.stage_entered_at).where(and_(
                stage_condition,
                Lead.stage_entered_at.isnot(None)
            ))
            
            # Filter by broker if provided
            if broker_id:
                query = query.where(Lead.assigned_to == broker_id)
            
            result = await db.execute(query)
            timestamps = [row[0] for row in result.all() if row[0]]
            
            # For NULL pipeline_stage leads, use created_at as fallback
            if stage == "entrada":
                fallback_query = select(Lead.created_at).where(
                    and_(
                        Lead.pipeline_stage.is_(None),
                        Lead.stage_entered_at.is_(None)
                    )
                )
                if broker_id:
                    fallback_query = fallback_query.where(Lead.assigned_to == broker_id)
                
                fallback_result = await db.execute(fallback_query)
                fallback_timestamps = [row[0] for row in fallback_result.all() if row[0]]
                timestamps.extend(fallback_timestamps)
            
            if timestamps:
                now = datetime.now().replace(tzinfo=timestamps[0].tzinfo)
                days_list = [(now - ts).days for ts in timestamps]
                stage_avg_days[stage] = sum(days_list) / len(days_list) if days_list else 0
            else:
                stage_avg_days[stage] = 0
        
        return {
            "total_leads": total_leads,
            "stage_counts": stage_counts,
            "stage_avg_days": stage_avg_days,
            "stages": PIPELINE_STAGES
        }
    
    @staticmethod
    async def get_leads_inactive_in_stage(
        db: AsyncSession,
        stage: str,
        inactivity_days: int = 7
    ) -> List[Lead]:
        """Get leads that have been in a stage for too long without activity"""
        
        if stage not in PIPELINE_STAGES:
            raise ValueError(f"Invalid pipeline stage: {stage}")
        
        cutoff_date = datetime.now() - timedelta(days=inactivity_days)
        
        query = select(Lead).where(and_(
            Lead.pipeline_stage == stage,
            Lead.stage_entered_at.isnot(None),
            Lead.stage_entered_at <= cutoff_date
        ))
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def calcular_calificacion(
        db: AsyncSession,
        lead: Lead,
        broker_id: Optional[int] = None
    ) -> str:
        """
        Calcula calificación financiera usando criterios configurables del broker
        
        ⭐ IMPORTANTE: NO hardcodear valores, usar broker_lead_configs
        
        Returns: "CALIFICADO", "POTENCIAL", "NO_CALIFICADO"
        """
        # Use BrokerConfigService for financial qualification (no hardcoding)
        # This will use broker config if available, or default config if broker_id is None
        from app.services.broker_config_service import BrokerConfigService
        
        calificacion = await BrokerConfigService.calcular_calificacion_financiera(
            db, lead, broker_id
        )
        return calificacion
    
    @staticmethod
    async def actualizar_pipeline_stage(
        db: AsyncSession,
        lead: Lead
    ) -> Optional[Lead]:
        """
        Actualiza automáticamente el pipeline_stage según datos del lead
        
        Lógica:
        - Si no tiene nombre → "entrada"
        - Si tiene datos básicos → "perfilamiento"
        - Si score >= 40 → "calificacion_financiera"
        - Si tiene monthly_income + dicom_status:
          - Calcular calificacion
          - Si CALIFICADO → listo para "agendado" (cuando se cree cita)
          - Si POTENCIAL → "seguimiento"
          - Si NO_CALIFICADO → "perdido"
        """
        metadata = lead.lead_metadata or {}
        current_stage = lead.pipeline_stage
        
        # Si no tiene nombre → "entrada"
        if not lead.name or lead.name in ["User", "Test User"]:
            if current_stage != "entrada":
                return await PipelineService.move_lead_to_stage(
                    db, lead.id, "entrada", "Auto: Sin nombre"
                )
            return None
        
        # Si tiene datos básicos → "perfilamiento"
        has_basic_data = (
            lead.name and 
            lead.name not in ["User", "Test User"] and
            (lead.phone or metadata.get("location") or metadata.get("budget"))
        )
        
        if has_basic_data and current_stage in [None, "entrada"]:
            return await PipelineService.move_lead_to_stage(
                db, lead.id, "perfilamiento", "Auto: Datos básicos recopilados"
            )
        
        # Si score >= 40 y tiene budget/location → "calificacion_financiera"
        if lead.lead_score >= 40 and current_stage == "perfilamiento":
            has_budget = metadata.get("budget") is not None and metadata.get("budget") != ""
            has_location = metadata.get("location") is not None and metadata.get("location") != ""
            
            if has_budget and has_location:
                return await PipelineService.move_lead_to_stage(
                    db, lead.id, "calificacion_financiera", "Auto: Score >= 40 con datos básicos"
                )
        
        # Si tiene monthly_income + dicom_status → calcular calificación
        monthly_income = metadata.get("monthly_income")
        dicom_status = metadata.get("dicom_status")
        
        if monthly_income and dicom_status and current_stage == "calificacion_financiera":
            # Obtener broker_id del lead
            broker_id = lead.broker_id
            calificacion = await PipelineService.calcular_calificacion(db, lead, broker_id)
            
            # Actualizar metadata con calificación
            if not isinstance(metadata, dict):
                metadata = {}
            metadata["calificacion"] = calificacion
            lead.lead_metadata = metadata
            
            # Si CALIFICADO → listo para "agendado" (se moverá cuando se cree cita)
            if calificacion == "CALIFICADO":
                # No movemos automáticamente a "agendado", esperamos que se cree la cita
                # Pero podemos verificar si ya hay cita
                from app.models.appointment import Appointment, AppointmentStatus
                appointment_result = await db.execute(
                    select(Appointment).where(and_(
                        Appointment.lead_id == lead.id,
                        Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED])
                    ))
                )
                appointment = appointment_result.scalars().first()
                
                if appointment and current_stage != "agendado":
                    return await PipelineService.move_lead_to_stage(
                        db, lead.id, "agendado", "Auto: CALIFICADO con cita agendada"
                    )
            
            # Si POTENCIAL → "seguimiento"
            elif calificacion == "POTENCIAL":
                if current_stage != "seguimiento":
                    return await PipelineService.move_lead_to_stage(
                        db, lead.id, "seguimiento", "Auto: POTENCIAL - requiere seguimiento"
                    )
            
            # Si NO_CALIFICADO → "perdido"
            elif calificacion == "NO_CALIFICADO":
                if current_stage != "perdido":
                    return await PipelineService.move_lead_to_stage(
                        db, lead.id, "perdido", "Auto: NO_CALIFICADO"
                    )
            
            await db.commit()
            await db.refresh(lead)
        
        return None
    
    @staticmethod
    def days_in_stage(lead: Lead) -> int:
        """Calcula días que lleva el lead en su etapa actual"""
        if not lead.stage_entered_at:
            # Si no tiene stage_entered_at, usar created_at como fallback
            if lead.created_at:
                delta = datetime.now(lead.created_at.tzinfo) - lead.created_at
                return delta.days
            return 0
        
        delta = datetime.now(lead.stage_entered_at.tzinfo) - lead.stage_entered_at
        return delta.days

