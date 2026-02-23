"""Financial qualification (CALIFICADO / POTENCIAL / NO_CALIFICADO)."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Any
import logging

from app.models.broker import BrokerLeadConfig

logger = logging.getLogger(__name__)


async def calcular_calificacion_financiera(
    db: AsyncSession,
    lead: Any,
    broker_id: int,
) -> str:
    """
    Calculate financial qualification using broker's configurable criteria.
    Returns: "CALIFICADO", "POTENCIAL", "NO_CALIFICADO"
    """
    config_result = await db.execute(
        select(BrokerLeadConfig).where(BrokerLeadConfig.broker_id == broker_id)
    )
    lead_config = config_result.scalars().first()

    if not lead_config or not lead_config.qualification_criteria:
        criteria = {
            "calificado": {
                "min_monthly_income": 1000000,
                "dicom_status": ["clean"],
                "max_debt_amount": 0,
            },
            "potencial": {
                "min_monthly_income": 500000,
                "dicom_status": ["clean", "has_debt"],
                "max_debt_amount": 500000,
            },
            "no_calificado": {
                "conditions": [
                    {"monthly_income_below": 500000},
                    {"debt_amount_above": 500000},
                ]
            },
        }
    else:
        criteria = lead_config.qualification_criteria

    if hasattr(lead, "lead_metadata"):
        metadata = lead.lead_metadata or {}
    elif isinstance(lead, dict):
        metadata = (
            lead.get("metadata", {})
            if isinstance(lead.get("metadata"), dict)
            else lead
        )
    else:
        metadata = {}

    monthly_income = metadata.get("monthly_income", 0)
    dicom_status = metadata.get("dicom_status", "unknown")
    debt_amount = metadata.get("morosidad_amount", 0)

    try:
        monthly_income = int(monthly_income) if monthly_income else 0
        debt_amount = int(debt_amount) if debt_amount else 0
    except (ValueError, TypeError):
        monthly_income = 0
        debt_amount = 0

    no_calificado_conditions = criteria.get("no_calificado", {}).get(
        "conditions", []
    )
    for condition in no_calificado_conditions:
        if "monthly_income_below" in condition:
            if monthly_income < condition["monthly_income_below"]:
                return "NO_CALIFICADO"
        if "debt_amount_above" in condition:
            if debt_amount > condition["debt_amount_above"]:
                return "NO_CALIFICADO"

    calificado_criteria = criteria.get("calificado", {})
    if (
        monthly_income >= calificado_criteria.get("min_monthly_income", 1000000)
        and dicom_status in calificado_criteria.get("dicom_status", ["clean"])
        and debt_amount <= calificado_criteria.get("max_debt_amount", 0)
    ):
        return "CALIFICADO"

    potencial_criteria = criteria.get("potencial", {})
    if (
        monthly_income >= potencial_criteria.get("min_monthly_income", 500000)
        and dicom_status
        in potencial_criteria.get("dicom_status", ["clean", "has_debt"])
        and debt_amount <= potencial_criteria.get("max_debt_amount", 500000)
    ):
        return "POTENCIAL"

    return "POTENCIAL"
