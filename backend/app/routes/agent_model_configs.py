"""
Agent Model Configuration endpoints — SUPERADMIN only.

Mounted at: /api/v1/admin/agent-models

Allows SUPERADMIN to configure which LLM provider/model each agent type uses
for a specific broker. Falls back to global env-var configuration when no
per-broker override is set.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.permissions import Permissions
from app.models.agent_model_config import VALID_AGENT_TYPES, VALID_PROVIDERS
from app.schemas.agent_model_config import (
    AgentModelConfigCreate,
    AgentModelConfigUpdate,
    AgentModelConfigResponse,
    AgentModelConfigList,
    AvailableProviderInfo,
    AvailableProvidersResponse,
)
from app.services.agents.model_config import (
    list_agent_model_configs,
    get_agent_model_config,
    upsert_agent_model_config,
    delete_agent_model_config,
)
from app.config import settings

router = APIRouter()


def _check_provider_availability(provider_name: str) -> bool:
    """Return True if the provider has an API key configured."""
    name = provider_name.lower()
    if name == "gemini":
        return bool(getattr(settings, "GEMINI_API_KEY", ""))
    if name == "claude":
        return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))
    if name == "openai":
        return bool(getattr(settings, "OPENAI_API_KEY", ""))
    if name == "openrouter":
        return bool(getattr(settings, "OPENROUTER_API_KEY", ""))
    return False


def _default_model_for_provider(provider_name: str) -> str:
    name = provider_name.lower()
    if name == "gemini":
        return getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    if name == "claude":
        return getattr(settings, "CLAUDE_MODEL", "claude-sonnet-4-20250514")
    if name == "openai":
        return getattr(settings, "OPENAI_MODEL", "gpt-4o")
    if name == "openrouter":
        return getattr(settings, "OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
    return ""


# ── List available providers ─────────────────────────────────────────────────

@router.get("/available-providers", response_model=AvailableProvidersResponse)
async def list_available_providers(
    current_user: dict = Depends(Permissions.require_superadmin),
):
    """
    List all LLM providers with their availability status (API key present).
    Used by the admin UI to populate the provider selector.
    """
    return AvailableProvidersResponse(
        providers=[
            AvailableProviderInfo(
                provider=p,
                is_configured=_check_provider_availability(p),
                default_model=_default_model_for_provider(p),
            )
            for p in sorted(VALID_PROVIDERS)
        ]
    )


# ── List configs for a broker ────────────────────────────────────────────────

@router.get("", response_model=AgentModelConfigList)
async def list_agent_model_configs_endpoint(
    broker_id: int = Query(..., description="Broker ID to query"),
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """List all agent model configs for a broker (including inactive)."""
    configs = await list_agent_model_configs(broker_id, db)
    return AgentModelConfigList(
        configs=[AgentModelConfigResponse(**c) for c in configs],
        total=len(configs),
    )


# ── Get single config ────────────────────────────────────────────────────────

@router.get("/{agent_type}", response_model=AgentModelConfigResponse)
async def get_agent_model_config_endpoint(
    agent_type: str,
    broker_id: int = Query(..., description="Broker ID to query"),
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Get the active LLM config for a specific agent within a broker."""
    if agent_type not in VALID_AGENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"agent_type must be one of: {sorted(VALID_AGENT_TYPES)}",
        )
    config = await get_agent_model_config(broker_id, agent_type, db)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"No model config found for agent '{agent_type}' on broker {broker_id}",
        )
    return AgentModelConfigResponse(**config)


# ── Create / update config ────────────────────────────────────────────────────

@router.put("/{agent_type}", response_model=AgentModelConfigResponse)
async def upsert_agent_model_config_endpoint(
    agent_type: str,
    body: AgentModelConfigCreate,
    broker_id: int = Query(..., description="Broker ID to configure"),
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create or update the LLM model config for a specific agent within a broker.

    If a config already exists for (broker_id, agent_type), it is updated.
    Validates that the selected provider is available (API key configured).
    """
    if agent_type not in VALID_AGENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"agent_type must be one of: {sorted(VALID_AGENT_TYPES)}",
        )
    if body.agent_type != agent_type:
        raise HTTPException(
            status_code=422,
            detail="agent_type in URL and body must match",
        )
    if not _check_provider_availability(body.llm_provider):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Provider '{body.llm_provider}' is not configured on this server "
                f"(missing API key). Configure the key before assigning this provider."
            ),
        )

    config = await upsert_agent_model_config(
        broker_id=broker_id,
        agent_type=agent_type,
        llm_provider=body.llm_provider,
        llm_model=body.llm_model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        is_active=body.is_active,
        db=db,
    )
    return AgentModelConfigResponse(**config)


# ── Delete config ────────────────────────────────────────────────────────────

@router.delete("/{agent_type}", status_code=204)
async def delete_agent_model_config_endpoint(
    agent_type: str,
    broker_id: int = Query(..., description="Broker ID to configure"),
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete the LLM model config for a specific agent, reverting it to the global
    env-var configured provider.
    """
    if agent_type not in VALID_AGENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"agent_type must be one of: {sorted(VALID_AGENT_TYPES)}",
        )
    deleted = await delete_agent_model_config(broker_id, agent_type, db)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No model config found for agent '{agent_type}' on broker {broker_id}",
        )
