"""
Broker configuration routes
Endpoints for managing broker prompt and lead configuration
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import Permissions
from app.schemas.broker import PromptConfigUpdate, LeadConfigUpdate
from app.models.broker import Broker, BrokerPromptConfig, BrokerLeadConfig
from app.services.broker_config_service import BrokerConfigService
from sqlalchemy.future import select
from sqlalchemy import text
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


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
                            "email": getattr(broker, 'email', None),
                            "phone": getattr(broker, 'phone', None)
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
                                   tools_instructions
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
        
        # Get lead config using raw SQL
        lead_config_data = None
        try:
            result = await db.execute(
                text("""
                    SELECT broker_id, field_weights, cold_max_score, warm_max_score, 
                           hot_min_score, qualified_min_score, field_priority, 
                           income_ranges, qualification_criteria, max_acceptable_debt,
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
            logger.error(f"Error loading lead config: {e}", exc_info=True)
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
                "phone": getattr(broker, 'phone', None),
                "email": getattr(broker, 'email', None),
                "logo_url": getattr(broker, 'logo_url', None),
                "website": getattr(broker, 'website', None),
                "address": getattr(broker, 'address', None),
                "is_active": broker.is_active
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
                "tools_instructions": safe_get(prompt_config_data, 'tools_instructions', None)
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
                "max_acceptable_debt": safe_get(lead_config_data, 'max_acceptable_debt', 500000),
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
    for key, value in update_data.items():
        setattr(prompt_config, key, value)
    
    await db.commit()
    await db.refresh(prompt_config)
    
    logger.info(f"Prompt config updated for broker {broker_id} - Changes will be applied immediately in next chat message")
    
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
    
    return {
        "message": "Lead configuration updated successfully",
        "config": {
            "field_weights": lead_config.field_weights,
            "cold_max_score": lead_config.cold_max_score,
            "warm_max_score": lead_config.warm_max_score,
            "hot_min_score": lead_config.hot_min_score
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


