"""
Broker configuration routes
Endpoints for managing broker prompt and lead configuration
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import Permissions
from app.schemas.broker import PromptConfigUpdate, LeadConfigUpdate
from app.models.broker import Broker, BrokerPromptConfig, BrokerLeadConfig
from app.models.prompt_version import PromptVersion
from app.services.broker import BrokerConfigService
from app.core.cache import cache_delete
from app.core.config import settings
from app.core.encryption import encrypt_value, decrypt_value
from sqlalchemy.future import select
from sqlalchemy import text, update
import logging
from jose import jwt, JWTError
import time

router = APIRouter()
logger = logging.getLogger(__name__)


async def _auto_snapshot_prompt(db: AsyncSession, broker_id: int, user_id: int):
    """
    Generate the current effective prompt and save it as a PromptVersion snapshot.
    Called automatically after any config change. Version tags use auto-incrementing
    numbers: auto-001, auto-002, etc. The new snapshot is set as active.
    Non-blocking: errors are logged but do not fail the parent request.
    """
    try:
        from app.services.broker.prompt_service import build_system_prompt

        # Build the current effective prompt
        prompt_text = await build_system_prompt(db=db, broker_id=broker_id)

        # Find the highest existing auto-N tag for this broker
        result = await db.execute(
            select(PromptVersion)
            .where(
                PromptVersion.broker_id == broker_id,
                PromptVersion.version_tag.like("auto-%"),
            )
            .order_by(PromptVersion.id.desc())
            .limit(1)
        )
        last = result.scalars().first()
        next_num = 1
        if last:
            try:
                next_num = int(last.version_tag.split("-")[1]) + 1
            except Exception:
                pass
        version_tag = f"auto-{next_num:03d}"

        # Deactivate previous versions
        await db.execute(
            update(PromptVersion)
            .where(PromptVersion.broker_id == broker_id)
            .values(is_active=False)
        )

        # Create new snapshot as active
        snapshot = PromptVersion(
            broker_id=broker_id,
            created_by=user_id,
            version_tag=version_tag,
            is_active=True,
            content=prompt_text,
        )
        db.add(snapshot)
        await db.commit()
        logger.info(
            "Auto-snapshot created: broker_id=%s tag=%r", broker_id, version_tag
        )
    except Exception as exc:
        logger.warning("Auto-snapshot failed for broker_id=%s: %s", broker_id, exc)


async def _ensure_default_configs(db: AsyncSession, broker_id: int):
    """Ensure default configurations exist for a broker, create them if not"""
    # This function is not used anymore - we'll return None configs and let the endpoint handle defaults
    # This avoids ORM queries that try to select non-existent columns
    return None, None


@router.get("/config")
async def get_broker_config(
    broker_id: Optional[int] = Query(None, description="Broker ID (required for superadmin, optional for admin)"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get complete broker configuration"""
    try:
        user_role = current_user.get("role", "").upper()
        
        # Determine which broker_id to use
        if user_role == "SUPERADMIN":
            # Superadmin must specify broker_id
            if not broker_id:
                # Return list of available brokers for superadmin to choose from
                brokers_result = await db.execute(
                    select(Broker).where(Broker.is_active == True)
                )
                brokers = brokers_result.scalars().all()
                
                return {
                    "error": "broker_id_required",
                    "message": "Para superadmin, debes especificar el broker_id como parámetro de consulta (?broker_id=1)",
                    "available_brokers": [
                        {
                            "id": broker.id,
                            "name": broker.name,
                            "slug": broker.slug,
                            "contact_email": broker.contact_email,
                            "contact_phone": broker.contact_phone
                        }
                        for broker in brokers
                    ]
                }
            
            target_broker_id = broker_id
        else:
            # Admin uses their own broker_id
            target_broker_id = current_user.get("broker_id")
            if not target_broker_id:
                raise HTTPException(status_code=404, detail="User does not belong to a broker")
            
            # If admin provided broker_id, verify they can access it (only their own)
            if broker_id and broker_id != target_broker_id:
                raise HTTPException(
                    status_code=403, 
                    detail="Solo puedes acceder a la configuración de tu propio broker"
                )
        
        # Get broker
        broker_result = await db.execute(
            select(Broker).where(Broker.id == target_broker_id)
        )
        broker = broker_result.scalars().first()
        
        if not broker:
            raise HTTPException(status_code=404, detail="Broker not found")
        
        # Get prompt config using raw SQL - only select columns that exist
        # Use minimal query to avoid missing column errors
        prompt_config_data = None
        try:
            # Try to get only basic columns first
            result = await db.execute(
                text("""
                    SELECT broker_id, agent_name, agent_role, enable_appointment_booking, id
                    FROM broker_prompt_configs 
                    WHERE broker_id = :broker_id
                    LIMIT 1
                """),
                {"broker_id": target_broker_id}
            )
            row = result.first()
            if row:
                prompt_config_data = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                # Try to get additional columns if they exist
                try:
                    result2 = await db.execute(
                        text("""
                            SELECT identity_prompt, business_context, agent_objective, 
                                   data_collection_prompt, behavior_rules, restrictions, 
                                   situation_handlers, output_format, full_custom_prompt, 
                                   tools_instructions, meeting_config
                            FROM broker_prompt_configs 
                            WHERE broker_id = :broker_id
                            LIMIT 1
                        """),
                        {"broker_id": target_broker_id}
                    )
                    row2 = result2.first()
                    if row2:
                        extra_data = dict(row2._mapping) if hasattr(row2, '_mapping') else dict(row2)
                        prompt_config_data.update(extra_data)
                except Exception:
                    # Some columns might not exist, that's ok
                    pass
        except Exception as e:
            logger.warning(f"Prompt config table might not exist or have different schema: {e}")
            prompt_config_data = None
        
        # Get lead config using raw SQL — only select columns guaranteed to exist
        lead_config_data = None
        try:
            result = await db.execute(
                text("""
                    SELECT broker_id, field_weights, cold_max_score, warm_max_score, 
                           hot_min_score, qualified_min_score, field_priority, 
                           max_acceptable_debt, scoring_config,
                           alert_on_hot_lead, alert_on_qualified, alert_score_threshold, alert_email,
                           id, created_at, updated_at
                    FROM broker_lead_configs 
                    WHERE broker_id = :broker_id
                """),
                {"broker_id": target_broker_id}
            )
            row = result.first()
            if row:
                lead_config_data = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
        except Exception as e:
            logger.warning(f"Error loading lead config (using defaults): {e}")
            lead_config_data = None
        
        # Helper function to safely get from dict
        def safe_get(d, key, default=None):
            if not d:
                return default
            return d.get(key, default)
        
        return {
            "broker": {
                "id": broker.id,
                "name": broker.name,
                "slug": broker.slug,
                "contact_phone": broker.contact_phone,
                "contact_email": broker.contact_email,
                "business_hours": broker.business_hours,
                "service_zones": broker.service_zones,
                "is_active": broker.is_active,
                "priority_assignment_enabled": getattr(broker, "priority_assignment_enabled", False),
            },
            "prompt_config": {
                "agent_name": safe_get(prompt_config_data, 'agent_name', 'Sofía'),
                "agent_role": safe_get(prompt_config_data, 'agent_role', 'asesora inmobiliaria'),
                "identity_prompt": safe_get(prompt_config_data, 'identity_prompt', None),
                "business_context": safe_get(prompt_config_data, 'business_context', None),
                "agent_objective": safe_get(prompt_config_data, 'agent_objective', None),
                "data_collection_prompt": safe_get(prompt_config_data, 'data_collection_prompt', None),
                "behavior_rules": safe_get(prompt_config_data, 'behavior_rules', None),
                "restrictions": safe_get(prompt_config_data, 'restrictions', None),
                "situation_handlers": safe_get(prompt_config_data, 'situation_handlers', None),
                "output_format": safe_get(prompt_config_data, 'output_format', None),
                "full_custom_prompt": safe_get(prompt_config_data, 'full_custom_prompt', None),
                "enable_appointment_booking": safe_get(prompt_config_data, 'enable_appointment_booking', True),
                "tools_instructions": safe_get(prompt_config_data, 'tools_instructions', None),
                "timezone": (safe_get(prompt_config_data, 'meeting_config') or {}).get('timezone', 'America/Santiago'),
            },
            "lead_config": {
                "field_weights": safe_get(lead_config_data, 'field_weights', {
                    "name": 10, "phone": 15, "email": 10, "location": 15, 
                    "monthly_income": 25, "dicom_status": 20, "budget": 10
                }),
                "cold_max_score": safe_get(lead_config_data, 'cold_max_score', 20),
                "warm_max_score": safe_get(lead_config_data, 'warm_max_score', 50),
                "hot_min_score": safe_get(lead_config_data, 'hot_min_score', 50),
                "qualified_min_score": safe_get(lead_config_data, 'qualified_min_score', 75),
                "field_priority": safe_get(lead_config_data, 'field_priority', [
                    'name', 'phone', 'email', 'location', 'monthly_income', 'dicom_status', 'budget'
                ]),
                "income_ranges": safe_get(lead_config_data, 'income_ranges', None),
                "qualification_criteria": safe_get(lead_config_data, 'qualification_criteria', None),
                "max_acceptable_debt": safe_get(lead_config_data, 'max_acceptable_debt', 0),
                "scoring_config": safe_get(lead_config_data, 'scoring_config') or {
                    "income_tiers": [
                        {"min": 3000000, "label": "Excelente", "points": 40},
                        {"min": 2000000, "label": "Alto", "points": 32},
                        {"min": 1000000, "label": "Medio", "points": 20},
                        {"min": 500000, "label": "Bajo", "points": 10},
                        {"min": 0, "label": "Insuficiente", "points": 0}
                    ],
                    "dicom_clean_pts": 20,
                    "dicom_has_debt_pts": 8
                },
                "alert_on_hot_lead": safe_get(lead_config_data, 'alert_on_hot_lead', True),
                "alert_on_qualified": safe_get(lead_config_data, 'alert_on_qualified', True),
                "alert_score_threshold": safe_get(lead_config_data, 'alert_score_threshold', 70),
                "alert_email": safe_get(lead_config_data, 'alert_email', None)
            }
        }
    except HTTPException:
        # Re-raise HTTP exceptions (they already have proper status codes)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_broker_config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al cargar configuración del broker: {str(e)}"
        )


@router.put("/config/assignment")
async def update_assignment_config(
    body: dict,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle priority-based lead assignment on or off for this broker."""
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=404, detail="User does not belong to a broker")

    enabled = body.get("priority_assignment_enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=422, detail="priority_assignment_enabled must be a boolean")

    result = await db.execute(select(Broker).where(Broker.id == broker_id))
    broker = result.scalars().first()
    if not broker:
        raise HTTPException(status_code=404, detail="Broker no encontrado")

    broker.priority_assignment_enabled = enabled
    await db.commit()
    return {"priority_assignment_enabled": broker.priority_assignment_enabled}


@router.put("/config/prompt")
async def update_prompt_config(
    updates: PromptConfigUpdate,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update prompt configuration (admin only)"""
    
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=404, detail="User does not belong to a broker")
    
    # Get or create prompt config
    result = await db.execute(
        select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
    )
    prompt_config = result.scalars().first()
    
    if not prompt_config:
        # Create new config
        prompt_config = BrokerPromptConfig(broker_id=broker_id)
        db.add(prompt_config)
    
    # Update fields
    update_data = updates.model_dump(exclude_unset=True)
    timezone = update_data.pop("timezone", None)
    for key, value in update_data.items():
        setattr(prompt_config, key, value)
    # Persist timezone inside meeting_config JSONB
    if timezone is not None:
        current_meeting = dict(prompt_config.meeting_config or {})
        current_meeting["timezone"] = timezone
        prompt_config.meeting_config = current_meeting
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(prompt_config, "meeting_config")
    
    await db.commit()
    await db.refresh(prompt_config)
    
    await cache_delete(f"broker_prompt:{broker_id}")
    logger.info(f"Prompt config updated for broker {broker_id} - cache invalidated")

    # Auto-snapshot: save the current effective prompt as a new version
    user_id = int(current_user.get("id") or current_user.get("user_id") or 0)
    await _auto_snapshot_prompt(db, broker_id, user_id)

    return {
        "message": "Prompt configuration updated successfully",
        "config": {
            "agent_name": prompt_config.agent_name,
            "agent_role": prompt_config.agent_role,
            "has_custom_prompt": bool(prompt_config.full_custom_prompt)
        }
    }


@router.put("/config/leads")
async def update_lead_config(
    updates: LeadConfigUpdate,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update lead scoring configuration (admin only)"""
    
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=404, detail="User does not belong to a broker")
    
    # Get or create lead config
    result = await db.execute(
        select(BrokerLeadConfig).where(BrokerLeadConfig.broker_id == broker_id)
    )
    lead_config = result.scalars().first()
    
    if not lead_config:
        # Create new config
        lead_config = BrokerLeadConfig(broker_id=broker_id)
        db.add(lead_config)
    
    # Update fields
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lead_config, key, value)
    
    await db.commit()
    await db.refresh(lead_config)
    
    logger.info(f"Lead config updated for broker {broker_id} - Changes will be applied immediately in next chat message")

    # Auto-snapshot: save the current effective prompt as a new version
    user_id = int(current_user.get("id") or current_user.get("user_id") or 0)
    await _auto_snapshot_prompt(db, broker_id, user_id)

    return {
        "message": "Lead configuration updated successfully",
        "config": {
            "field_weights": lead_config.field_weights,
            "cold_max_score": lead_config.cold_max_score,
            "warm_max_score": lead_config.warm_max_score,
            "hot_min_score": lead_config.hot_min_score,
            "scoring_config": lead_config.scoring_config,
        }
    }


@router.get("/config/prompt/preview")
async def preview_prompt(
    broker_id: Optional[int] = Query(None, description="Broker ID (required for superadmin, optional for admin)"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Preview the current system prompt that will be used"""
    try:
        user_role = current_user.get("role", "").upper()
        
        # Determine which broker_id to use
        if user_role == "SUPERADMIN":
            if not broker_id:
                raise HTTPException(
                    status_code=400,
                    detail="Para superadmin, debes especificar el broker_id como parámetro de consulta (?broker_id=1)"
                )
            target_broker_id = broker_id
        else:
            target_broker_id = current_user.get("broker_id")
            if not target_broker_id:
                raise HTTPException(status_code=404, detail="User does not belong to a broker")
            
            # If admin provided broker_id, verify they can access it (only their own)
            if broker_id and broker_id != target_broker_id:
                raise HTTPException(
                    status_code=403,
                    detail="Solo puedes ver el preview del prompt de tu propio broker"
                )
        
        prompt = await BrokerConfigService.build_system_prompt(db, target_broker_id)
        
        return {
            "prompt": prompt,
            "length": len(prompt)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating prompt preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar preview del prompt: {str(e)}"
        )


@router.get("/config/agent-prompts")
async def get_agent_prompts(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the default agent prompts and any broker-level custom overrides.
    Custom overrides are stored in situation_handlers under _agent_* keys.
    """
    import os
    from app.services.agents.prompts.qualifier_prompt import QUALIFIER_SYSTEM_PROMPT
    from app.services.agents.prompts.scheduler_prompt import SCHEDULER_SYSTEM_PROMPT
    from app.services.agents.prompts.follow_up_prompt import FOLLOW_UP_SYSTEM_PROMPT

    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=404, detail="User does not belong to a broker")

    # Load broker custom overrides from situation_handlers
    overrides = {}
    try:
        result = await db.execute(
            select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
        )
        cfg = result.scalars().first()
        if cfg and isinstance(cfg.situation_handlers, dict):
            overrides = {
                k[len("_agent_"):]: v
                for k, v in cfg.situation_handlers.items()
                if k.startswith("_agent_") and v
            }
    except Exception as e:
        logger.warning("Could not load agent prompt overrides: %s", e)

    multi_agent_enabled = os.getenv("MULTI_AGENT_ENABLED", "false").lower() == "true"

    # Build preview placeholders for display
    preview_data = {
        "qualifier": {
            "default": QUALIFIER_SYSTEM_PROMPT.replace("{agent_name}", "Sofía").replace("{broker_name}", "tu inmobiliaria"),
            "custom": overrides.get("qualifier", ""),
        },
        "scheduler": {
            "default": SCHEDULER_SYSTEM_PROMPT.replace("{agent_name}", "Sofía").replace("{broker_name}", "tu inmobiliaria").replace("{current_datetime}", "[fecha actual]").replace("{lead_id}", "[id]").replace("{lead_summary}", "[resumen del lead]").replace("{available_projects}", "[proyectos disponibles]"),
            "custom": overrides.get("scheduler", ""),
        },
        "follow_up": {
            "default": FOLLOW_UP_SYSTEM_PROMPT.replace("{agent_name}", "Sofía").replace("{broker_name}", "tu inmobiliaria").replace("{lead_summary}", "[resumen del lead]"),
            "custom": overrides.get("follow_up", ""),
        },
        "multi_agent_enabled": multi_agent_enabled,
    }
    return preview_data


@router.put("/config/agent-prompts")
async def save_agent_prompts(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save broker-level custom overrides for the agent prompts.
    Pass empty string to reset to default for a given agent.
    """
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=404, detail="User does not belong to a broker")

    qualifier_custom = (body.get("qualifier") or "").strip()
    scheduler_custom = (body.get("scheduler") or "").strip()
    follow_up_custom = (body.get("follow_up") or "").strip()
    property_custom = (body.get("property") or "").strip()
    # Skill extensions — appended after the base skill document for each agent
    skill_qualifier = (body.get("skill_qualifier") or "").strip()
    skill_scheduler = (body.get("skill_scheduler") or "").strip()
    skill_follow_up = (body.get("skill_follow_up") or "").strip()
    skill_property = (body.get("skill_property") or "").strip()

    try:
        result = await db.execute(
            select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
        )
        cfg = result.scalars().first()
        if not cfg:
            raise HTTPException(status_code=404, detail="No prompt config found for this broker")

        handlers = dict(cfg.situation_handlers or {})
        # Store / clear prompt overrides and skill extensions
        for key, val in [
            ("_agent_qualifier", qualifier_custom),
            ("_agent_scheduler", scheduler_custom),
            ("_agent_follow_up", follow_up_custom),
            ("_agent_property", property_custom),
            ("_skill_qualifier", skill_qualifier),
            ("_skill_scheduler", skill_scheduler),
            ("_skill_follow_up", skill_follow_up),
            ("_skill_property", skill_property),
        ]:
            if val:
                handlers[key] = val
            else:
                handlers.pop(key, None)

        cfg.situation_handlers = handlers
        await db.commit()

        # Invalidate broker prompt cache
        from app.core.cache import cache_delete
        await cache_delete(f"broker_prompt:{broker_id}")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error saving agent prompts: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True}


@router.get("/config/defaults")
async def get_default_config(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get default configuration values"""
    
    # Use the service to get defaults
    defaults = await BrokerConfigService.get_default_config(db)
    
    return {
        "prompt": {
            "agent_name": "Sofía",
            "agent_role": "asesora inmobiliaria",
            "enable_appointment_booking": True,
            "default_system_prompt": BrokerConfigService.DEFAULT_SYSTEM_PROMPT
        },
        "leads": defaults
    }


# ── Prompt Versions ──────────────────────────────────────────────────────────

def _resolve_broker_id(current_user: dict, broker_id: int) -> int:
    """Return the target broker_id, enforcing admin scope."""
    role = current_user.get("role", "").upper()
    if role == "SUPERADMIN":
        return broker_id
    user_broker_id = current_user.get("broker_id")
    if not user_broker_id:
        raise HTTPException(status_code=404, detail="User does not belong to a broker")
    if broker_id != user_broker_id:
        raise HTTPException(status_code=403, detail="Solo puedes acceder a la configuración de tu propio broker")
    return user_broker_id


@router.get("/brokers/{broker_id}/prompts")
async def list_prompt_versions(
    broker_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all prompt versions for a broker (newest first)."""
    _resolve_broker_id(current_user, broker_id)

    result = await db.execute(
        select(PromptVersion)
        .where(PromptVersion.broker_id == broker_id)
        .order_by(PromptVersion.id.desc())
    )
    versions = result.scalars().all()

    return {
        "broker_id": broker_id,
        "versions": [
            {
                "id": v.id,
                "version_tag": v.version_tag,
                "prompt_type": v.prompt_type,
                "is_active": v.is_active,
                "notes": v.notes,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                # Performance metrics (populated by background task)
                "total_uses": v.total_uses,
                "avg_tokens_per_call": v.avg_tokens_per_call,
                "avg_latency_ms": v.avg_latency_ms,
                "avg_lead_score_delta": v.avg_lead_score_delta,
                "escalation_rate": v.escalation_rate,
            }
            for v in versions
        ],
    }


@router.post("/brokers/{broker_id}/prompts", status_code=201)
async def create_prompt_version(
    broker_id: int,
    payload: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new prompt version for a broker.

    Body fields:
    - version_tag (str, required): e.g. "v2.0.0"
    - content (str, required): full prompt text
    - sections_json (object, optional): structured sections dict
    - activate (bool, optional, default false): immediately activate this version
    """
    _resolve_broker_id(current_user, broker_id)

    version_tag: str = payload.get("version_tag", "").strip()
    content: str = payload.get("content", "").strip()

    if not version_tag:
        raise HTTPException(status_code=422, detail="version_tag is required")
    if not content:
        raise HTTPException(status_code=422, detail="content is required")

    # Check for duplicate tag within this broker
    existing = await db.execute(
        select(PromptVersion).where(
            PromptVersion.broker_id == broker_id,
            PromptVersion.version_tag == version_tag,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=f"Version {version_tag!r} already exists for this broker",
        )

    user_id: Optional[int] = current_user.get("id")
    activate: bool = bool(payload.get("activate", False))

    if activate:
        # Deactivate all existing versions for this broker
        await db.execute(
            update(PromptVersion)
            .where(PromptVersion.broker_id == broker_id)
            .values(is_active=False)
        )

    new_version = PromptVersion(
        broker_id=broker_id,
        version_tag=version_tag,
        content=content,
        sections_json=payload.get("sections_json"),
        is_active=activate,
        created_by=user_id,
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)

    if activate:
        # Invalidate cached prompt for this broker
        await cache_delete(f"broker_prompt:{broker_id}")

    logger.info(
        "PromptVersion created broker_id=%s tag=%r active=%s by user_id=%s",
        broker_id, version_tag, activate, user_id,
    )

    return {
        "id": new_version.id,
        "broker_id": broker_id,
        "version_tag": new_version.version_tag,
        "is_active": new_version.is_active,
        "created_at": new_version.created_at.isoformat() if new_version.created_at else None,
    }


@router.put("/brokers/{broker_id}/prompts/{version_id}/activate")
async def activate_prompt_version(
    broker_id: int,
    version_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Activate a specific prompt version (atomically deactivates all others).
    Returns the newly-active version metadata.
    """
    _resolve_broker_id(current_user, broker_id)

    result = await db.execute(
        select(PromptVersion).where(
            PromptVersion.id == version_id,
            PromptVersion.broker_id == broker_id,
        )
    )
    version = result.scalars().first()
    if not version:
        raise HTTPException(status_code=404, detail="Prompt version not found")

    # Deactivate all versions for this broker, then activate the target
    await db.execute(
        update(PromptVersion)
        .where(PromptVersion.broker_id == broker_id)
        .values(is_active=False)
    )
    version.is_active = True
    await db.commit()
    await db.refresh(version)

    # Invalidate cached prompt
    await cache_delete(f"broker_prompt:{broker_id}")

    logger.info(
        "PromptVersion activated broker_id=%s version_id=%s tag=%r by user_id=%s",
        broker_id, version_id, version.version_tag, current_user.get("id"),
    )

    return {
        "id": version.id,
        "broker_id": broker_id,
        "version_tag": version.version_tag,
        "is_active": version.is_active,
        "activated_at": version.updated_at.isoformat() if version.updated_at else None,
    }


# ── Google Calendar OAuth por Broker ─────────────────────────────────────────

GOOGLE_OAUTH_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_STATE_TTL = 600  # 10 minutos


def _make_state(broker_id: int) -> str:
    """Create a signed JWT state for the OAuth flow."""
    payload = {"broker_id": broker_id, "exp": int(time.time()) + _STATE_TTL}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def _verify_state(state: str) -> int:
    """Decode and verify the state JWT. Returns broker_id."""
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
        return int(payload["broker_id"])
    except (JWTError, Exception):
        raise HTTPException(status_code=400, detail="Estado OAuth inválido o expirado")


@router.get("/calendar/auth-url")
async def get_calendar_auth_url(
    current_user: dict = Depends(Permissions.require_admin),
):
    """
    Generate the Google OAuth URL for the current broker.
    The frontend opens this URL in a popup/new tab.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth no está configurado (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET faltantes)",
        )

    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    try:
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=GOOGLE_OAUTH_SCOPES,
        )
        flow.redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=_make_state(broker_id),
        )
        return {"auth_url": auth_url}
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Librería google-auth-oauthlib no instalada",
        )


@router.get("/calendar/callback")
async def calendar_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Google OAuth2 callback — public endpoint (no JWT auth).
    Exchanges the authorization code for tokens, stores the encrypted
    refresh_token in broker_prompt_configs, then redirects to the frontend.
    """
    broker_id = _verify_state(state)

    try:
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=GOOGLE_OAUTH_SCOPES,
            state=state,
        )
        flow.redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI
        flow.fetch_token(code=code)

        credentials = flow.credentials
        refresh_token = credentials.refresh_token
        if not refresh_token:
            return RedirectResponse(
                f"{settings.FRONTEND_URL}/settings?tab=calendar&status=error&reason=no_refresh_token"
            )

        # Get the Gmail address from the token info
        calendar_email = None
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {credentials.token}"},
                )
                if resp.status_code == 200:
                    calendar_email = resp.json().get("email")
        except Exception:
            pass  # email is optional

        # Save encrypted refresh token to DB
        result = await db.execute(
            select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
        )
        broker_config = result.scalars().first()

        if not broker_config:
            broker_config = BrokerPromptConfig(broker_id=broker_id)
            db.add(broker_config)

        broker_config.google_refresh_token = encrypt_value(refresh_token)
        broker_config.google_calendar_id = broker_config.google_calendar_id or "primary"
        broker_config.calendar_provider = "google"
        if calendar_email:
            broker_config.google_calendar_email = calendar_email

        await db.commit()
        logger.info("Google Calendar conectado para broker_id=%s email=%s", broker_id, calendar_email)

    except Exception as e:
        logger.error("Error en callback OAuth Google Calendar broker_id=%s: %s", broker_id, e, exc_info=True)
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/settings?tab=calendar&calendar=google&status=error&reason=callback_failed"
        )

    return RedirectResponse(
        f"{settings.FRONTEND_URL}/settings?tab=calendar&calendar=google&status=success"
    )


@router.get("/calendar/status")
async def get_calendar_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return Google Calendar connection status for the current broker."""
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    result = await db.execute(
        select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
    )
    cfg = result.scalars().first()

    if not cfg or not cfg.google_refresh_token:
        return {"connected": False, "email": None, "calendar_id": None}

    return {
        "connected": True,
        "email": cfg.google_calendar_email,
        "calendar_id": cfg.google_calendar_id or "primary",
    }


@router.delete("/calendar/disconnect")
async def disconnect_calendar(
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove Google Calendar credentials for the current broker."""
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    result = await db.execute(
        select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
    )
    cfg = result.scalars().first()

    if cfg:
        cfg.google_refresh_token = None
        cfg.google_calendar_email = None
        cfg.calendar_provider = "none"
        await db.commit()
        logger.info("Google Calendar desconectado para broker_id=%s", broker_id)

    return {"ok": True, "message": "Google Calendar desconectado"}


# ── Combined calendar status ───────────────────────────────────────────────────

@router.get("/calendar/all-status")
async def get_all_calendar_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return connection status for both Google and Outlook calendars."""
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    result = await db.execute(
        select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
    )
    cfg = result.scalars().first()

    google_connected = bool(cfg and cfg.google_refresh_token)
    outlook_connected = bool(cfg and cfg.outlook_refresh_token)
    # calendar_provider is None for legacy brokers — infer from which token exists
    if cfg and cfg.calendar_provider:
        provider = cfg.calendar_provider
    elif google_connected:
        provider = "google"
    else:
        provider = "none"

    return {
        "provider": provider,
        "google": {
            "connected": google_connected,
            "email": cfg.google_calendar_email if cfg else None,
        },
        "outlook": {
            "connected": outlook_connected,
            "email": cfg.outlook_calendar_email if cfg else None,
        },
    }


# ── Outlook Calendar OAuth routes ─────────────────────────────────────────────

OUTLOOK_SCOPES = [
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "offline_access",
    "User.Read",
]


def _get_msal_app():
    """Build a ConfidentialClientApplication for Microsoft Graph OAuth."""
    import msal
    return msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_CLIENT_ID,
        client_credential=settings.MICROSOFT_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}",
    )


@router.get("/calendar/outlook/auth-url")
async def get_outlook_calendar_auth_url(
    current_user: dict = Depends(Permissions.require_admin),
):
    """
    Generate the Microsoft OAuth URL for the current broker.
    The frontend opens this URL in a popup/new tab.
    """
    if not settings.MICROSOFT_CLIENT_ID or not settings.MICROSOFT_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Outlook OAuth no está configurado (MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET faltantes)",
        )

    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    try:
        from app.core.cache import cache_set_json
        import msal

        msal_app = _get_msal_app()
        flow = msal_app.initiate_auth_code_flow(
            scopes=OUTLOOK_SCOPES,
            redirect_uri=settings.MICROSOFT_OAUTH_REDIRECT_URI,
            state=_make_state(broker_id),
        )
        # Store the flow dict in Redis so the callback can retrieve it
        await cache_set_json(f"outlook_flow:{broker_id}", flow, ttl=_STATE_TTL)
        return {"auth_url": flow["auth_uri"]}
    except ImportError:
        raise HTTPException(status_code=503, detail="Librería msal no instalada")


@router.get("/calendar/outlook/callback")
async def outlook_calendar_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Microsoft OAuth2 callback — public endpoint (no JWT auth).
    Exchanges the authorization code for tokens, stores the encrypted
    refresh_token in broker_prompt_configs, then redirects to the frontend.
    """
    broker_id = _verify_state(state)

    try:
        from app.core.cache import cache_get_json, cache_delete
        import msal, httpx

        msal_app = _get_msal_app()

        # Retrieve the flow dict saved during auth-url generation
        flow = await cache_get_json(f"outlook_flow:{broker_id}")
        if not flow:
            return RedirectResponse(
                f"{settings.FRONTEND_URL}/settings?tab=calendar&status=error&reason=flow_expired"
            )

        result = msal_app.acquire_token_by_auth_code_flow(
            flow, {"code": code, "state": state}
        )

        # Flow is single-use — delete from Redis immediately regardless of outcome
        await cache_delete(f"outlook_flow:{broker_id}")

        if "error" in result:
            logger.error(
                "Outlook OAuth error broker_id=%s: %s — %s",
                broker_id, result.get("error"), result.get("error_description"),
            )
            return RedirectResponse(
                f"{settings.FRONTEND_URL}/settings?tab=calendar&status=error&reason=oauth_error"
            )

        refresh_token = result.get("refresh_token")
        access_token = result.get("access_token")
        if not refresh_token:
            return RedirectResponse(
                f"{settings.FRONTEND_URL}/settings?tab=calendar&status=error&reason=no_refresh_token"
            )

        # Get the user's primary calendar ID from Graph API
        calendar_id = None
        outlook_email = result.get("id_token_claims", {}).get("preferred_username")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://graph.microsoft.com/v1.0/me/calendar",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    calendar_id = resp.json().get("id")
        except Exception as exc:
            logger.warning("Could not fetch Outlook calendar ID for broker_id=%s: %s", broker_id, exc)

        # Persist to DB
        db_result = await db.execute(
            select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
        )
        broker_config = db_result.scalars().first()
        if not broker_config:
            broker_config = BrokerPromptConfig(broker_id=broker_id)
            db.add(broker_config)

        broker_config.outlook_refresh_token = encrypt_value(refresh_token)
        broker_config.outlook_calendar_id = calendar_id
        broker_config.outlook_calendar_email = outlook_email
        broker_config.calendar_provider = "outlook"

        await db.commit()
        logger.info(
            "Outlook Calendar conectado para broker_id=%s email=%s calendar_id=%s",
            broker_id, outlook_email, calendar_id,
        )

    except Exception as exc:
        logger.error(
            "Error en callback OAuth Outlook Calendar broker_id=%s: %s",
            broker_id, exc, exc_info=True,
        )
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/settings?tab=calendar&status=error&reason=callback_failed"
        )

    return RedirectResponse(
        f"{settings.FRONTEND_URL}/settings?tab=calendar&calendar=outlook&status=success"
    )


@router.get("/calendar/outlook/status")
async def get_outlook_calendar_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return Outlook Calendar connection status for the current broker."""
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    result = await db.execute(
        select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
    )
    cfg = result.scalars().first()

    if not cfg or not cfg.outlook_refresh_token:
        return {"connected": False, "email": None, "calendar_id": None}

    return {
        "connected": True,
        "email": cfg.outlook_calendar_email,
        "calendar_id": cfg.outlook_calendar_id,
    }


@router.delete("/calendar/outlook/disconnect")
async def disconnect_outlook_calendar(
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove Outlook Calendar credentials for the current broker."""
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    result = await db.execute(
        select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
    )
    cfg = result.scalars().first()

    if cfg:
        cfg.outlook_refresh_token = None
        cfg.outlook_calendar_id = None
        cfg.outlook_calendar_email = None
        # Revert to google if google token still exists, otherwise none
        cfg.calendar_provider = "google" if cfg.google_refresh_token else "none"
        await db.commit()
        logger.info("Outlook Calendar desconectado para broker_id=%s", broker_id)

    return {"ok": True, "message": "Outlook Calendar desconectado"}


# ── Availability Slots CRUD ────────────────────────────────────────────────────

@router.get("/calendar/availability", response_model=List[dict])
async def list_availability_slots(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all availability slots for the current broker."""
    from app.models.appointment import AvailabilitySlot
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker assigned")
    result = await db.execute(
        select(AvailabilitySlot).where(AvailabilitySlot.broker_id == broker_id).order_by(
            AvailabilitySlot.day_of_week, AvailabilitySlot.start_time
        )
    )
    slots = result.scalars().all()
    return [
        {
            "id": s.id,
            "day_of_week": s.day_of_week,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "slot_duration_minutes": s.slot_duration_minutes,
            "is_active": s.is_active,
            "valid_from": s.valid_from.isoformat(),
            "valid_until": s.valid_until.isoformat() if s.valid_until else None,
            "notes": s.notes,
        }
        for s in slots
    ]


@router.post("/calendar/availability", response_model=dict, status_code=201)
async def create_availability_slot(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new availability slot for the current broker."""
    from app.models.appointment import AvailabilitySlot
    from datetime import time as dt_time, date
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker assigned")

    def parse_time(t: str):
        h, m = t.split(":")
        return dt_time(int(h), int(m))

    slot = AvailabilitySlot(
        broker_id=broker_id,
        agent_id=None,  # Global: applies to all agents
        day_of_week=int(data["day_of_week"]),
        start_time=parse_time(data["start_time"]),
        end_time=parse_time(data["end_time"]),
        slot_duration_minutes=int(data.get("slot_duration_minutes", 60)),
        is_active=True,
        valid_from=date.fromisoformat(data["valid_from"]) if data.get("valid_from") else date.today(),
        valid_until=date.fromisoformat(data["valid_until"]) if data.get("valid_until") else None,
        notes=data.get("notes"),
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return {
        "id": slot.id,
        "day_of_week": slot.day_of_week,
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M"),
        "slot_duration_minutes": slot.slot_duration_minutes,
        "is_active": slot.is_active,
        "valid_from": slot.valid_from.isoformat(),
        "valid_until": slot.valid_until.isoformat() if slot.valid_until else None,
        "notes": slot.notes,
    }


@router.put("/calendar/availability/{slot_id}", response_model=dict)
async def update_availability_slot(
    slot_id: int,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an availability slot (broker-owned only)."""
    from app.models.appointment import AvailabilitySlot
    from datetime import time as dt_time, date
    broker_id = current_user.get("broker_id")
    result = await db.execute(
        select(AvailabilitySlot).where(
            AvailabilitySlot.id == slot_id,
            AvailabilitySlot.broker_id == broker_id,
        )
    )
    slot = result.scalars().first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    def parse_time(t: str):
        h, m = t.split(":")
        return dt_time(int(h), int(m))

    if "day_of_week" in data:
        slot.day_of_week = int(data["day_of_week"])
    if "start_time" in data:
        slot.start_time = parse_time(data["start_time"])
    if "end_time" in data:
        slot.end_time = parse_time(data["end_time"])
    if "slot_duration_minutes" in data:
        slot.slot_duration_minutes = int(data["slot_duration_minutes"])
    if "is_active" in data:
        slot.is_active = bool(data["is_active"])
    if "valid_until" in data:
        slot.valid_until = date.fromisoformat(data["valid_until"]) if data["valid_until"] else None
    if "notes" in data:
        slot.notes = data["notes"]

    await db.commit()
    await db.refresh(slot)
    return {
        "id": slot.id,
        "day_of_week": slot.day_of_week,
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M"),
        "slot_duration_minutes": slot.slot_duration_minutes,
        "is_active": slot.is_active,
        "valid_from": slot.valid_from.isoformat(),
        "valid_until": slot.valid_until.isoformat() if slot.valid_until else None,
        "notes": slot.notes,
    }


@router.delete("/calendar/availability/{slot_id}", response_model=dict)
async def delete_availability_slot(
    slot_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an availability slot (broker-owned only)."""
    from app.models.appointment import AvailabilitySlot
    broker_id = current_user.get("broker_id")
    result = await db.execute(
        select(AvailabilitySlot).where(
            AvailabilitySlot.id == slot_id,
            AvailabilitySlot.broker_id == broker_id,
        )
    )
    slot = result.scalars().first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    await db.delete(slot)
    await db.commit()
    return {"ok": True}


# ── Appointment Blocks CRUD ────────────────────────────────────────────────────

@router.get("/calendar/blocks", response_model=List[dict])
async def list_appointment_blocks(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List appointment blocks for the current broker."""
    from app.models.appointment import AppointmentBlock
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker assigned")
    result = await db.execute(
        select(AppointmentBlock).where(
            AppointmentBlock.broker_id == broker_id
        ).order_by(AppointmentBlock.start_time)
    )
    blocks = result.scalars().all()
    return [
        {
            "id": b.id,
            "start_time": b.start_time.isoformat(),
            "end_time": b.end_time.isoformat(),
            "reason": b.reason,
            "notes": b.notes,
        }
        for b in blocks
    ]


@router.post("/calendar/blocks", response_model=dict, status_code=201)
async def create_appointment_block(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an appointment block for the current broker."""
    from app.models.appointment import AppointmentBlock
    from datetime import datetime
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker assigned")
    block = AppointmentBlock(
        broker_id=broker_id,
        agent_id=None,
        start_time=datetime.fromisoformat(data["start_time"]),
        end_time=datetime.fromisoformat(data["end_time"]),
        reason=data.get("reason", "blocked"),
        notes=data.get("notes"),
    )
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return {
        "id": block.id,
        "start_time": block.start_time.isoformat(),
        "end_time": block.end_time.isoformat(),
        "reason": block.reason,
        "notes": block.notes,
    }


@router.delete("/calendar/blocks/{block_id}", response_model=dict)
async def delete_appointment_block(
    block_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an appointment block (broker-owned only)."""
    from app.models.appointment import AppointmentBlock
    broker_id = current_user.get("broker_id")
    result = await db.execute(
        select(AppointmentBlock).where(
            AppointmentBlock.id == block_id,
            AppointmentBlock.broker_id == broker_id,
        )
    )
    block = result.scalars().first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    await db.delete(block)
    await db.commit()
    return {"ok": True}


@router.post("/voice/assistant", response_model=dict)
async def create_voice_assistant(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the Vapi assistant for this broker from its stored configuration."""
    try:
        broker_id = current_user.get("broker_id")
        if not broker_id:
            raise HTTPException(
                status_code=400,
                detail="Current user has no broker assigned. Assign the user to a broker first.",
            )
        from app.services.voice.providers.vapi import VapiAssistantService
        result = await VapiAssistantService.create_assistant_for_broker(db, broker_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating voice assistant broker_id=%s: %s", current_user.get("broker_id"), str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


