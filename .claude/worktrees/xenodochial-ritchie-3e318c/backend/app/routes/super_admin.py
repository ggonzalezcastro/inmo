"""
Super Admin endpoints — only accessible to SUPERADMIN role.

Mounted at: /api/v1/admin
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import create_access_token, get_current_user
from app.middleware.permissions import Permissions
from app.models.broker import Broker
from app.models.broker_chat_config import BrokerChatConfig
from app.models.broker_plan import BrokerPlan
from app.models.lead import Lead
from app.models.chat_message import ChatMessage
from app.models.llm_call import LLMCall
from app.models.user import User
from app.core.cache import cache_get_json, cache_set_json
from app.middleware.plan_limits import invalidate_plan_cache
from app.services.audit import log_audit
from app.services.health import get_system_health

router = APIRouter()

_SENTRY_CACHE_KEY = "super_admin:sentry_issues"
_SENTRY_CACHE_TTL = 60  # seconds


# ---------------------------------------------------------------------------
# Dashboard KPIs
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def super_admin_dashboard(
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Global KPIs for the super admin dashboard.
    Returns: active_brokers, total_leads, messages_today, cost_this_month, health_status.
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Active brokers count
    active_brokers_result = await db.execute(
        select(func.count(Broker.id)).where(Broker.is_active == True)
    )
    active_brokers = active_brokers_result.scalar() or 0

    # Total leads
    total_leads_result = await db.execute(select(func.count(Lead.id)))
    total_leads = total_leads_result.scalar() or 0

    # Messages today
    messages_today_result = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.created_at >= today_start)
    )
    messages_today = messages_today_result.scalar() or 0

    # LLM cost this month
    cost_month_result = await db.execute(
        select(func.coalesce(func.sum(LLMCall.estimated_cost_usd), 0)).where(
            LLMCall.created_at >= month_start
        )
    )
    cost_this_month = float(cost_month_result.scalar() or 0)

    # Quick health snapshot (status only to keep response fast)
    health = await get_system_health()

    return {
        "active_brokers": active_brokers,
        "total_leads": total_leads,
        "messages_today": messages_today,
        "cost_this_month_usd": round(cost_this_month, 4),
        "health_status": health["status"],
    }


# ---------------------------------------------------------------------------
# Full System Health
# ---------------------------------------------------------------------------

@router.get("/health")
async def super_admin_health(
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Full system health detail: DB, Redis, circuit breakers, WS connections per broker, cache stats.
    Also enriches WS connection counts with broker names.
    """
    health = await get_system_health()

    # Enrich WebSocket broker stats with broker names
    ws_raw: dict = health.get("websocket", {})
    ws_by_broker = ws_raw.get("by_broker", {}) if isinstance(ws_raw, dict) else {}

    if ws_by_broker:
        broker_ids = [int(bid) for bid in ws_by_broker.keys() if str(bid).isdigit()]
        if broker_ids:
            result = await db.execute(
                select(Broker.id, Broker.name).where(Broker.id.in_(broker_ids))
            )
            broker_names = {row.id: row.name for row in result}
            health["websocket"]["by_broker_named"] = {
                broker_names.get(int(bid), f"broker_{bid}"): count
                for bid, count in ws_by_broker.items()
            }

    return health


# ---------------------------------------------------------------------------
# Sentry Error Panel
# ---------------------------------------------------------------------------


@router.get("/errors")
async def super_admin_errors(
    limit: int = Query(25, ge=1, le=100),
    current_user: dict = Depends(Permissions.require_superadmin),
):
    """
    Fetch recent unresolved Sentry issues.
    Requires SENTRY_AUTH_TOKEN, SENTRY_ORG, SENTRY_PROJECT in settings.
    Results are cached in Redis for 60 seconds (shared across all workers).
    Falls back to direct Sentry fetch when Redis is unavailable.
    """
    if not all([settings.SENTRY_AUTH_TOKEN, settings.SENTRY_ORG, settings.SENTRY_PROJECT]):
        return {"configured": False, "issues": []}

    cached = await cache_get_json(f"{_SENTRY_CACHE_KEY}:{limit}")
    if cached is not None:
        return {"configured": True, "issues": cached}

    url = (
        f"https://sentry.io/api/0/projects/{settings.SENTRY_ORG}/{settings.SENTRY_PROJECT}/issues/"
        f"?query=is:unresolved&sort=date&limit={limit}"
    )
    headers = {"Authorization": f"Bearer {settings.SENTRY_AUTH_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            raw = resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Sentry API error: {exc.response.status_code}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sentry unreachable: {str(exc)}")

    issues = [
        {
            "id": issue.get("id"),
            "short_id": issue.get("shortId"),
            "title": issue.get("title"),
            "level": issue.get("level"),
            "count": issue.get("count"),
            "last_seen": issue.get("lastSeen"),
            "first_seen": issue.get("firstSeen"),
            "permalink": issue.get("permalink"),
        }
        for issue in raw
    ]

    await cache_set_json(f"{_SENTRY_CACHE_KEY}:{limit}", issues, ttl_seconds=_SENTRY_CACHE_TTL)

    return {"configured": True, "issues": issues}


# ---------------------------------------------------------------------------
# Broker Plans CRUD
# ---------------------------------------------------------------------------

class PlanCreate(BaseModel):
    name: str
    description: Optional[str] = None
    max_leads: Optional[int] = None
    max_users: Optional[int] = None
    max_messages_per_month: Optional[int] = None
    max_llm_cost_per_month: Optional[float] = None
    is_default: bool = False


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_leads: Optional[int] = None
    max_users: Optional[int] = None
    max_messages_per_month: Optional[int] = None
    max_llm_cost_per_month: Optional[float] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


def _plan_to_dict(plan: BrokerPlan) -> dict:
    return {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "max_leads": plan.max_leads,
        "max_users": plan.max_users,
        "max_messages_per_month": plan.max_messages_per_month,
        "max_llm_cost_per_month": plan.max_llm_cost_per_month,
        "is_default": plan.is_default,
        "is_active": plan.is_active,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


@router.get("/plans")
async def list_plans(
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BrokerPlan).order_by(BrokerPlan.id))
    plans = result.scalars().all()
    return [_plan_to_dict(p) for p in plans]


@router.post("/plans", status_code=201)
async def create_plan(
    body: PlanCreate,
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    plan = BrokerPlan(**body.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return _plan_to_dict(plan)


@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: int,
    body: PlanUpdate,
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BrokerPlan).where(BrokerPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(plan, field, value)

    await db.commit()
    await db.refresh(plan)
    return _plan_to_dict(plan)


@router.delete("/plans/{plan_id}", status_code=200)
async def deactivate_plan(
    plan_id: int,
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BrokerPlan).where(BrokerPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    affected_result = await db.execute(
        select(func.count(Broker.id)).where(
            Broker.plan_id == plan_id,
            Broker.is_active == True,
        )
    )
    affected_count = affected_result.scalar() or 0
    if affected_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede desactivar: {affected_count} broker(s) tienen este plan asignado. Reasígnalos primero.",
        )

    plan.is_active = False
    await db.commit()
    return {"status": "deactivated", "id": plan_id}


class AssignPlanBody(BaseModel):
    plan_id: Optional[int] = None  # None = unassign


@router.put("/brokers/{broker_id}/plan")
async def assign_plan_to_broker(
    broker_id: int,
    body: AssignPlanBody,
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Broker).where(Broker.id == broker_id))
    broker = result.scalar_one_or_none()
    if not broker:
        raise HTTPException(status_code=404, detail="Broker no encontrado")

    if body.plan_id is not None:
        plan_result = await db.execute(select(BrokerPlan).where(BrokerPlan.id == body.plan_id, BrokerPlan.is_active == True))
        if not plan_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Plan no encontrado o inactivo")

    broker.plan_id = body.plan_id
    await db.commit()
    await invalidate_plan_cache(broker_id)
    return {"status": "updated", "broker_id": broker_id, "plan_id": body.plan_id}


# ---------------------------------------------------------------------------
# Impersonation
# ---------------------------------------------------------------------------

_IMPERSONATION_TTL_MINUTES = 30


@router.post("/impersonate/{broker_id}")
async def start_impersonation(
    broker_id: int,
    request: Request,
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a short-lived JWT that appears as an ADMIN scoped to the target broker.
    The original superadmin's user_id is preserved in 'sub'.
    The token carries an 'impersonating: true' flag so get_current_user can detect it.
    """
    result = await db.execute(
        select(Broker).where(Broker.id == broker_id, Broker.is_active == True)
    )
    broker = result.scalar_one_or_none()
    if not broker:
        raise HTTPException(status_code=404, detail="Broker no encontrado o inactivo")

    # Load superadmin user to get email
    try:
        sa_uid = int(current_user["user_id"])
    except (TypeError, ValueError):
        sa_uid = None
    user_result = await db.execute(select(User).where(User.id == sa_uid)) if sa_uid else None
    sa_user = user_result.scalar_one_or_none() if user_result else None

    token_data = {
        "sub": current_user["user_id"],       # keeps original user_id
        "email": sa_user.email if sa_user else current_user.get("email", ""),
        "role": "ADMIN",                       # impersonated as broker admin
        "broker_id": broker_id,
        "impersonating": True,
        "original_role": "SUPERADMIN",
    }

    token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=_IMPERSONATION_TTL_MINUTES),
    )

    # Audit log
    try:
        audit_uid = int(current_user["user_id"])
    except (TypeError, ValueError):
        audit_uid = None
    await log_audit(
        db,
        user_id=audit_uid,
        broker_id=broker_id,
        action="impersonation_start",
        resource_type="broker",
        resource_id=broker_id,
        changes={"target_broker": broker.name},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return {
        "token": token,
        "broker_id": broker_id,
        "broker_name": broker.name,
        "expires_in": _IMPERSONATION_TTL_MINUTES * 60,
    }


@router.post("/impersonate/exit")
async def exit_impersonation(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates that the caller is currently impersonating, then logs the exit.
    The frontend is responsible for restoring the original token.
    """
    if not current_user.get("impersonating"):
        raise HTTPException(status_code=400, detail="No estás en modo impersonation")

    broker_id = current_user.get("broker_id")

    try:
        exit_uid = int(current_user["user_id"])
    except (TypeError, ValueError):
        exit_uid = None
    await log_audit(
        db,
        user_id=exit_uid,
        broker_id=broker_id,
        action="impersonation_end",
        resource_type="broker",
        resource_id=broker_id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return {"status": "exited"}


# ---------------------------------------------------------------------------
# Broker Chat Channel Configuration (WhatsApp / Telegram)
# ---------------------------------------------------------------------------

_SENSITIVE_FIELDS = {"access_token", "bot_token", "webhook_secret", "app_secret"}


class ChatConfigUpdate(BaseModel):
    enabled_providers: List[str]
    provider_configs: dict  # {"whatsapp": {...}, "telegram": {...}}


class ChatConfigResponse(BaseModel):
    broker_id: int
    enabled_providers: List[str]
    default_provider: str
    provider_configs: dict  # sensitive values replaced with "***"
    webhook_configs: dict


def _obfuscate_provider_configs(provider_configs: dict) -> dict:
    """Replace sensitive credential values with *** for safe display."""
    result = {}
    for provider, cfg in (provider_configs or {}).items():
        result[provider] = {
            k: ("***" if k in _SENSITIVE_FIELDS and v else v)
            for k, v in (cfg or {}).items()
        }
    return result


def _merge_provider_configs(existing: dict, incoming: dict) -> dict:
    """
    Merge incoming provider_configs into existing ones.
    For each provider: keep existing values, override with incoming ones.
    If an incoming value is "***", preserve the existing value (user didn't change it).
    """
    merged = dict(existing or {})
    for provider, new_cfg in (incoming or {}).items():
        old_cfg = merged.get(provider, {})
        merged_cfg = dict(old_cfg)
        for k, v in (new_cfg or {}).items():
            if v != "***":  # only update when user provided a real value
                merged_cfg[k] = v
        merged[provider] = merged_cfg
    return merged


@router.get("/brokers/{broker_id}/chat-config", response_model=ChatConfigResponse)
async def get_broker_chat_config(
    broker_id: int,
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Get chat channel configuration for a broker (credentials obfuscated)."""
    result = await db.execute(
        select(BrokerChatConfig).where(BrokerChatConfig.broker_id == broker_id)
    )
    cfg = result.scalars().first()
    if cfg is None:
        return ChatConfigResponse(
            broker_id=broker_id,
            enabled_providers=[],
            default_provider="webchat",
            provider_configs={},
            webhook_configs={},
        )
    return ChatConfigResponse(
        broker_id=broker_id,
        enabled_providers=cfg.enabled_providers or [],
        default_provider=cfg.default_provider.value if cfg.default_provider else "webchat",
        provider_configs=_obfuscate_provider_configs(cfg.provider_configs or {}),
        webhook_configs=cfg.webhook_configs or {},
    )


@router.put("/brokers/{broker_id}/chat-config", response_model=ChatConfigResponse)
async def update_broker_chat_config(
    broker_id: int,
    data: ChatConfigUpdate,
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upsert chat channel configuration for a broker.
    Existing credentials are preserved when the incoming value is "***".
    Automatically generates webhook_configs entries with the public webhook URLs.
    """
    # Verify broker exists
    broker_result = await db.execute(select(Broker).where(Broker.id == broker_id))
    if broker_result.scalars().first() is None:
        raise HTTPException(status_code=404, detail="Broker not found")

    result = await db.execute(
        select(BrokerChatConfig).where(BrokerChatConfig.broker_id == broker_id)
    )
    cfg = result.scalars().first()

    base_url = settings.WEBHOOK_BASE_URL.rstrip("/") if settings.WEBHOOK_BASE_URL else ""

    # Build updated webhook_configs
    webhook_configs: dict = {}
    if "whatsapp" in data.enabled_providers:
        webhook_configs["whatsapp"] = {
            "url": f"{base_url}/webhooks/whatsapp",
            "enabled": True,
        }
    if "telegram" in data.enabled_providers:
        webhook_configs["telegram"] = {
            "url": f"{base_url}/webhooks/telegram/{broker_id}",
            "enabled": True,
        }

    if cfg is None:
        cfg = BrokerChatConfig(
            broker_id=broker_id,
            enabled_providers=data.enabled_providers,
            provider_configs=data.provider_configs,
            webhook_configs=webhook_configs,
        )
        db.add(cfg)
    else:
        cfg.enabled_providers = data.enabled_providers
        cfg.provider_configs = _merge_provider_configs(
            cfg.provider_configs or {}, data.provider_configs
        )
        cfg.webhook_configs = webhook_configs

    await db.commit()
    await db.refresh(cfg)

    return ChatConfigResponse(
        broker_id=broker_id,
        enabled_providers=cfg.enabled_providers or [],
        default_provider=cfg.default_provider.value if cfg.default_provider else "webchat",
        provider_configs=_obfuscate_provider_configs(cfg.provider_configs or {}),
        webhook_configs=cfg.webhook_configs or {},
    )


@router.post("/brokers/{broker_id}/chat-config/register-webhook")
async def register_broker_webhook(
    broker_id: int,
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Register the Telegram webhook for this broker using the stored bot_token.
    The webhook URL is generated as: {BASE_URL}/webhooks/telegram/{broker_id}
    """
    result = await db.execute(
        select(BrokerChatConfig).where(BrokerChatConfig.broker_id == broker_id)
    )
    cfg = result.scalars().first()

    if cfg is None or not (cfg.provider_configs or {}).get("telegram", {}).get("bot_token"):
        raise HTTPException(
            status_code=400,
            detail="No Telegram bot_token configured. Save the configuration first.",
        )

    bot_token = cfg.provider_configs["telegram"]["bot_token"]
    base_url = settings.WEBHOOK_BASE_URL.rstrip("/") if settings.WEBHOOK_BASE_URL else ""
    webhook_url = f"{base_url}/webhooks/telegram/{broker_id}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": webhook_url},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Telegram API error: {resp.text}",
        )

    tg_result = resp.json()
    if not tg_result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail=f"Telegram setWebhook failed: {tg_result.get('description', 'unknown error')}",
        )

    # Update stored webhook_configs
    webhook_configs = cfg.webhook_configs or {}
    webhook_configs["telegram"] = {
        "url": webhook_url,
        "enabled": True,
        "registered_at": datetime.utcnow().isoformat(),
    }
    cfg.webhook_configs = webhook_configs
    await db.commit()

    return {
        "ok": True,
        "webhook_url": webhook_url,
        "telegram_response": tg_result,
    }

