"""
MCP Server for Inmo Agent Tools.

Standalone MCP server that exposes appointment scheduling tools via the
Model Context Protocol. Any MCP-compatible LLM client can discover and
call these tools, regardless of the underlying model (Gemini, Claude, OpenAI, etc.).

Run standalone:
    python -m app.mcp.server

Or use via MCPClientAdapter from within the FastAPI backend.
"""
import asyncio
import logging
import sys
from datetime import datetime, date, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP Server instance
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "inmo-tools",
    instructions=(
        "Herramientas para gestión inmobiliaria. "
        "Incluye agendamiento de citas y consulta de disponibilidad."
    ),
)


# ---------------------------------------------------------------------------
# Database helpers (async session management for tool execution)
# ---------------------------------------------------------------------------
async def _get_db_session():
    """Get a fresh async database session for tool execution."""
    from app.core.database import AsyncSessionLocal
    return AsyncSessionLocal()


# ---------------------------------------------------------------------------
# Tool: get_available_appointment_slots
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_available_appointment_slots(
    start_date: Optional[str] = None,
    days_ahead: int = 14,
    duration_minutes: int = 60,
) -> dict:
    """
    Obtiene los horarios disponibles para agendar citas.
    Úsalo cuando el cliente quiera agendar una reunión o visita.

    Args:
        start_date: Fecha de inicio en formato ISO (YYYY-MM-DD). Si no se
                    especifica, usa la fecha actual.
        days_ahead: Número de días hacia adelante para buscar. Default 14.
        duration_minutes: Duración de la cita en minutos. Default 60.

    Returns:
        Dict con slots disponibles, conteo, y rango de fechas.
    """
    from app.services.appointments import AppointmentService
    from app.models.appointment import AppointmentType

    # Parse start_date
    if start_date:
        try:
            parsed_start = datetime.fromisoformat(start_date.split("T")[0]).date()
        except Exception:
            parsed_start = date.today()
    else:
        parsed_start = date.today()

    end_date = parsed_start + timedelta(days=days_ahead)

    db = await _get_db_session()
    try:
        slots = await AppointmentService.get_available_slots(
            db=db,
            start_date=parsed_start,
            end_date=end_date,
            agent_id=None,
            appointment_type=AppointmentType.VIRTUAL_MEETING,
            duration_minutes=duration_minutes,
        )

        formatted = AppointmentService.format_slots_for_llm(slots, max_slots=20)

        return {
            "success": True,
            "result": {
                "slots": slots[:20],
                "formatted": formatted,
                "count": len(slots),
                "date_range": {
                    "start": parsed_start.isoformat(),
                    "end": end_date.isoformat(),
                },
            },
        }
    except Exception as e:
        logger.error(f"[MCP] Error getting slots: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Tool: create_appointment
# ---------------------------------------------------------------------------
@mcp.tool()
async def create_appointment(
    start_time: str,
    lead_id: int,
    duration_minutes: int = 60,
    appointment_type: str = "virtual_meeting",
    notes: Optional[str] = None,
) -> dict:
    """
    Crea una cita para el cliente.
    SOLO úsalo cuando el cliente confirme explícitamente un horario específico.

    Args:
        start_time: Fecha y hora de inicio en formato ISO 8601 con timezone
                    (ej: '2025-02-01T15:00:00-03:00'). DEBE incluir timezone.
        lead_id: ID del lead para quien se crea la cita.
        duration_minutes: Duración en minutos. Default 60.
        appointment_type: Tipo de cita. Opciones: virtual_meeting, property_visit,
                          phone_call, office_meeting. Default virtual_meeting.
        notes: Notas adicionales sobre la cita (opcional).

    Returns:
        Dict con datos de la cita creada o error.
    """
    from app.services.appointments import AppointmentService
    from app.models.appointment import AppointmentType as AptType
    from app.models.lead import Lead
    from app.models.user import User
    from sqlalchemy.future import select

    db = await _get_db_session()
    try:
        # Verify lead exists and has email
        lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = lead_result.scalars().first()

        if not lead:
            return {"success": False, "error": "Lead no encontrado"}

        if not lead.email or lead.email.strip() == "":
            return {
                "success": False,
                "error": (
                    "El lead no tiene email registrado. "
                    "Por favor, solicita el email antes de crear la cita "
                    "para poder enviar el link de Google Meet."
                ),
            }

        # Get default agent
        agent_result = await db.execute(
            select(User).where(User.is_active == True).limit(1)
        )
        agent = agent_result.scalars().first()
        agent_id = agent.id if agent else None

        if not agent_id:
            return {
                "success": False,
                "error": "No hay agentes disponibles. No se puede crear la cita.",
            }

        # Parse start_time
        try:
            parsed_start = datetime.fromisoformat(
                start_time.replace("Z", "+00:00")
            )
            if parsed_start.tzinfo is None:
                import pytz
                chile_tz = pytz.timezone("America/Santiago")
                parsed_start = chile_tz.localize(parsed_start)
        except Exception as e:
            return {
                "success": False,
                "error": (
                    f"Formato de fecha inválido: {start_time}. "
                    "Usa formato ISO 8601 (ej: '2025-02-01T15:00:00-03:00')"
                ),
            }

        # Parse appointment type
        try:
            apt_type = AptType(appointment_type)
        except Exception:
            apt_type = AptType.VIRTUAL_MEETING

        # Create appointment
        appointment = await AppointmentService.create_appointment(
            db=db,
            lead_id=lead_id,
            start_time=parsed_start,
            duration_minutes=duration_minutes,
            appointment_type=apt_type,
            agent_id=agent_id,
            location=(
                "Reunión virtual"
                if apt_type == AptType.VIRTUAL_MEETING
                else None
            ),
            notes=notes,
        )

        await db.commit()

        logger.info(f"[MCP] Appointment created: {appointment.id}")

        return {
            "success": True,
            "result": {
                "appointment_id": appointment.id,
                "start_time": appointment.start_time.isoformat(),
                "end_time": appointment.end_time.isoformat(),
                "meet_url": appointment.meet_url,
                "status": appointment.status.value,
                "message": (
                    f"Cita creada exitosamente para "
                    f"{appointment.start_time.strftime('%d/%m/%Y a las %H:%M')}"
                ),
            },
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"[MCP] Error creating appointment: {e}", exc_info=True)
        await db.rollback()
        return {"success": False, "error": f"Error al crear la cita: {e}"}
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Entry point for standalone execution
# ---------------------------------------------------------------------------
def run_server():
    """
    Start the MCP server.

    Transport is selected via the MCP_TRANSPORT environment variable:
      - "http"  → SSE/HTTP server on MCP_SERVER_PORT (default 8001).
                  Run as an independent microservice in docker-compose.
      - "stdio" → Standard I/O (default, backward-compatible, for development).

    Examples:
        # HTTP mode (production / docker-compose)
        MCP_TRANSPORT=http python -m app.mcp.server

        # stdio mode (development / legacy)
        python -m app.mcp.server
    """
    import os
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport == "http":
        port = int(os.getenv("MCP_SERVER_PORT", "8001"))
        host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
        logger.info(f"[MCP Server] Starting HTTP/SSE server on {host}:{port}")
        # host/port are FastMCP Settings — set them before running SSE transport
        mcp.settings.host = host
        mcp.settings.port = port
        import asyncio
        asyncio.run(mcp.run_sse_async())
    else:
        logger.info("[MCP Server] Starting stdio server")
        mcp.run()


if __name__ == "__main__":
    run_server()
