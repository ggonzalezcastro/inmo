"""
Agent model configuration service.

Handles per-broker, per-agent LLM configuration with Redis write-through
cache for cross-worker consistency. Falls back to DB on cache miss.

All writes are performed by SUPERADMIN-only API endpoints — this module
handles only the read/write/invalidate logic.

Cache key: "agent_model_config:{broker_id}"
Cache value: JSON object mapping agent_type → config dict
Cache TTL: 1 hour (explicit invalidation on every write)
"""
import json
import logging
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.cache import cache_get_json, cache_set_json, cache_delete

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "agent_model_config:"
_CACHE_TTL = 3600  # 1 hour


def _cache_key(broker_id: int) -> str:
    return f"{_CACHE_PREFIX}{broker_id}"


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert an AgentModelConfig ORM row to a plain dict safe for JSON."""
    return {
        "id": row.id,
        "broker_id": row.broker_id,
        "agent_type": row.agent_type,
        "llm_provider": row.llm_provider,
        "llm_model": row.llm_model,
        "temperature": row.temperature,
        "max_tokens": row.max_tokens,
        "is_active": row.is_active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


# ── Read helpers ──────────────────────────────────────────────────────────────

async def _fetch_from_db(broker_id: int, db: AsyncSession) -> Dict[str, Dict]:
    """Load all active agent model configs for a broker from the DB."""
    from app.models.agent_model_config import AgentModelConfig
    result = await db.execute(
        select(AgentModelConfig).where(
            AgentModelConfig.broker_id == broker_id,
            AgentModelConfig.is_active == True,  # noqa: E712
        )
    )
    rows = result.scalars().all()
    return {row.agent_type: _row_to_dict(row) for row in rows}


async def load_all_agent_configs(broker_id: int, db: AsyncSession) -> Dict[str, Dict]:
    """
    Load all agent model configs for a broker.

    Tries Redis first; on miss, queries DB and writes through to Redis.
    Returns a dict of agent_type → config dict (may be empty if no configs set).
    """
    cached = await cache_get_json(_cache_key(broker_id))
    if cached is not None:
        return cached

    configs = await _fetch_from_db(broker_id, db)
    await cache_set_json(_cache_key(broker_id), configs, ttl_seconds=_CACHE_TTL)
    return configs


async def get_agent_model_config(
    broker_id: int,
    agent_type: str,
    db: AsyncSession,
) -> Optional[Dict[str, Any]]:
    """
    Get the active LLM config for a specific agent within a broker.

    Returns None if no config is set (callers should fall back to global provider).
    """
    all_configs = await load_all_agent_configs(broker_id, db)
    return all_configs.get(agent_type)


async def invalidate_agent_configs(broker_id: int) -> None:
    """Invalidate Redis cache for a broker's agent configs."""
    await cache_delete(_cache_key(broker_id))
    logger.debug("[AgentModelConfig] Cache invalidated for broker %s", broker_id)


# ── Write helpers ─────────────────────────────────────────────────────────────

async def upsert_agent_model_config(
    broker_id: int,
    agent_type: str,
    llm_provider: str,
    llm_model: str,
    temperature: Optional[float],
    max_tokens: Optional[int],
    is_active: bool,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Create or update an agent model config for a broker.

    Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE (upsert) to handle
    the unique constraint on (broker_id, agent_type) atomically.
    """
    from app.models.agent_model_config import AgentModelConfig

    stmt = (
        pg_insert(AgentModelConfig)
        .values(
            broker_id=broker_id,
            agent_type=agent_type,
            llm_provider=llm_provider,
            llm_model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
            is_active=is_active,
        )
        .on_conflict_do_update(
            constraint="uq_agent_model_config_broker_agent",
            set_={
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "is_active": is_active,
            },
        )
        .returning(AgentModelConfig)
    )
    result = await db.execute(stmt)
    await db.commit()
    row = result.scalars().first()

    await invalidate_agent_configs(broker_id)
    logger.info(
        "[AgentModelConfig] Upserted broker=%s agent=%s provider=%s model=%s",
        broker_id, agent_type, llm_provider, llm_model,
    )
    return _row_to_dict(row)


async def delete_agent_model_config(
    broker_id: int,
    agent_type: str,
    db: AsyncSession,
) -> bool:
    """
    Delete an agent model config, reverting that agent to the global provider.
    Returns True if a row was deleted, False if no config existed.
    """
    from app.models.agent_model_config import AgentModelConfig
    result = await db.execute(
        select(AgentModelConfig).where(
            AgentModelConfig.broker_id == broker_id,
            AgentModelConfig.agent_type == agent_type,
        )
    )
    row = result.scalars().first()
    if row is None:
        return False

    await db.delete(row)
    await db.commit()
    await invalidate_agent_configs(broker_id)
    logger.info(
        "[AgentModelConfig] Deleted broker=%s agent=%s (reverted to global)",
        broker_id, agent_type,
    )
    return True


async def list_agent_model_configs(
    broker_id: int,
    db: AsyncSession,
) -> List[Dict[str, Any]]:
    """Return all configs for a broker (including inactive), direct from DB."""
    from app.models.agent_model_config import AgentModelConfig
    result = await db.execute(
        select(AgentModelConfig)
        .where(AgentModelConfig.broker_id == broker_id)
        .order_by(AgentModelConfig.agent_type)
    )
    return [_row_to_dict(r) for r in result.scalars().all()]
