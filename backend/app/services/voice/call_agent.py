"""
Call agent service for AI-powered phone conversations
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, Any, Optional, List
import logging
from app.models.lead import Lead
from app.services.llm import LLMServiceFacade
from app.services.shared import TemplateService
from app.models.template import MessageTemplate, AgentType
from google.genai import types

logger = logging.getLogger(__name__)


class CallAgentService:
    """Service for AI agent that conducts phone calls"""

    @staticmethod
    async def build_call_prompt(
        db: AsyncSession,
        lead: Lead,
        agent_type: str,
        step: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build LLM prompt for phone call conversation

        Args:
            db: Database session
            lead: Lead instance
            agent_type: Type of agent (perfilador, calificador_financiero, etc.)
            step: Optional campaign step context

        Returns:
            Formatted prompt string
        """

        # Get lead context
        lead_data = {
            "id": lead.id,
            "name": lead.name or "Cliente",
            "phone": lead.phone,
            "email": lead.email,
            "lead_score": lead.lead_score,
            "pipeline_stage": lead.pipeline_stage,
            "lead_metadata": lead.lead_metadata or {}
        }

        metadata = lead.lead_metadata or {}

        # Build context summary
        context_parts = []
        context_parts.append(f"CLIENTE: {lead.name or 'Cliente'}")
        if metadata.get("budget"):
            context_parts.append(f"PRESUPUESTO: {metadata.get('budget')}")
        if metadata.get("location"):
            context_parts.append(f"UBICACIÓN: {metadata.get('location')}")
        if lead.pipeline_stage:
            context_parts.append(f"ETAPA: {lead.pipeline_stage}")

        context_summary = "\n".join(context_parts) if context_parts else "Nueva conversación"

        # Agent-specific instructions
        agent_instructions = {
            "perfilador": """Tu objetivo es obtener información del cliente:
- Presupuesto aproximado
- Ubicación deseada (comuna/sector)
- Timeline (cuándo necesita la propiedad)
- Tipo de propiedad (departamento, casa, etc.)
- Número de habitaciones/dormitorios

Pregunta de forma natural y conversacional. No seas muy insistente.""",

            "calificador_financiero": """Tu objetivo es validar la capacidad financiera:
- Ingresos mensuales
- Capacidad de pago
- Pre-aprobación de crédito hipotecario (si aplica)
- Fuente de financiamiento

Sé profesional pero amigable. No presiones demasiado.""",

            "agendador": """Tu objetivo es agendar una cita:
- Proponer horarios disponibles
- Confirmar fecha y hora
- Mencionar que se enviará link de Google Meet

Sé claro y directo con los horarios.""",

            "seguimiento": """Tu objetivo es hacer seguimiento post-reunión:
- Preguntar cómo le pareció la opción mostrada
- Ver si tiene preguntas
- Ofrecer más opciones si es necesario
- Mantener el interés activo

Sé empático y no muy insistente."""
        }

        instructions = agent_instructions.get(agent_type, agent_instructions["perfilador"])

        prompt = f"""Eres un agente inmobiliario haciendo una llamada telefónica.

CONTEXTO DEL CLIENTE:
{context_summary}

INSTRUCCIONES:
{instructions}

IMPORTANTE:
- Habla de forma natural y conversacional
- No hables más de 2-3 oraciones seguidas
- Deja que el cliente responda
- Si el cliente se muestra desinteresado, sé respetuoso y cierra la llamada amablemente
- Extrae información específica: números, fechas, montos

RESPONDE EN ESPAÑOL CHILENO, de forma amigable y profesional."""

        return prompt

    @staticmethod
    async def generate_call_script(
        prompt: str,
        lead_name: Optional[str] = None
    ) -> str:
        """
        Generate initial greeting script for call

        Args:
            prompt: Call prompt with context
            lead_name: Optional lead name

        Returns:
            Initial greeting text to speak
        """

        greeting_prompt = f"""{prompt}

Genera un saludo inicial breve (1-2 oraciones) para comenzar la llamada.
Saluda al cliente por su nombre si está disponible: {lead_name or 'Cliente'}.
Sé profesional pero amigable."""

        try:
            response = await LLMServiceFacade.generate_response(greeting_prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating call script: {str(e)}")
            # Fallback greeting
            name = lead_name or ""
            return f"Hola {name}, te llamo de la inmobiliaria. ¿Tienes un momento para hablar?"

    @staticmethod
    async def process_call_turn(
        transcript_so_far: str,
        customer_response: str,
        agent_type: str,
        lead_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a turn in the conversation (ReAct pattern)

        Args:
            transcript_so_far: Full conversation transcript up to now
            customer_response: What the customer just said
            agent_type: Type of agent
            lead_context: Lead context data

        Returns:
            Dict with:
            - next_message: What bot should say next
            - extracted_data: Dict of extracted information
            - should_continue: bool - whether to continue conversation
            - stage_to_move: Optional stage to move lead to
        """

        # Build prompt for processing turn
        processing_prompt = f"""Eres un agente inmobiliario en una llamada telefónica.

CONTEXTO:
{lead_context.get('name', 'Cliente')}
Etapa: {lead_context.get('pipeline_stage', 'entrada')}
Tipo de agente: {agent_type}

CONVERSACIÓN HASTA AHORA:
{transcript_so_far}

ÚLTIMA RESPUESTA DEL CLIENTE:
{customer_response}

INSTRUCCIONES:
1. Analiza lo que dijo el cliente
2. Extrae información relevante (presupuesto, ubicación, timeline, etc.)
3. Genera tu siguiente respuesta (máximo 2 oraciones)
4. Decide si debes continuar la conversación o cerrar

Retorna JSON con:
- next_message: tu respuesta
- extracted_data: {{"budget": "...", "location": "...", "timeline": "...", etc.}}
- should_continue: true/false
- stage_to_move: etapa a la que mover el lead (o null)"""

        try:
            # Use LLM to process
            response = await LLMServiceFacade.generate_response(processing_prompt)

            # Try to parse JSON response
            import json
            import re

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                # Fallback: extract data manually
                result = {
                    "next_message": response,
                    "extracted_data": {},
                    "should_continue": True,
                    "stage_to_move": None
                }

            return result

        except Exception as e:
            logger.error(f"Error processing call turn: {str(e)}", exc_info=True)
            return {
                "next_message": "Entiendo, gracias por la información. ¿Hay algo más en lo que pueda ayudarte?",
                "extracted_data": {},
                "should_continue": False,
                "stage_to_move": None
            }

    @staticmethod
    async def generate_call_summary(
        full_transcript: str,
        lead_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate AI summary of call after completion

        Args:
            full_transcript: Complete call transcript
            lead_context: Lead context

        Returns:
            Dict with:
            - summary: Text summary
            - interest_level: 1-10
            - budget: Extracted budget
            - timeline: Extracted timeline
            - next_steps: Recommended next steps
            - score_delta: Score change from call
            - stage_to_move: Stage to advance to
        """

        summary_prompt = f"""Analiza esta conversación telefónica y genera un resumen.

TRANSCRIPCIÓN:
{full_transcript}

CONTEXTO:
{lead_context.get('name', 'Cliente')}
Etapa actual: {lead_context.get('pipeline_stage', 'entrada')}

Genera un resumen JSON con:
- summary: resumen ejecutivo de la llamada (2-3 oraciones)
- interest_level: nivel de interés 1-10
- budget: presupuesto mencionado (o null)
- timeline: timeline mencionado (o null)
- next_steps: próximos pasos recomendados
- score_delta: cambio de score (-10 a +20)
- stage_to_move: etapa a la que avanzar (o null)"""

        try:
            response = await LLMServiceFacade.generate_response(summary_prompt)

            # Parse JSON
            import json
            import re

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                summary = json.loads(json_match.group())
            else:
                # Fallback
                summary = {
                    "summary": "Llamada completada",
                    "interest_level": 5,
                    "budget": None,
                    "timeline": None,
                    "next_steps": "Seguimiento estándar",
                    "score_delta": 0,
                    "stage_to_move": None
                }

            return summary

        except Exception as e:
            logger.error(f"Error generating call summary: {str(e)}", exc_info=True)
            return {
                "summary": "Error generando resumen de llamada",
                "interest_level": 5,
                "budget": None,
                "timeline": None,
                "next_steps": "Revisar llamada manualmente",
                "score_delta": 0,
                "stage_to_move": None
            }
