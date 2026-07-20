"""
Voice system-prompt builder — produces prompts tuned for telephone conversations.

Designed for the AgentSupervisor / CRMLLMProcessor path: this prompt is fed
to the multi-agent system when the conversation comes from a voice channel.
It enforces SHORT replies, no markdown/lists/emojis, natural confirmations,
and one-question-at-a-time pacing — all of which collapse if the LLM is
allowed to use its normal "assistant" tone.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


_VOICE_INSTRUCTIONS = """\
INSTRUCCIONES DE CONVERSACIÓN (críticas para sonar natural por teléfono):
- Habla en frases CORTAS — máximo 2 oraciones por turno.
- Usa confirmaciones naturales: "claro", "entiendo", "por supuesto", "ya veo".
- NO repitas información que el cliente acaba de mencionar.
- Haz UNA pregunta a la vez, nunca varias seguidas.
- Si el cliente no entiende, reformula DIFERENTE — no más largo.
- Tolera pausas. No interrumpas si el cliente está pensando.
- Llama a la herramienta `capture_info` apenas tengas un dato clave
  (presupuesto, ubicación deseada, plazo, DICOM, etc.) en lugar de
  guardarlo solo al final.

FORMATO: solo texto hablado. Prohibido: viñetas, listas, markdown, emojis,
URLs, código, tablas. Si necesitas enumerar algo, dilo con palabras
("primero ... luego ... por último ...").
"""


def build_voice_system_prompt(
    lead: Any,
    broker_config: Optional[Any] = None,
    call_purpose: Optional[str] = None,
) -> str:
    """
    Compose the voice system prompt.

    Parameters
    ----------
    lead : Lead ORM row (or any object with name/pipeline_stage/lead_metadata).
    broker_config : optional BrokerPromptConfig — supplies persona/broker name.
    call_purpose : free-text override for the call objective (from
        CallAgentService.build_call_prompt). When None, uses a generic
        qualification objective.
    """
    broker_name = getattr(broker_config, "broker_name", None) or "la inmobiliaria"
    persona = getattr(broker_config, "persona_name", None) or "Sofía"

    name = getattr(lead, "name", None) or "el cliente"
    stage = getattr(lead, "pipeline_stage", None) or "entrada"
    metadata = getattr(lead, "lead_metadata", None) or {}

    presupuesto = metadata.get("presupuesto") or metadata.get("budget") or "sin datos"
    interes = metadata.get("nivel_interes") or metadata.get("interest_level") or "sin medir"

    purpose = call_purpose or (
        "Calificar al lead: confirmar interés, presupuesto y disponibilidad para "
        "agendar una visita."
    )

    return (
        f"Eres {persona}, asistente de {broker_name}. "
        f"Estás en una LLAMADA TELEFÓNICA real con un cliente.\n\n"
        f"CONTEXTO DEL CLIENTE:\n"
        f"- Nombre: {name}\n"
        f"- Etapa del pipeline: {stage}\n"
        f"- Presupuesto conocido: {presupuesto}\n"
        f"- Nivel de interés: {interes}\n\n"
        f"PROPÓSITO DE LA LLAMADA:\n{purpose}\n\n"
        f"{_VOICE_INSTRUCTIONS}"
    )
