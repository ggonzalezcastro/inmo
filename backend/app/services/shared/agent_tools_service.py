"""
Service for defining agent tools (functions) that the LLM can call
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from google.genai import types
import logging
from app.services.appointments import AppointmentService
from app.models.appointment import AppointmentType

logger = logging.getLogger(__name__)


class AgentToolsService:
    """Service for agent tools (functions the LLM can call)"""
    
    @staticmethod
    def get_function_declarations() -> List[types.FunctionDeclaration]:
        """Get function declarations for Gemini function calling"""
        
        # Function 1: Get available appointment slots
        get_slots_function = types.FunctionDeclaration(
            name="get_available_appointment_slots",
            description="Obtiene los horarios disponibles para agendar citas. Úsalo cuando el cliente quiera agendar una reunión o visita.",
            parameters={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Fecha de inicio en formato ISO (YYYY-MM-DD). Si no se especifica, usa la fecha actual.",
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "Número de días hacia adelante para buscar horarios disponibles. Default: 14 días.",
                        "default": 14
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duración de la cita en minutos. Default: 60 minutos.",
                        "default": 60
                    }
                },
                "required": []
            }
        )
        
        # Function 2: Create appointment
        create_appointment_function = types.FunctionDeclaration(
            name="create_appointment",
            description="Crea una cita para el cliente. SOLO úsalo cuando el cliente confirme explícitamente un horario específico.",
            parameters={
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "Fecha y hora de inicio de la cita en formato ISO 8601 con timezone (ej: '2025-02-01T15:00:00-03:00'). DEBE incluir timezone.",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duración de la cita en minutos. Default: 60.",
                        "default": 60
                    },
                    "appointment_type": {
                        "type": "string",
                        "enum": ["virtual_meeting", "property_visit", "phone_call", "office_meeting"],
                        "description": "Tipo de cita. 'virtual_meeting' para reunión virtual, 'property_visit' para visita a propiedad.",
                        "default": "virtual_meeting"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Notas adicionales sobre la cita (opcional)."
                    }
                },
                "required": ["start_time"]
            }
        )
        
        return [get_slots_function, create_appointment_function]
    
    @staticmethod
    async def execute_tool(
        db: AsyncSession,
        tool_name: str,
        arguments: Dict[str, Any],
        lead_id: int,
        agent_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool function and return the result

        Args:
            db: Database session
            tool_name: Name of the tool/function to execute
            arguments: Arguments for the function
            lead_id: ID of the lead making the request
            agent_id: ID of the agent (optional, defaults to first available agent)

        Returns:
            Dict with 'result' (the tool result) and 'success' (bool)
        """
        
        logger.info(f"[AGENT_TOOLS] Executing tool: {tool_name} with args: {arguments}")
        
        try:
            if tool_name == "get_available_appointment_slots":
                return await AgentToolsService._get_available_slots(
                    db, arguments, agent_id
                )
            
            elif tool_name == "create_appointment":
                return await AgentToolsService._create_appointment(
                    db, arguments, lead_id, agent_id
                )
            
            else:
                logger.warning(f"[AGENT_TOOLS] Unknown tool: {tool_name}")
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
        
        except Exception as e:
            logger.error(f"[AGENT_TOOLS] Error executing tool {tool_name}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def _get_available_slots(
        db: AsyncSession,
        arguments: Dict[str, Any],
        agent_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get available appointment slots"""
        
        # Parse start_date
        start_date_str = arguments.get("start_date")
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str.split('T')[0]).date()
            except:
                start_date = date.today()
        else:
            start_date = date.today()
        
        # Parse days_ahead
        days_ahead = arguments.get("days_ahead", 14)
        end_date = start_date + timedelta(days=days_ahead)
        
        # Parse duration
        duration_minutes = arguments.get("duration_minutes", 60)
        
        # Get available slots
        slots = await AppointmentService.get_available_slots(
            db=db,
            start_date=start_date,
            end_date=end_date,
            agent_id=agent_id,
            appointment_type=AppointmentType.VIRTUAL_MEETING,  # Default to virtual
            duration_minutes=duration_minutes
        )
        
        # Format slots for LLM
        formatted_slots = AppointmentService.format_slots_for_llm(slots, max_slots=20)
        
        return {
            "success": True,
            "result": {
                "slots": slots[:20],  # Return first 20 slots
                "formatted": formatted_slots,
                "count": len(slots),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
        }
    
    @staticmethod
    async def _create_appointment(
        db: AsyncSession,
        arguments: Dict[str, Any],
        lead_id: int,
        agent_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create an appointment"""
        
        # Verify lead has email (required for sending Meet link)
        from app.models.lead import Lead
        from sqlalchemy.future import select
        
        lead_result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = lead_result.scalars().first()
        
        if not lead:
            return {
                "success": False,
                "error": "Lead no encontrado"
            }
        
        if not lead.email or lead.email.strip() == '':
            return {
                "success": False,
                "error": "El lead no tiene email registrado. Por favor, solicita el email antes de crear la cita para poder enviar el link de Google Meet."
            }
        
        # Get default agent if not specified
        if not agent_id:
            from app.models.user import User
            from sqlalchemy.future import select
            
            agent_result = await db.execute(
                select(User).where(User.is_active == True).limit(1)
            )
            agent = agent_result.scalars().first()
            if agent:
                agent_id = agent.id
            else:
                return {
                    "success": False,
                    "error": "No hay agentes disponibles. No se puede crear la cita."
                }
        
        # Parse start_time
        start_time_str = arguments.get("start_time")
        try:
            # Try parsing ISO format with timezone
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            # Ensure timezone-aware (Chile timezone)
            if start_time.tzinfo is None:
                import pytz
                chile_tz = pytz.timezone('America/Santiago')
                start_time = chile_tz.localize(start_time)
        except Exception as e:
            logger.error(f"[AGENT_TOOLS] Error parsing start_time: {str(e)}")
            return {
                "success": False,
                "error": f"Formato de fecha inválido: {start_time_str}. Usa formato ISO 8601 (ej: '2025-02-01T15:00:00-03:00')"
            }
        
        # Parse duration
        duration_minutes = arguments.get("duration_minutes", 60)
        
        # Parse appointment type
        apt_type_str = arguments.get("appointment_type", "virtual_meeting")
        try:
            apt_type = AppointmentType(apt_type_str)
        except:
            apt_type = AppointmentType.VIRTUAL_MEETING
        
        # Parse notes
        notes = arguments.get("notes")
        
        # Create appointment
        try:
            appointment = await AppointmentService.create_appointment(
                db=db,
                lead_id=lead_id,
                start_time=start_time,
                duration_minutes=duration_minutes,
                appointment_type=apt_type,
                agent_id=agent_id,
                location="Reunión virtual" if apt_type == AppointmentType.VIRTUAL_MEETING else None,
                notes=notes
            )
            
            logger.info(f"[AGENT_TOOLS] Appointment created: {appointment.id}")
            
            return {
                "success": True,
                "result": {
                    "appointment_id": appointment.id,
                    "start_time": appointment.start_time.isoformat(),
                    "end_time": appointment.end_time.isoformat(),
                    "meet_url": appointment.meet_url,
                    "status": appointment.status.value,
                    "message": f"Cita creada exitosamente para {appointment.start_time.strftime('%d/%m/%Y a las %H:%M')}"
                }
            }
        
        except ValueError as e:
            # Likely availability issue
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"[AGENT_TOOLS] Error creating appointment: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Error al crear la cita: {str(e)}"
            }
