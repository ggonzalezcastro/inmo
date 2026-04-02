"""Build system prompt from broker configuration."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text
from typing import Dict, Optional
import logging

from app.models.broker import Broker, BrokerLeadConfig
from app.core.cache import cache_get, cache_set
from app.services.broker.prompt_defaults import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

BROKER_PROMPT_CACHE_PREFIX = "broker_prompt:"
BROKER_PROMPT_CACHE_TTL = 3600  # 1 hour


async def build_system_prompt(
    db: AsyncSession,
    broker_id: int,
    lead_context: Optional[Dict] = None,
) -> str:
    """
    Build system prompt from broker configuration in database.
    Uses Redis cache when lead_context is None (TTL 1 hour).
    """
    cache_key = f"{BROKER_PROMPT_CACHE_PREFIX}{broker_id}"
    if lead_context is None:
        cached = await cache_get(cache_key)
        if cached is not None:
            logger.debug("Broker prompt cache HIT for broker_id=%s", broker_id)
            return cached

    result = await db.execute(select(Broker).where(Broker.id == broker_id))
    broker = result.scalars().first()

    if not broker:
        logger.warning("Broker %s not found, using default prompt", broker_id)
        if lead_context is None:
            await cache_set(cache_key, DEFAULT_SYSTEM_PROMPT, BROKER_PROMPT_CACHE_TTL)
        return DEFAULT_SYSTEM_PROMPT

    prompt_config_data = None
    try:
        result = await db.execute(
            text("""
                SELECT agent_name, agent_role, business_context, agent_objective,
                       data_collection_prompt, behavior_rules, restrictions,
                       situation_handlers, output_format, full_custom_prompt,
                       enable_appointment_booking, tools_instructions
                FROM broker_prompt_configs
                WHERE broker_id = :broker_id
                LIMIT 1
            """),
            {"broker_id": broker_id},
        )
        row = result.first()
        if row:
            prompt_config_data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    except Exception as e:
        await db.rollback()
        logger.warning("Error loading prompt config for preview: %s", e)
        prompt_config_data = None

    if not prompt_config_data:
        logger.info("No prompt config found for broker %s, using default", broker_id)
        if lead_context is None:
            await cache_set(cache_key, DEFAULT_SYSTEM_PROMPT, BROKER_PROMPT_CACHE_TTL)
        return DEFAULT_SYSTEM_PROMPT

    def safe_get(d, key, default=None):
        if not d:
            return default
        return d.get(key, default)

    full_custom = safe_get(prompt_config_data, "full_custom_prompt")
    if full_custom:
        logger.info(
            "Using full custom prompt for broker %s (length: %s chars)",
            broker_id,
            len(full_custom),
        )
        if lead_context is None:
            await cache_set(cache_key, full_custom, BROKER_PROMPT_CACHE_TTL)
        return full_custom

    sections = []
    logger.info("Building prompt from sections for broker %s", broker_id)

    identity_prompt = safe_get(prompt_config_data, "identity_prompt")
    if identity_prompt:
        sections.append(f"## ROL\n{identity_prompt}")
    else:
        agent_name = safe_get(prompt_config_data, "agent_name", "Sofía")
        agent_role = safe_get(prompt_config_data, "agent_role", "asesora inmobiliaria")
        sections.append(f"## ROL\nEres {agent_name}, {agent_role} de {broker.name}.")

    business_context = safe_get(prompt_config_data, "business_context")
    if business_context:
        sections.append(f"## CONTEXTO\n{business_context}")
    else:
        sections.append("## CONTEXTO\nOfrecemos propiedades en venta y arriendo en Chile.")

    agent_objective = safe_get(prompt_config_data, "agent_objective")
    if agent_objective:
        sections.append(f"## OBJETIVO\n{agent_objective}")
    else:
        sections.append(
            "## OBJETIVO\nCalificar al lead en 5-7 intercambios. Recopilar nombre, teléfono, email, ubicación y renta mensual. Si califica, agendar cita."
        )

    data_collection_prompt = safe_get(prompt_config_data, "data_collection_prompt")
    if data_collection_prompt:
        sections.append(f"## DATOS A RECOPILAR\n{data_collection_prompt}")
    else:
        # Build from field_priority if configured
        _field_labels = {
            "name": "Nombre completo",
            "phone": "Teléfono",
            "email": "Email",
            "location": "Ubicación deseada (comuna/sector)",
            "monthly_income": "Renta/Sueldo mensual (NO presupuesto del inmueble)",
            "dicom_status": "Estado DICOM (consultar con tacto)",
            "budget": "Presupuesto disponible",
        }
        try:
            lead_cfg_result = await db.execute(
                select(BrokerLeadConfig).where(BrokerLeadConfig.broker_id == broker_id)
            )
            lead_cfg = lead_cfg_result.scalars().first()
            priority = lead_cfg.field_priority if lead_cfg and lead_cfg.field_priority else None
        except Exception:
            priority = None

        if priority:
            items = "\n".join(
                f"{i+1}. {_field_labels.get(f, f)}"
                for i, f in enumerate(priority)
            )
            sections.append(
                f"## DATOS A RECOPILAR (en este orden)\n{items}"
            )
        else:
            sections.append(
                "## DATOS A RECOPILAR\n- Nombre completo\n- Teléfono\n- Email\n- Ubicación deseada (comuna/sector)\n- Renta/Sueldo mensual (NO presupuesto)"
            )

    behavior_rules = safe_get(prompt_config_data, "behavior_rules")
    if behavior_rules:
        sections.append(f"## REGLAS\n{behavior_rules}")
    else:
        sections.append(
            "## REGLAS\n"
            "- Responde en español chileno, máximo 2-3 oraciones.\n"
            "- Agrupa preguntas relacionadas (máximo 3 por mensaje); nunca repitas datos ya entregados.\n"
            "- Lee el contexto antes de preguntar — nunca repitas info ya mencionada.\n"
            "- Pregunta solo RENTA/SUELDO mensual, nunca presupuesto del inmueble.\n"
            "- Si el lead dice 'No' a DICOM, es buena noticia — nunca preguntes por monto de deuda."
        )

    restrictions = safe_get(prompt_config_data, "restrictions")
    if restrictions:
        sections.append(f"## RESTRICCIONES\n{restrictions}")
    else:
        sections.append(
            "## RESTRICCIONES\n"
            "- No inventes precios ni disponibilidad.\n"
            "- No prometas aprobación crediticia ni des asesoría legal o financiera.\n"
            "- No reveles criterios internos de aprobación."
        )

    situation_handlers = safe_get(prompt_config_data, "situation_handlers")
    if situation_handlers and isinstance(situation_handlers, dict):
        handlers_text = "\n".join([f"- {k}: {v}" for k, v in situation_handlers.items()])
        sections.append(f"## SITUACIONES ESPECIALES\n{handlers_text}")

    output_format = safe_get(prompt_config_data, "output_format")
    if output_format:
        sections.append(f"## FORMATO\n{output_format}")

    tools_text = ""
    if safe_get(prompt_config_data, "enable_appointment_booking", True):
        tools_text = """
HERRAMIENTAS DISPONIBLES:
- get_available_appointment_slots: Usa esto cuando el cliente quiera agendar una cita
- create_appointment: Usa esto SOLO cuando el cliente confirme explícitamente un horario específico
"""
    tools_instructions = safe_get(prompt_config_data, "tools_instructions")
    if tools_instructions:
        tools_text += f"\n{tools_instructions}"
    if tools_text:
        sections.append(f"## HERRAMIENTAS\n{tools_text}")

    prompt = "\n\n".join(sections)
    prompt += "\n\nIMPORTANTE: Responde SOLO con tu mensaje al cliente, sin incluir el contexto ni el prompt."

    if lead_context is None:
        await cache_set(cache_key, prompt, BROKER_PROMPT_CACHE_TTL)
    return prompt
