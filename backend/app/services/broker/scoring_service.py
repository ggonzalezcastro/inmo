"""Lead scoring and default config (broker)."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, Any, Optional
import logging

from app.models.broker import BrokerLeadConfig

logger = logging.getLogger(__name__)


async def get_default_config(db: AsyncSession) -> Dict[str, Any]:
    """Get default configuration values when no broker config exists."""
    return {
        "field_weights": {
            "name": 10,
            "phone": 15,
            "email": 10,
            "location": 15,
            "budget": 20,
            "monthly_income": 25,
            "dicom_status": 20,
        },
        "cold_max_score": 20,
        "warm_max_score": 50,
        "hot_min_score": 50,
        "qualified_min_score": 75,
        "field_priority": [
            "name",
            "phone",
            "email",
            "location",
            "monthly_income",
            "dicom_status",
            "budget",
        ],
        "income_ranges": {
            "insufficient": {"min": 0, "max": 500000, "label": "Insuficiente"},
            "low": {"min": 500000, "max": 1000000, "label": "Bajo"},
            "medium": {"min": 1000000, "max": 2000000, "label": "Medio"},
            "good": {"min": 2000000, "max": 4000000, "label": "Bueno"},
            "excellent": {"min": 4000000, "max": None, "label": "Excelente"},
        },
        "qualification_criteria": {
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
        },
        "max_acceptable_debt": 500000,
    }


async def calculate_financial_score(
    db: AsyncSession,
    lead_data: Dict[str, Any],
    broker_id: int,
) -> int:
    """Calculate financial score (0-45) from monthly_income and dicom_status."""
    config_result = await db.execute(
        select(BrokerLeadConfig).where(BrokerLeadConfig.broker_id == broker_id)
    )
    lead_config = config_result.scalars().first()

    if not lead_config or not lead_config.field_weights:
        income_weight = 25
        dicom_weight = 20
        max_acceptable_debt = 500000
        income_ranges = None
    else:
        income_weight = lead_config.field_weights.get("monthly_income", 25)
        dicom_weight = lead_config.field_weights.get("dicom_status", 20)
        max_acceptable_debt = lead_config.max_acceptable_debt or 500000
        income_ranges = lead_config.income_ranges

    points = 0
    metadata = (
        lead_data.get("metadata", {})
        if isinstance(lead_data.get("metadata"), dict)
        else lead_data
    )

    monthly_income = metadata.get("monthly_income")
    if monthly_income:
        try:
            income = int(monthly_income)
            if income_ranges:
                for range_key, range_data in income_ranges.items():
                    range_min = range_data.get("min", 0)
                    range_max = range_data.get("max")
                    if range_max is None:
                        if income >= range_min:
                            points += income_weight
                            break
                    elif range_min <= income < range_max:
                        if range_key == "excellent":
                            points += income_weight
                        elif range_key == "good":
                            points += int(income_weight * 0.8)
                        elif range_key == "medium":
                            points += int(income_weight * 0.6)
                        elif range_key == "low":
                            points += int(income_weight * 0.4)
                        break
            else:
                if income >= 4000000:
                    points += income_weight
                elif income >= 2000000:
                    points += int(income_weight * 0.8)
                elif income >= 1000000:
                    points += int(income_weight * 0.6)
                elif income >= 500000:
                    points += int(income_weight * 0.4)
        except (ValueError, TypeError):
            pass

    dicom_status = metadata.get("dicom_status")
    if dicom_status == "clean":
        points += dicom_weight
    elif dicom_status == "has_debt":
        morosidad_amount = metadata.get("morosidad_amount", 0)
        try:
            morosidad = int(morosidad_amount)
            if morosidad <= max_acceptable_debt:
                points += int(dicom_weight * 0.5)
        except (ValueError, TypeError):
            pass

    return min(45, points)


async def determine_lead_status(
    db: AsyncSession,
    score: float,
    broker_id: int,
) -> str:
    """Determine lead status (cold/warm/hot) from score and broker thresholds."""
    config_result = await db.execute(
        select(BrokerLeadConfig).where(BrokerLeadConfig.broker_id == broker_id)
    )
    lead_config = config_result.scalars().first()

    if not lead_config:
        cold_max, warm_max, hot_min = 20, 50, 50
    else:
        cold_max = lead_config.cold_max_score
        warm_max = lead_config.warm_max_score
        hot_min = lead_config.hot_min_score

    if score <= cold_max:
        return "cold"
    if score <= warm_max:
        return "warm"
    return "hot"


async def calculate_lead_score(
    db: AsyncSession,
    lead_data: Dict[str, Any],
    broker_id: int,
) -> Dict[str, Any]:
    """Calculate lead score and status using broker config."""
    config_result = await db.execute(
        select(BrokerLeadConfig).where(BrokerLeadConfig.broker_id == broker_id)
    )
    lead_config = config_result.scalars().first()

    if not lead_config or not lead_config.field_weights:
        default_config = await get_default_config(db)
        weights = default_config["field_weights"]
        cold_max = default_config["cold_max_score"]
        warm_max = default_config["warm_max_score"]
        hot_min = default_config["hot_min_score"]
    else:
        weights = lead_config.field_weights
        cold_max = lead_config.cold_max_score
        warm_max = lead_config.warm_max_score
        hot_min = lead_config.hot_min_score

    score = 0
    metadata = (
        lead_data.get("metadata", {})
        if isinstance(lead_data.get("metadata"), dict)
        else {}
    )

    if lead_data.get("name") and lead_data["name"] not in ("User", "Test User"):
        score += weights.get("name", 0)
    if lead_data.get("phone") and not str(lead_data["phone"]).startswith(
        ("web_chat_", "whatsapp_", "+569999")
    ):
        score += weights.get("phone", 0)
    if lead_data.get("email") and lead_data["email"].strip():
        score += weights.get("email", 0)
    if lead_data.get("location") or metadata.get("location"):
        score += weights.get("location", 0)
    if lead_data.get("budget") or metadata.get("budget"):
        score += weights.get("budget", 0)

    financial_data = {"metadata": metadata}
    financial_score = await calculate_financial_score(db, financial_data, broker_id)
    score += financial_score

    status = await determine_lead_status(db, score, broker_id)

    return {
        "score": score,
        "status": status,
        "financial_score": financial_score,
    }


async def get_next_field_to_ask(
    db: AsyncSession,
    lead_data: Dict[str, Any],
    broker_id: int,
) -> Optional[str]:
    """Get next field to ask based on broker priority."""
    config_result = await db.execute(
        select(BrokerLeadConfig).where(BrokerLeadConfig.broker_id == broker_id)
    )
    lead_config = config_result.scalars().first()

    priority = [
        "name",
        "phone",
        "email",
        "location",
        "monthly_income",
        "dicom_status",
    ]
    if lead_config and lead_config.field_priority:
        priority = lead_config.field_priority

    metadata = (
        lead_data.get("metadata", {})
        if isinstance(lead_data.get("metadata"), dict)
        else {}
    )

    def has_field(field_name: str) -> bool:
        if field_name == "name":
            return bool(
                lead_data.get("name")
                and lead_data["name"] not in ("User", "Test User")
            )
        if field_name == "phone":
            phone = lead_data.get("phone")
            return bool(
                phone
                and not str(phone).startswith(
                    ("web_chat_", "whatsapp_", "+569999")
                )
            )
        if field_name == "email":
            return bool(
                lead_data.get("email") and str(lead_data["email"]).strip()
            )
        if field_name == "location":
            return bool(metadata.get("location"))
        return False

    for field in priority:
        if not has_field(field):
            return field
    return None
