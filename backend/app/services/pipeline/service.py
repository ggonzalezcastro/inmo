"""
Pipeline service: advancement and metrics facade.
"""
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.services.broker import BrokerConfigService
from app.services.pipeline.constants import PIPELINE_STAGES
from app.services.pipeline.advancement_service import (
    move_lead_to_stage as _move_lead_to_stage,
    auto_advance_stage as _auto_advance_stage,
    actualizar_pipeline_stage as _actualizar_pipeline_stage,
    days_in_stage as _days_in_stage,
)
from app.services.pipeline.metrics_service import (
    get_leads_by_stage as _get_leads_by_stage,
    get_stage_metrics as _get_stage_metrics,
    get_leads_inactive_in_stage as _get_leads_inactive_in_stage,
)


class PipelineService:
    """Facade for pipeline advancement and metrics. Same public API as before."""

    PIPELINE_STAGES = PIPELINE_STAGES

    @staticmethod
    async def move_lead_to_stage(
        db: AsyncSession,
        lead_id: int,
        new_stage: str,
        reason: Optional[str] = None,
        triggered_by_campaign: Optional[int] = None,
    ) -> Lead:
        return await _move_lead_to_stage(
            db, lead_id, new_stage, reason, triggered_by_campaign
        )

    @staticmethod
    async def auto_advance_stage(db: AsyncSession, lead_id: int) -> Optional[Lead]:
        return await _auto_advance_stage(db, lead_id)

    @staticmethod
    async def get_leads_by_stage(
        db: AsyncSession,
        stage: str,
        broker_id: Optional[int] = None,
        treatment_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[Lead], int]:
        return await _get_leads_by_stage(
            db, stage, broker_id, treatment_type, skip, limit
        )

    @staticmethod
    async def get_stage_metrics(
        db: AsyncSession,
        broker_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        return await _get_stage_metrics(db, broker_id)

    @staticmethod
    async def get_leads_inactive_in_stage(
        db: AsyncSession,
        stage: str,
        inactivity_days: int = 7,
    ) -> List[Lead]:
        return await _get_leads_inactive_in_stage(db, stage, inactivity_days)

    @staticmethod
    async def calcular_calificacion(
        db: AsyncSession,
        lead: Lead,
        broker_id: Optional[int] = None,
    ) -> str:
        return await BrokerConfigService.calcular_calificacion_financiera(
            db, lead, broker_id
        )

    @staticmethod
    async def actualizar_pipeline_stage(
        db: AsyncSession,
        lead: Lead,
    ) -> Optional[Lead]:
        return await _actualizar_pipeline_stage(db, lead)

    @staticmethod
    def days_in_stage(lead: Lead) -> int:
        return _days_in_stage(lead)
