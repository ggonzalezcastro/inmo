"""
Tool definitions for function calling during voice calls.

These are the same tools as chat but with voice-optimized descriptions
that prompt the LLM to produce natural spoken confirmations before/after
tool execution (e.g., "Déjame revisar..." filler while searching).
"""
from app.services.llm.base_provider import LLMToolDefinition

VOICE_SEARCH_PROPERTIES_TOOL = LLMToolDefinition(
    name="search_properties",
    description=(
        "Busca propiedades disponibles según los criterios del lead. "
        "ANTES de llamar esta función, di en voz alta: "
        "'Déjame revisar las opciones disponibles para ti.' "
        "Después de obtener resultados, preséntelos conversacionalmente."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Descripción de lo que busca el lead en lenguaje natural",
            },
            "commune": {
                "type": "string",
                "description": "Comuna o zona de interés",
            },
            "max_uf": {
                "type": "number",
                "description": "Presupuesto máximo en UF",
            },
            "bedrooms": {
                "type": "integer",
                "description": "Número de dormitorios requeridos",
            },
        },
        "required": ["query"],
    },
)

VOICE_CREATE_APPOINTMENT_TOOL = LLMToolDefinition(
    name="create_appointment",
    description=(
        "Agenda una cita o videollamada con el ejecutivo de ventas. "
        "ANTES de llamar esta función, confirma verbalmente la fecha y hora con el lead. "
        "Después de crear la cita, di: 'Perfecto, tu cita ha quedado agendada. "
        "Recibirás una invitación por correo.'"
    ),
    parameters={
        "type": "object",
        "properties": {
            "lead_id": {
                "type": "integer",
                "description": "ID del lead",
            },
            "scheduled_at": {
                "type": "string",
                "description": "Fecha y hora en formato ISO 8601 (e.g. 2026-05-06T10:00:00-03:00)",
            },
            "notes": {
                "type": "string",
                "description": "Notas adicionales para el ejecutivo",
            },
        },
        "required": ["lead_id", "scheduled_at"],
    },
)

VOICE_TOOLS = [VOICE_SEARCH_PROPERTIES_TOOL, VOICE_CREATE_APPOINTMENT_TOOL]
