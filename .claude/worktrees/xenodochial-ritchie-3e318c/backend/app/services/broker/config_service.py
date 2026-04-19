"""
Broker configuration service: prompts, scoring, qualification.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, Any, Optional
import logging

from app.models.broker import Broker
from app.services.broker.prompt_defaults import DEFAULT_SYSTEM_PROMPT
from app.services.broker.prompt_service import build_system_prompt as _build_system_prompt
from app.services.broker.scoring_service import (
    get_default_config as _get_default_config,
    calculate_lead_score as _calculate_lead_score,
    calculate_financial_score as _calculate_financial_score,
    determine_lead_status as _determine_lead_status,
    get_next_field_to_ask as _get_next_field_to_ask,
)
from app.services.broker.qualification_service import (
    calcular_calificacion_financiera as _calcular_calificacion_financiera,
)

logger = logging.getLogger(__name__)


class BrokerConfigService:
    """Facade for broker configuration, prompts, scoring, and qualification."""

    DEFAULT_SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT

    @staticmethod
    async def get_broker_with_config(
        db: AsyncSession, broker_id: int
    ) -> Optional[Broker]:
        """Get broker with prompt and lead configs."""
        result = await db.execute(
            select(Broker).where(Broker.id == broker_id)
        )
        return result.scalars().first()

    @staticmethod
    async def build_system_prompt(
        db: AsyncSession,
        broker_id: int,
        lead_context: Optional[Dict] = None,
    ) -> str:
        """Build system prompt from broker configuration."""
        return await _build_system_prompt(db, broker_id, lead_context)

    @staticmethod
    async def get_default_config(db: AsyncSession) -> Dict[str, Any]:
        """Get default configuration values."""
        return await _get_default_config(db)

    @staticmethod
    async def calculate_lead_score(
        db: AsyncSession,
        lead_data: Dict[str, Any],
        broker_id: int,
    ) -> Dict[str, Any]:
        """Calculate lead score and status."""
        return await _calculate_lead_score(db, lead_data, broker_id)

    @staticmethod
    async def calculate_financial_score(
        db: AsyncSession,
        lead_data: Dict[str, Any],
        broker_id: int,
    ) -> int:
        """Calculate financial score (0-45)."""
        return await _calculate_financial_score(db, lead_data, broker_id)

    @staticmethod
    async def determine_lead_status(
        db: AsyncSession,
        score: float,
        broker_id: int,
    ) -> str:
        """Determine lead status (cold/warm/hot)."""
        return await _determine_lead_status(db, score, broker_id)

    @staticmethod
    async def get_next_field_to_ask(
        db: AsyncSession,
        lead_data: Dict[str, Any],
        broker_id: int,
    ) -> Optional[str]:
        """Get next field to ask based on broker priority."""
        return await _get_next_field_to_ask(db, lead_data, broker_id)

    @staticmethod
    async def calcular_calificacion_financiera(
        db: AsyncSession,
        lead: Any,
        broker_id: int,
    ) -> str:
        """Calculate financial qualification (CALIFICADO/POTENCIAL/NO_CALIFICADO)."""
        return await _calcular_calificacion_financiera(db, lead, broker_id)
