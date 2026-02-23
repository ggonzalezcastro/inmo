"""
Broker voice configuration service.
Handles voice (Vapi) config per broker, assistant_id resolution, and building
assistant config from BrokerConfigService prompt + voice settings.
"""
import logging
import re
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.broker import Broker
from app.models.broker_voice_config import BrokerVoiceConfig
from app.services.broker.config_service import BrokerConfigService
from app.core.cache import cache_get, cache_set, cache_get_json, cache_set_json
from app.config import settings

logger = logging.getLogger(__name__)

BROKER_VOICE_CACHE_PREFIX = "broker_voice:"
BROKER_VOICE_CACHE_TTL = 3600

DEFAULT_VOICE_CONFIG = {
    "provider": "azure",
    "voiceId": "es-MX-DaliaNeural",
}
DEFAULT_MODEL_CONFIG = {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
}
DEFAULT_TRANSCRIBER_CONFIG = {
    "provider": "deepgram",
    "model": "nova-2",
    "language": "es",
}
DEFAULT_TIMING_CONFIG = {
    "maxDurationSeconds": 300,
    "waitSeconds": 0.4,
    "voiceSeconds": 0.3,
    "backoffSeconds": 1.2,
}
DEFAULT_END_CALL_CONFIG = {
    "endCallMessage": "Muchas gracias por tu tiempo. ¡Hasta pronto!",
    "endCallPhrases": [
        "tengo que colgar",
        "tengo que irme",
        "no me interesa",
        "adiós",
        "hasta luego",
        "chao",
    ],
}


def _safe_get(d: Optional[Dict], key: str, default: Any = None) -> Any:
    if not d or not isinstance(d, dict):
        return default
    return d.get(key, default)


class BrokerVoiceConfigService:
    """Voice config per broker; uses BrokerConfigService for prompt."""

    @staticmethod
    async def get_voice_config(db: AsyncSession, broker_id: int) -> Dict[str, Any]:
        """
        Get voice config for broker from DB. Returns defaults if not found.
        Uses Redis cache (TTL 1 hour).
        """
        cache_key = f"{BROKER_VOICE_CACHE_PREFIX}{broker_id}"
        cached = await cache_get_json(cache_key)
        if cached is not None:
            logger.debug("Broker voice config cache HIT for broker_id=%s", broker_id)
            return cached

        result = await db.execute(
            select(BrokerVoiceConfig).where(BrokerVoiceConfig.broker_id == broker_id)
        )
        row = result.scalars().first()

        out = {
            "provider": "vapi",
            "phone_number_id": None,
            "assistant_id_default": None,
            "assistant_id_by_type": {},
            "voice_config": DEFAULT_VOICE_CONFIG.copy(),
            "model_config": DEFAULT_MODEL_CONFIG.copy(),
            "transcriber_config": DEFAULT_TRANSCRIBER_CONFIG.copy(),
            "timing_config": DEFAULT_TIMING_CONFIG.copy(),
            "end_call_config": DEFAULT_END_CALL_CONFIG.copy(),
            "first_message_template": None,
            "recording_enabled": True,
        }

        if row:
            if getattr(row, "provider", None):
                out["provider"] = row.provider
            if row.phone_number_id:
                out["phone_number_id"] = row.phone_number_id
            if row.assistant_id_default:
                out["assistant_id_default"] = row.assistant_id_default
            if row.assistant_id_by_type:
                out["assistant_id_by_type"] = dict(row.assistant_id_by_type)
            if row.voice_config:
                out["voice_config"] = {**out["voice_config"], **row.voice_config}
            if row.model_config:
                out["model_config"] = {**out["model_config"], **row.model_config}
            if row.transcriber_config:
                out["transcriber_config"] = {**out["transcriber_config"], **row.transcriber_config}
            if row.timing_config:
                out["timing_config"] = {**out["timing_config"], **row.timing_config}
            if row.end_call_config:
                out["end_call_config"] = {**out["end_call_config"], **row.end_call_config}
            if row.first_message_template:
                out["first_message_template"] = row.first_message_template
            out["recording_enabled"] = row.recording_enabled

        await cache_set_json(cache_key, out, BROKER_VOICE_CACHE_TTL)
        return out

    @staticmethod
    async def get_phone_number_id(db: AsyncSession, broker_id: int) -> str:
        """
        Obtiene phone_number_id del broker.
        Fallback a settings.VAPI_PHONE_NUMBER_ID si no está configurado.
        """
        config = await BrokerVoiceConfigService.get_voice_config(db, broker_id)
        phone_number_id = config.get("phone_number_id")
        if not phone_number_id:
            phone_number_id = getattr(settings, "VAPI_PHONE_NUMBER_ID", None)
        if not phone_number_id:
            raise ValueError(
                f"No phone_number_id configured for broker {broker_id}. "
                "Set BrokerVoiceConfig.phone_number_id or VAPI_PHONE_NUMBER_ID."
            )
        return phone_number_id

    @staticmethod
    async def get_assistant_id(
        db: AsyncSession,
        broker_id: int,
        agent_type: Optional[str] = None,
    ) -> str:
        """
        Resolve assistant_id for broker and optional agent_type.
        """
        config = await BrokerVoiceConfigService.get_voice_config(db, broker_id)
        by_type = config.get("assistant_id_by_type") or {}
        default_from_db = config.get("assistant_id_default")
        agent_type = (agent_type or "").strip().lower() if agent_type else None

        if agent_type and by_type.get(agent_type):
            return by_type[agent_type]
        if default_from_db:
            return default_from_db
        global_id = getattr(settings, "VAPI_ASSISTANT_ID", None) or ""
        if global_id:
            return global_id
        raise ValueError(
            "No assistant_id configured. Set BrokerVoiceConfig.assistant_id_default for this broker "
            "or VAPI_ASSISTANT_ID in settings."
        )

    @staticmethod
    def adapt_prompt_for_voice(prompt: str) -> str:
        """
        Adapt chat prompt for voice: remove tools section, add voice instructions.
        """
        voice_header = """## ESTÁS EN UNA LLAMADA DE VOZ (no chat)
- Habla de forma natural. Máximo 2-3 oraciones por turno.
- Una pregunta a la vez; espera la respuesta del cliente antes de continuar.
- No menciones "mensaje" ni "chat"; es una llamada telefónica.
- Si el cliente quiere agendar una cita, di: "Perfecto, un asesor te contactará para confirmar horario y enviarte el link de la reunión por correo."
- El resto de tu rol, objetivo, datos a recopilar y reglas son los mismos que en el chat.

---

"""

        tools_section = re.compile(
            r"## HERRAMIENTAS DISPONIBLES.*?(?=## FORMATO DE RESPUESTA|\Z)",
            re.DOTALL,
        )
        prompt_no_tools = tools_section.sub(
            "\n## AGENDAMIENTO EN LLAMADA\n"
            "Si el cliente quiere agendar: di que un asesor los contactará para confirmar horario y enviar el link por correo.\n\n",
            prompt,
        )

        prompt_no_tools = prompt_no_tools.replace(
            "1. SIEMPRE responde SOLO con tu mensaje al cliente",
            "1. SIEMPRE di SOLO tu respuesta al cliente (en voz)",
        )
        prompt_no_tools = prompt_no_tools.replace(
            'NO incluyas etiquetas como "Asistente:", "Respuesta:", etc.',
            "No incluyas etiquetas; solo habla.",
        )
        prompt_no_tools = prompt_no_tools.replace(
            "Máximo 2-3 oraciones por mensaje",
            "Máximo 2-3 oraciones por turno",
        )
        prompt_no_tools = prompt_no_tools.replace(
            "Si llamas una herramienta, espera su resultado antes de responder",
            "",
        )

        return voice_header + prompt_no_tools

    @staticmethod
    async def build_assistant_config(
        db: AsyncSession,
        broker_id: int,
        agent_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build full Vapi assistant config for broker.
        """
        system_prompt = await BrokerConfigService.build_system_prompt(db, broker_id, lead_context=None)
        voice_prompt = BrokerVoiceConfigService.adapt_prompt_for_voice(system_prompt)

        config = await BrokerVoiceConfigService.get_voice_config(db, broker_id)

        result = await db.execute(select(Broker).where(Broker.id == broker_id))
        broker = result.scalars().first()
        broker_name = broker.name if broker else "Agente"
        broker_company = broker.name if broker else "Corredora"

        first_message = _safe_get(config, "first_message_template")
        if not first_message:
            first_message = (
                f"Hola, ¿cómo estás? Soy asistente de {broker_company}. "
                "Te llamo porque vimos tu interés en nuestras propiedades. ¿Tienes un momento para conversar?"
            )
        else:
            first_message = first_message.replace("{broker_name}", broker_name).replace(
                "{broker_company}", broker_company
            )

        voice_cfg = config.get("voice_config") or DEFAULT_VOICE_CONFIG
        model_cfg = config.get("model_config") or DEFAULT_MODEL_CONFIG
        transcriber_cfg = config.get("transcriber_config") or DEFAULT_TRANSCRIBER_CONFIG
        timing_cfg = config.get("timing_config") or DEFAULT_TIMING_CONFIG
        end_cfg = config.get("end_call_config") or DEFAULT_END_CALL_CONFIG

        voice_id = voice_cfg.get("voiceId") or voice_cfg.get("voice_id") or "es-MX-DaliaNeural"
        payload = {
            "name": f"Voz - {broker_company}",
            "model": {
                "provider": model_cfg.get("provider", "openai"),
                "model": model_cfg.get("model", "gpt-4o"),
                "temperature": model_cfg.get("temperature", 0.7),
                "messages": [{"role": "system", "content": voice_prompt}],
            },
            "voice": {
                "provider": voice_cfg.get("provider", "azure"),
                "voiceId": voice_id,
            },
            "firstMessage": first_message,
            "firstMessageMode": "assistant-speaks-first",
            "transcriber": {
                "provider": transcriber_cfg.get("provider", "deepgram"),
                "model": transcriber_cfg.get("model", "nova-2"),
                "language": transcriber_cfg.get("language", "es"),
            },
            "startSpeakingPlan": {
                "waitSeconds": timing_cfg.get("waitSeconds", 0.4),
                "transcriptionEndpointingPlan": {
                    "onPunctuationSeconds": 0.1,
                    "onNoPunctuationSeconds": 2.0,
                },
            },
            "stopSpeakingPlan": {
                "numWords": 0,
                "voiceSeconds": timing_cfg.get("voiceSeconds", 0.3),
                "backoffSeconds": timing_cfg.get("backoffSeconds", 1.2),
            },
            "maxDurationSeconds": timing_cfg.get("maxDurationSeconds", 300),
            "recordingEnabled": config.get("recording_enabled", True),
            "endCallMessage": end_cfg.get("endCallMessage", "Muchas gracias por tu tiempo. ¡Hasta pronto!"),
            "endCallPhrases": end_cfg.get("endCallPhrases", DEFAULT_END_CALL_CONFIG["endCallPhrases"]),
        }
        return payload
