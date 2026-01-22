"""
Template routes for managing message templates
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.template_service import TemplateService
from app.models.template import TemplateChannel, AgentType
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    template_data: TemplateCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new message template"""
    
    try:
        broker_id = current_user.get("id")
        
        template = await TemplateService.create_template(
            db=db,
            name=template_data.name,
            channel=TemplateChannel(template_data.channel),
            content=template_data.content,
            broker_id=broker_id,
            agent_type=AgentType(template_data.agent_type) if template_data.agent_type else None,
            variables=template_data.variables
        )
        
        return TemplateResponse.model_validate(template)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    channel: Optional[str] = Query(None),
    agent_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List templates with filters"""
    
    try:
        broker_id = current_user.get("id")
        
        channel_enum = None
        if channel:
            try:
                channel_enum = TemplateChannel(channel)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid channel: {channel}")
        
        agent_type_enum = None
        if agent_type:
            try:
                agent_type_enum = AgentType(agent_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid agent_type: {agent_type}")
        
        templates = await TemplateService.list_templates(
            db=db,
            broker_id=broker_id,
            channel=channel_enum,
            agent_type=agent_type_enum
        )
        
        return TemplateListResponse(
            data=[TemplateResponse.model_validate(t) for t in templates]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get template details"""
    
    try:
        broker_id = current_user.get("id")
        
        template = await TemplateService.get_template(
            db=db,
            template_id=template_id,
            broker_id=broker_id
        )
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return TemplateResponse.model_validate(template)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_update: TemplateUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a template"""
    
    try:
        broker_id = current_user.get("id")
        
        template = await TemplateService.update_template(
            db=db,
            template_id=template_id,
            name=template_update.name,
            content=template_update.content,
            variables=template_update.variables,
            broker_id=broker_id
        )
        
        return TemplateResponse.model_validate(template)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a template"""
    
    try:
        broker_id = current_user.get("id")
        
        await TemplateService.delete_template(
            db=db,
            template_id=template_id,
            broker_id=broker_id
        )
        
        return None
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent-type/{agent_type}", response_model=TemplateListResponse)
async def get_templates_by_agent_type(
    agent_type: str,
    channel: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get templates filtered by agent type"""
    
    try:
        broker_id = current_user.get("id")
        
        try:
            agent_type_enum = AgentType(agent_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid agent_type: {agent_type}")
        
        channel_enum = None
        if channel:
            try:
                channel_enum = TemplateChannel(channel)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid channel: {channel}")
        
        templates = await TemplateService.get_templates_by_type(
            db=db,
            agent_type=agent_type_enum,
            channel=channel_enum,
            broker_id=broker_id
        )
        
        return TemplateListResponse(
            data=[TemplateResponse.model_validate(t) for t in templates]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting templates by agent type: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



