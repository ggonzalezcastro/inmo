"""
Template service for managing message templates
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc
from typing import List, Optional, Dict, Any
import re
import logging
from app.models.template import (
    MessageTemplate,
    TemplateChannel,
    AgentType
)
from app.models.lead import Lead

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for managing message templates and variable substitution"""
    
    # Common variable patterns
    VARIABLE_PATTERN = re.compile(r'\{\{(\w+)\}\}')
    
    @staticmethod
    async def create_template(
        db: AsyncSession,
        name: str,
        channel: TemplateChannel,
        content: str,
        broker_id: int,
        agent_type: Optional[AgentType] = None,
        variables: Optional[List[str]] = None
    ) -> MessageTemplate:
        """Create a new message template"""
        
        # Auto-extract variables from content if not provided
        if variables is None:
            variables = TemplateService._extract_variables(content)
        
        template = MessageTemplate(
            name=name,
            channel=channel,
            content=content,
            agent_type=agent_type,
            variables=variables or [],
            broker_id=broker_id
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        logger.info(f"Template created: {template.id} - {template.name}")
        return template
    
    @staticmethod
    def _extract_variables(content: str) -> List[str]:
        """Extract variable names from template content"""
        variables = TemplateService.VARIABLE_PATTERN.findall(content)
        return list(set(variables))  # Remove duplicates
    
    @staticmethod
    async def render_template(
        template: MessageTemplate,
        lead_data: Dict[str, Any],
        fallback_values: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Render template by replacing variables with lead data
        
        Args:
            template: MessageTemplate instance
            lead_data: Dictionary with lead information
            fallback_values: Optional fallback values for missing variables
        
        Returns:
            Rendered template string
        """
        
        fallback_values = fallback_values or {}
        
        # Build variable map from lead_data
        variable_map = {
            "name": lead_data.get("name", fallback_values.get("name", "Cliente")),
            "phone": lead_data.get("phone", fallback_values.get("phone", "")),
            "email": lead_data.get("email", fallback_values.get("email", "")),
            "budget": lead_data.get("budget") or lead_data.get("lead_metadata", {}).get("budget", fallback_values.get("budget", "")),
            "location": lead_data.get("location") or lead_data.get("lead_metadata", {}).get("location", fallback_values.get("location", "")),
            "timeline": lead_data.get("timeline") or lead_data.get("lead_metadata", {}).get("timeline", fallback_values.get("timeline", "")),
            "score": str(lead_data.get("lead_score", fallback_values.get("score", "0"))),
            "stage": lead_data.get("pipeline_stage", fallback_values.get("stage", "")),
        }
        
        # Add any custom variables from lead_metadata
        if "lead_metadata" in lead_data and isinstance(lead_data["lead_metadata"], dict):
            for key, value in lead_data["lead_metadata"].items():
                if key not in variable_map:
                    variable_map[key] = str(value) if value is not None else ""
        
        # Replace variables in template
        rendered = template.content
        for variable in template.variables:
            value = variable_map.get(variable, fallback_values.get(variable, ""))
            rendered = rendered.replace(f"{{{{{variable}}}}}", str(value))
        
        # Replace any remaining variables that weren't in the variables list
        for match in TemplateService.VARIABLE_PATTERN.findall(rendered):
            value = variable_map.get(match, fallback_values.get(match, ""))
            rendered = rendered.replace(f"{{{{{match}}}}}", str(value))
        
        return rendered
    
    @staticmethod
    async def get_templates_by_type(
        db: AsyncSession,
        agent_type: AgentType,
        channel: Optional[TemplateChannel] = None,
        broker_id: Optional[int] = None
    ) -> List[MessageTemplate]:
        """Get templates filtered by agent type"""
        
        query = select(MessageTemplate).where(MessageTemplate.agent_type == agent_type)
        
        if channel:
            query = query.where(MessageTemplate.channel == channel)
        
        if broker_id:
            query = query.where(MessageTemplate.broker_id == broker_id)
        
        query = query.order_by(desc(MessageTemplate.created_at))
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def list_templates(
        db: AsyncSession,
        broker_id: int,
        channel: Optional[TemplateChannel] = None,
        agent_type: Optional[AgentType] = None
    ) -> List[MessageTemplate]:
        """List templates with filters"""
        
        query = select(MessageTemplate).where(MessageTemplate.broker_id == broker_id)
        
        if channel:
            query = query.where(MessageTemplate.channel == channel)
        
        if agent_type:
            query = query.where(MessageTemplate.agent_type == agent_type)
        
        query = query.order_by(desc(MessageTemplate.created_at))
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_template(
        db: AsyncSession,
        template_id: int,
        broker_id: Optional[int] = None
    ) -> Optional[MessageTemplate]:
        """Get a template by ID"""
        
        query = select(MessageTemplate).where(MessageTemplate.id == template_id)
        
        if broker_id:
            query = query.where(MessageTemplate.broker_id == broker_id)
        
        result = await db.execute(query)
        return result.scalars().first()
    
    @staticmethod
    async def update_template(
        db: AsyncSession,
        template_id: int,
        name: Optional[str] = None,
        content: Optional[str] = None,
        variables: Optional[List[str]] = None,
        broker_id: Optional[int] = None
    ) -> MessageTemplate:
        """Update a template"""
        
        query = select(MessageTemplate).where(MessageTemplate.id == template_id)
        
        if broker_id:
            query = query.where(MessageTemplate.broker_id == broker_id)
        
        result = await db.execute(query)
        template = result.scalars().first()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        if name:
            template.name = name
        
        if content:
            template.content = content
            # Re-extract variables if content changed
            if variables is None:
                template.variables = TemplateService._extract_variables(content)
        
        if variables is not None:
            template.variables = variables
        
        await db.commit()
        await db.refresh(template)
        
        logger.info(f"Template {template_id} updated")
        return template
    
    @staticmethod
    async def delete_template(
        db: AsyncSession,
        template_id: int,
        broker_id: Optional[int] = None
    ) -> bool:
        """Delete a template"""
        
        query = select(MessageTemplate).where(MessageTemplate.id == template_id)
        
        if broker_id:
            query = query.where(MessageTemplate.broker_id == broker_id)
        
        result = await db.execute(query)
        template = result.scalars().first()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        await db.delete(template)
        await db.commit()
        
        logger.info(f"Template {template_id} deleted")
        return True

