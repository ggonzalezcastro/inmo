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
from app.models.appointment import Appointment, AppointmentStatus
from app.services.appointments.time_resolver import (
    DEFAULT_DURATION_MINUTES,
    SchedulingTimeError,
    resolve_schedule_time,
)

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
                        "description": "Duración de la cita en minutos. Default: 30 minutos.",
                        "default": DEFAULT_DURATION_MINUTES
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
                    "date_reference": {
                        "type": "string",
                        "enum": ["today", "tomorrow", "absolute"],
                        "description": "Referencia de fecha expresada por el usuario. El backend la resuelve.",
                    },
                    "local_date": {
                        "type": "string",
                        "description": "Fecha YYYY-MM-DD, solo cuando date_reference sea absolute.",
                    },
                    "local_time": {
                        "type": "string",
                        "description": "Hora local HH:MM indicada por el usuario.",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duración de la cita en minutos. Default: 30.",
                        "default": DEFAULT_DURATION_MINUTES
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
                "required": ["date_reference", "local_time"]
            }
        )
        reschedule_function = types.FunctionDeclaration(
            name="reschedule_appointment",
            description="Reagenda la última cita activa del cliente, solo tras confirmar el nuevo horario.",
            parameters={
                "type": "object",
                "properties": {
                    "date_reference": {"type": "string", "enum": ["today", "tomorrow", "absolute"]},
                    "local_date": {"type": "string", "description": "Fecha YYYY-MM-DD para una fecha absoluta."},
                    "local_time": {"type": "string", "description": "Hora local HH:MM."},
                    "duration_minutes": {"type": "integer", "default": DEFAULT_DURATION_MINUTES},
                },
                "required": ["date_reference", "local_time"],
            },
        )
        return [get_slots_function, create_appointment_function, reschedule_function]
    
    @staticmethod
    async def execute_tool(
        db: AsyncSession,
        tool_name: str,
        arguments: Dict[str, Any],
        lead_id: int,
        agent_id: Optional[int] = None,
        timezone_name: str = "America/Santiago",
        conversation_text: str = "",
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
                    db, arguments, agent_id, lead_id=lead_id
                )
            
            elif tool_name == "create_appointment":
                return await AgentToolsService._create_appointment(
                    db, arguments, lead_id, agent_id, timezone_name, conversation_text
                )
            elif tool_name == "reschedule_appointment":
                return await AgentToolsService._reschedule_appointment(
                    db, arguments, lead_id, timezone_name, conversation_text
                )
            
            else:
                logger.warning(f"[AGENT_TOOLS] Unknown tool: {tool_name}")
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
        
        except SchedulingTimeError as e:
            await db.rollback()
            return {"success": False, "error_code": e.code, "error": str(e)}
        except Exception as e:
            await db.rollback()
            logger.error(f"[AGENT_TOOLS] Error executing tool {tool_name}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def _get_available_slots(
        db: AsyncSession,
        arguments: Dict[str, Any],
        agent_id: Optional[int] = None,
        lead_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get available appointment slots.

        If the lead already has an assigned agent, show that agent's slots.
        Otherwise show the union of all active agents' slots.
        """
        # Resolve agent_id from lead assignment if not provided
        if not agent_id and lead_id:
            try:
                from app.models.lead import Lead
                from sqlalchemy.future import select as sa_select
                lr = await db.execute(sa_select(Lead).where(Lead.id == lead_id))
                lead = lr.scalars().first()
                if lead and lead.assigned_to:
                    agent_id = lead.assigned_to
            except Exception:
                pass
        
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
        duration_minutes = arguments.get("duration_minutes", DEFAULT_DURATION_MINUTES)
        
        if not agent_id:
            return {"success": False, "error_code": "agent_calendar_unavailable", "error": "No hay un ejecutivo asignado para consultar su calendario"}

        # Get internal CRM availability first.
        slots = await AppointmentService.get_available_slots(
            db=db,
            start_date=start_date,
            end_date=end_date,
            agent_id=agent_id,
            appointment_type=AppointmentType.VIRTUAL_MEETING,  # Default to virtual
            duration_minutes=duration_minutes
        )

        if slots:
            range_start = datetime.fromisoformat(slots[0]["start_time"])
            range_end = datetime.fromisoformat(slots[-1]["end_time"])
            busy = await AppointmentService.external_busy_intervals(db, lead_id, agent_id, range_start, range_end)
            if busy is None:
                return {"success": False, "error_code": "external_calendar_unavailable", "error": "No pude verificar el calendario externo; no ofreceré horarios"}
            slots = [slot for slot in slots if not any(
                datetime.fromisoformat(slot["start_time"]) < busy_end
                and datetime.fromisoformat(slot["end_time"]) > busy_start
                for busy_start, busy_end in busy
            )]
        formatted_slots = AppointmentService.format_slots_for_llm(slots, max_slots=20) if slots else "No hay horarios verificables disponibles."

        return {
            "success": True,
            "result": {
                "slots": slots[:20],
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
        agent_id: Optional[int] = None,
        timezone_name: str = "America/Santiago",
        conversation_text: str = "",
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
        
        # Get default agent if not specified — use round-robin
        if not agent_id:
            from app.models.user import User
            from app.services.appointments.round_robin import RoundRobinService
            from sqlalchemy.future import select

            # Determine broker_id from lead
            broker_id = lead.broker_id if lead else None

            if broker_id:
                agent = await RoundRobinService.assign_next_agent(db, broker_id=broker_id)
            else:
                # Last-resort fallback: first active agent
                agent_result = await db.execute(
                    select(User).where(User.is_active == True).limit(1)
                )
                agent = agent_result.scalars().first()

            if agent:
                agent_id = agent.id
                # Auto-assign lead to this agent
                if lead and lead.assigned_to != agent_id:
                    lead.assigned_to = agent_id
                    await db.commit()
                    logger.info(
                        "[AGENT_TOOLS] Lead %s auto-assigned to agent %s via round-robin",
                        lead_id, agent_id,
                    )
            else:
                return {
                    "success": False,
                    "error": "No hay agentes disponibles. No se puede crear la cita."
                }
        else:
            # agent_id provided externally — still load the User object for calendar lookup
            from app.models.user import User
            from sqlalchemy.future import select
            agent_result = await db.execute(select(User).where(User.id == agent_id))
            agent = agent_result.scalars().first()
        
        resolved = resolve_schedule_time(
            arguments, timezone_name=timezone_name, conversation_text=conversation_text
        )
        start_time = resolved.start_time
        
        # Parse duration
        duration_minutes = arguments.get("duration_minutes", DEFAULT_DURATION_MINUTES)
        
        # Parse appointment type
        apt_type_str = arguments.get("appointment_type", "virtual_meeting")
        try:
            apt_type = AppointmentType(apt_type_str)
        except:
            apt_type = AppointmentType.VIRTUAL_MEETING
        
        # Parse notes
        notes = arguments.get("notes")
        
        # Create appointment (pass agent object for per-agent calendar lookup)
        try:
            appointment = await AppointmentService.create_appointment(
                db=db,
                lead_id=lead_id,
                start_time=start_time,
                duration_minutes=duration_minutes,
                appointment_type=apt_type,
                agent_id=agent_id,
                agent=agent,
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
                    "agent_name": agent.name if agent else None,
                    "message": f"Cita creada exitosamente para {appointment.start_time.strftime('%d/%m/%Y a las %H:%M')}"
                }
            }
        
        except SchedulingTimeError as e:
            await db.rollback()
            return {"success": False, "error_code": e.code, "error": str(e)}
        except ValueError as e:
            await db.rollback()
            # Likely availability issue
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            await db.rollback()
            logger.error(f"[AGENT_TOOLS] Error creating appointment: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Error al crear la cita: {str(e)}"
            }

    @staticmethod
    async def _reschedule_appointment(db, arguments, lead_id, timezone_name, conversation_text):
        from sqlalchemy.future import select
        result = await db.execute(
            select(Appointment).where(
                Appointment.lead_id == lead_id,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
            ).order_by(Appointment.created_at.desc()).limit(1)
        )
        appointment = result.scalars().first()
        if not appointment:
            return {"success": False, "error_code": "appointment_not_found", "error": "No hay una cita activa para reagendar"}
        resolved = resolve_schedule_time(arguments, timezone_name=timezone_name, conversation_text=conversation_text)
        updated = await AppointmentService.update_appointment(db, appointment.id, {
            "start_time": resolved.start_time,
            "duration_minutes": arguments.get("duration_minutes", appointment.duration_minutes or DEFAULT_DURATION_MINUTES),
        })
        return {"success": True, "result": {
            "appointment_id": updated.id,
            "start_time": updated.start_time.isoformat(),
            "end_time": updated.end_time.isoformat(),
            "message": f"Cita reagendada para {updated.start_time.strftime('%d/%m/%Y a las %H:%M')}",
        }}
