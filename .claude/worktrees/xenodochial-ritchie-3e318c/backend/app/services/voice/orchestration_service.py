"""
VapiOrchestrationService — two-layer voice config + Web SDK JWT for CRM-initiated calls.

Phase 1: Transcriptor mode.
Phase 2: AI Agent mode (ensure_vapi_assistant, merged config, function-call tools).
"""
import logging
from typing import Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.agent_voice_profile import AgentVoiceProfile
from app.models.agent_voice_template import AgentVoiceTemplate
from app.models.lead import Lead
from app.models.user import User
from app.models.voice_call import CallPurpose, CallStatus, VoiceCall

logger = logging.getLogger(__name__)

_TRANSCRIPTOR_CONFIG = {
    "transcriber": {
        "provider": "deepgram",
        "model": "nova-2",
        "language": "es",
    },
    # firstMessage: brief greeting so VAPI initialises audio but stays silent.
    # Prevents LLM prompt leakage — no model block means no AI responses.
    "firstMessage": ".",
    # No model block → pure transcription, no LLM response
}

# ── Per-purpose structured extraction tool definitions ────────────────────────
# These are injected into the VAPI assistant config when call_mode == "ai_agent".
# VAPI fires a tool-calls webhook when the assistant decides to call one; our
# handle_tool_call handler then persists the parameters to VoiceCall.call_output.
# Format: VAPI uses model.functions[] with flat {name, description, parameters}
# (not the OpenAI {type:"function", function:{...}} wrapper).

_PURPOSE_TOOLS: dict[str, list[dict]] = {
    CallPurpose.CALIFICACION_INICIAL: [
        {
            "name": "capture_lead_info",
            "description": (
                "Registra la información recopilada del lead durante la calificación inicial. "
                "Llama esta función cuando tengas los datos clave del prospecto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "presupuesto": {"type": "string", "description": "Presupuesto máximo del lead"},
                    "zona": {"type": "string", "description": "Zona o sector de interés"},
                    "tipo_propiedad": {"type": "string", "description": "Casa, departamento, comercial, etc."},
                    "disponibilidad_visita": {"type": "string", "description": "Días/horarios disponibles para visita"},
                    "nivel_interes": {"type": "string", "description": "alto, medio, bajo"},
                },
                "required": [],
            },
        }
    ],
    CallPurpose.CALIFICACION_FINANCIERA: [
        {
            "name": "capture_financial_info",
            "description": (
                "Registra los datos financieros recopilados. "
                "Llama cuando tengas información sobre ingresos y capacidad de pago."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ingresos": {"type": "string", "description": "Renta mensual aproximada"},
                    "capacidad_pago": {"type": "string", "description": "Cuota mensual que puede pagar"},
                    "pre_aprobacion": {"type": "boolean", "description": "Tiene pre-aprobación bancaria"},
                    "nivel_interes": {"type": "string", "description": "alto, medio, bajo"},
                },
                "required": [],
            },
        }
    ],
    CallPurpose.CONFIRMACION_REUNION: [
        {
            "name": "capture_confirmation",
            "description": "Registra si el lead confirmó, rechazó o propuso nueva fecha para la reunión.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmo_asistencia": {"type": "boolean", "description": "true si confirma asistencia"},
                    "nueva_fecha_propuesta": {"type": "string", "description": "Fecha/hora alternativa si no confirma"},
                    "motivo_rechazo": {"type": "string", "description": "Razón por la que no asistirá"},
                },
                "required": ["confirmo_asistencia"],
            },
        }
    ],
    CallPurpose.CONFIRMACION_VISITA: [
        {
            "name": "capture_confirmation",
            "description": "Registra si el lead confirmó, rechazó o propuso nueva fecha para la visita.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmo_asistencia": {"type": "boolean", "description": "true si confirma asistencia"},
                    "nueva_fecha_propuesta": {"type": "string", "description": "Fecha/hora alternativa si no confirma"},
                    "motivo_rechazo": {"type": "string", "description": "Razón por la que no asistirá"},
                },
                "required": ["confirmo_asistencia"],
            },
        }
    ],
    CallPurpose.SEGUIMIENTO_POST_VISITA: [
        {
            "name": "capture_post_visit_feedback",
            "description": "Registra el feedback del lead después de la visita a la propiedad.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nivel_interes_actualizado": {"type": "string", "description": "alto, medio, bajo"},
                    "objeciones": {"type": "string", "description": "Objeciones o dudas del lead"},
                    "proximos_pasos": {"type": "string", "description": "Qué sigue según el lead"},
                },
                "required": [],
            },
        }
    ],
    CallPurpose.REACTIVACION: [
        {
            "name": "capture_reactivation_outcome",
            "description": "Registra el resultado del intento de reactivación del lead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "respondio_llamada": {"type": "boolean", "description": "true si el lead contestó"},
                    "sigue_interesado": {"type": "boolean", "description": "true si sigue interesado"},
                    "nuevo_contexto": {"type": "string", "description": "Cambios en la situación del lead"},
                },
                "required": ["respondio_llamada"],
            },
        }
    ],
}


class VapiOrchestrationService:

    # ── Config helpers ────────────────────────────────────────────────────────

    @staticmethod
    def merge_config(
        template: AgentVoiceTemplate,
        profile: Optional[AgentVoiceProfile],
    ) -> dict:
        """
        Build the BASE VAPI assistant config from template + profile overrides.

        This config is persisted as the VAPI assistant (server-side only).
        It intentionally does NOT include call-purpose tools — those are
        injected per-call via assistantOverrides so the base assistant
        stays stable and race-condition-free.

        Profile may override: selected_voice_id, selected_tone (validated
        against template allowed lists), assistant_name, opening_message.
        Template fields (business_prompt, transcriber, limits) are immutable.
        """
        transcriber = dict(template.transcriber_config or {}) or {
            "provider": "deepgram",
            "model": "nova-2",
            "language": template.language or "es",
        }

        config: dict[str, Any] = {
            "transcriber": transcriber,
            "maxDurationSeconds": template.max_duration_seconds,
            "silenceTimeoutSeconds": template.max_silence_seconds,
        }

        model_config: dict[str, Any] = {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.7,
        }
        if template.business_prompt:
            model_config["messages"] = [
                {"role": "system", "content": template.business_prompt}
            ]

        config["model"] = model_config

        # Voice
        voice_id = None
        voice_provider = "azure"  # default provider
        if profile and profile.selected_voice_id:
            allowed = template.available_voice_ids or []
            # Each entry may be a plain voiceId string (legacy) or a
            # {voiceId, provider} dict (preferred, allows non-Azure voices).
            for entry in allowed:
                if isinstance(entry, dict):
                    if entry.get("voiceId") == profile.selected_voice_id:
                        voice_id = profile.selected_voice_id
                        voice_provider = entry.get("provider", "azure")
                        break
                elif entry == profile.selected_voice_id:
                    voice_id = profile.selected_voice_id
                    break
            if not voice_id:
                logger.warning(
                    "selected_voice_id %s not in template %s allowed list, skipping",
                    profile.selected_voice_id,
                    template.id,
                )
        if voice_id:
            config["voice"] = {"provider": voice_provider, "voiceId": voice_id}

        # Name / opening
        if profile:
            if profile.assistant_name:
                config["name"] = profile.assistant_name
            if profile.opening_message:
                config["firstMessage"] = profile.opening_message

        return config

    @staticmethod
    def build_call_overrides(call_purpose: str) -> Optional[dict]:
        """
        Build assistantOverrides for a specific call_purpose.

        These are passed to vapi.start(assistantId, overrides) on the frontend
        so that each call gets the correct structured-extraction tools without
        mutating the base assistant. Safe for concurrent calls by the same agent.

        Returns None when call_purpose has no registered tools.
        """
        try:
            purpose_enum = CallPurpose(call_purpose)
        except ValueError:
            return None
        tools = _PURPOSE_TOOLS.get(purpose_enum, [])
        if not tools:
            return None
        # VAPI uses model.functions[] (flat format), not model.tools[]
        return {"model": {"functions": tools}}

    @staticmethod
    def get_vapi_public_key() -> str:
        """
        Return the VAPI Public Key for the @vapi-ai/web SDK.

        This is the browser-safe key from VAPI dashboard → API Keys → Public Key.
        It only allows initiating calls — it does NOT grant API access.

        Raises ValueError when VAPI_PUBLIC_KEY is not configured.
        """
        key = getattr(settings, "VAPI_PUBLIC_KEY", "") or ""
        if not key:
            raise ValueError(
                "VAPI_PUBLIC_KEY not configured — set it from VAPI dashboard → API Keys → Public Key"
            )
        return key

    @staticmethod
    async def ensure_vapi_assistant(
        db: AsyncSession,
        profile: AgentVoiceProfile,
        base_config: dict,
    ) -> str:
        """
        Create or sync the per-agent BASE VAPI assistant (no call-purpose tools).

        - If profile.vapi_assistant_id exists → PATCH with latest base_config
          (keeps voice/prompt/transcriber in sync when template changes).
        - Otherwise → POST to create, persist the ID on the profile.

        Returns the VAPI assistant_id string.
        """
        from app.services.voice.providers.vapi.assistant_service import VapiAssistantService

        # Inject serverUrl so VAPI can send tool-calls webhooks to our backend.
        webhook_url = getattr(settings, "WEBHOOK_BASE_URL", "") or ""
        if webhook_url:
            base_config.setdefault("serverUrl", f"{webhook_url.rstrip('/')}/webhooks/voice")

        # Row-level lock prevents two concurrent calls for the same agent from
        # both hitting the "no assistant yet" branch and creating duplicate assistants.
        from sqlalchemy import select as sa_select
        locked_result = await db.execute(
            sa_select(AgentVoiceProfile)
            .where(AgentVoiceProfile.id == profile.id)
            .with_for_update()
        )
        locked_profile = locked_result.scalars().first()
        if locked_profile is None:
            raise ValueError(f"AgentVoiceProfile {profile.id} not found")
        # Re-check after acquiring lock — another request may have just created it
        profile = locked_profile

        if profile.vapi_assistant_id:
            logger.info(
                "Syncing VAPI assistant %s for user %s",
                profile.vapi_assistant_id,
                profile.user_id,
            )
            await VapiAssistantService.update_assistant(
                profile.vapi_assistant_id, base_config
            )
            return profile.vapi_assistant_id

        logger.info("Creating new VAPI assistant for user %s", profile.user_id)
        api_key = getattr(settings, "VAPI_API_KEY", None) or ""
        if not api_key:
            raise ValueError("VAPI_API_KEY not configured — cannot create VAPI assistant")

        import aiohttp
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.vapi.ai/assistant",
                json=base_config,
                headers=headers,
            ) as response:
                if response.status not in (200, 201):
                    error_text = await response.text()
                    raise ValueError(f"Failed to create VAPI assistant: {error_text}")
                assistant = await response.json()

        assistant_id: str = assistant["id"]
        profile.vapi_assistant_id = assistant_id
        await db.commit()
        logger.info("Created VAPI assistant %s for user %s", assistant_id, profile.user_id)
        return assistant_id

    # ── Autonomous call (VAPI calls the lead directly) ────────────────────────

    @staticmethod
    async def start_autonomous_call(
        vapi_assistant_id: str,
        phone_number: str,
        call_purpose: str,
        voice_call_id: int,
    ) -> str:
        """
        POST to VAPI /call so VAPI dials the lead's phone directly.

        VAPI → lead's phone → AI handles the call → sends webhooks back to us.
        Returns the VAPI external_call_id to link back to our VoiceCall row.
        """
        import aiohttp

        api_key = getattr(settings, "VAPI_API_KEY", "") or ""
        phone_number_id = getattr(settings, "VAPI_PHONE_NUMBER_ID", "") or ""
        if not api_key:
            raise ValueError("VAPI_API_KEY not configured")
        if not phone_number_id:
            raise ValueError("VAPI_PHONE_NUMBER_ID not configured — import a number in VAPI dashboard")

        overrides = VapiOrchestrationService.build_call_overrides(call_purpose)

        payload: dict = {
            "assistantId": vapi_assistant_id,
            "phoneNumberId": phone_number_id,
            "customer": {"number": phone_number},
            "metadata": {
                "call_id": voice_call_id,
                "call_purpose": call_purpose,
            },
        }
        if overrides:
            payload["assistantOverrides"] = overrides

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.vapi.ai/call",
                json=payload,
                headers=headers,
            ) as response:
                if response.status not in (200, 201):
                    error_text = await response.text()
                    raise ValueError(f"VAPI outbound call failed: {error_text}")
                call_data = await response.json()

        external_id: str = call_data.get("id", "")
        logger.info(
            "VAPI autonomous call %s initiated for VoiceCall %s → %s",
            external_id,
            voice_call_id,
            phone_number,
        )
        return external_id

    # ── Main entry point ──────────────────────────────────────────────────────

    @staticmethod
    async def start_call(
        db: AsyncSession,
        agent_user: User,
        lead_id: int,
        call_mode: str,
        call_purpose: str,
    ) -> dict:
        """
        Orchestrate a CRM-initiated voice call.

        Modes:
          - "ai_agent" / "transcriptor": returns vapi_public_key + assistantId for
            the frontend web SDK (agente habla desde browser).
          - "autonomous": backend calls VAPI REST API → VAPI dials the lead's phone
            directly. Returns external_call_id; no public key needed.

        Returns a dict the route can return directly as JSON.
        """
        # 1. Validate call_purpose
        try:
            CallPurpose(call_purpose)
        except ValueError:
            valid = [p.value for p in CallPurpose]
            raise ValueError(
                f"Invalid call_purpose '{call_purpose}'. Valid values: {valid}"
            )

        # 2. Load lead
        lead_result = await db.execute(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.broker_id == agent_user.broker_id,
            )
        )
        lead = lead_result.scalars().first()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found for this broker")
        if not lead.phone:
            raise ValueError(f"Lead {lead_id} has no phone number")

        # 3. Load profile + template
        profile_result = await db.execute(
            select(AgentVoiceProfile).where(
                AgentVoiceProfile.user_id == agent_user.id
            )
        )
        profile: Optional[AgentVoiceProfile] = profile_result.scalars().first()

        template: Optional[AgentVoiceTemplate] = None
        if profile:
            template_result = await db.execute(
                select(AgentVoiceTemplate).where(
                    AgentVoiceTemplate.id == profile.template_id,
                    AgentVoiceTemplate.is_active.is_(True),
                )
            )
            template = template_result.scalars().first()

        # 4. Validate mode requirements
        effective_call_mode = call_mode
        if effective_call_mode in ("ai_agent", "autonomous") and (profile is None or template is None):
            raise ValueError(
                f"'{effective_call_mode}' mode requires an AgentVoiceProfile with an active template assigned"
            )

        # 5. Snapshots for audit
        template_snapshot = None
        profile_snapshot = None
        if template:
            template_snapshot = {
                "id": template.id,
                "name": template.name,
                "business_prompt": template.business_prompt,
                "language": template.language,
                "max_duration_seconds": template.max_duration_seconds,
                "recording_policy": template.recording_policy,
            }
        if profile:
            profile_snapshot = {
                "id": profile.id,
                "selected_voice_id": profile.selected_voice_id,
                "selected_tone": profile.selected_tone,
                "assistant_name": profile.assistant_name,
                "preferred_call_mode": profile.preferred_call_mode,
            }

        # 6. Create VoiceCall row
        voice_call = VoiceCall(
            lead_id=lead_id,
            phone_number=lead.phone,
            status=CallStatus.INITIATED,
            broker_id=agent_user.id,
            agent_user_id=agent_user.id,
            call_mode=effective_call_mode,
            call_purpose=call_purpose,
            template_snapshot=template_snapshot,
            profile_snapshot=profile_snapshot,
        )
        db.add(voice_call)
        await db.commit()
        await db.refresh(voice_call)

        # 7. Resolve assistantId (needed by all modes).
        #    Create/sync the BASE assistant in VAPI (prompt lives server-side).
        if profile and template:
            base_config = VapiOrchestrationService.merge_config(template, profile)
            if effective_call_mode == "transcriptor":
                base_config.pop("model", None)
                base_config.setdefault("transcriber", _TRANSCRIPTOR_CONFIG["transcriber"])

            vapi_assistant_id = await VapiOrchestrationService.ensure_vapi_assistant(
                db, profile, base_config
            )

            # ── Autonomous: VAPI calls the lead directly ──────────────────────
            if effective_call_mode == "autonomous":
                external_call_id = await VapiOrchestrationService.start_autonomous_call(
                    vapi_assistant_id=vapi_assistant_id,
                    phone_number=lead.phone,
                    call_purpose=call_purpose,
                    voice_call_id=voice_call.id,
                )
                # Persist external_call_id so webhook handler can look up the row
                voice_call.external_call_id = external_call_id
                await db.commit()
                return {
                    "voice_call_id": voice_call.id,
                    "call_mode": effective_call_mode,
                    "external_call_id": external_call_id,
                    "vapi_public_key": None,
                    "vapi_assistant_id": vapi_assistant_id,
                    "assistant_overrides": None,
                    "vapi_config": None,
                }

            # ── Web SDK: agent speaks from browser ───────────────────────────
            vapi_public_key = VapiOrchestrationService.get_vapi_public_key()
            assistant_overrides: Optional[dict] = None
            if effective_call_mode == "ai_agent":
                assistant_overrides = VapiOrchestrationService.build_call_overrides(call_purpose)

            return {
                "vapi_public_key": vapi_public_key,
                "voice_call_id": voice_call.id,
                "call_mode": effective_call_mode,
                "vapi_assistant_id": vapi_assistant_id,
                "assistant_overrides": assistant_overrides,
                "vapi_config": None,
                "external_call_id": None,
            }

        # Bare transcriptor fallback (no profile configured — web SDK only)
        logger.info(
            "No AgentVoiceTemplate for user %s — using bare transcriptor inline config",
            agent_user.id,
        )
        vapi_public_key = VapiOrchestrationService.get_vapi_public_key()
        return {
            "vapi_public_key": vapi_public_key,
            "voice_call_id": voice_call.id,
            "call_mode": effective_call_mode,
            "vapi_assistant_id": None,
            "assistant_overrides": None,
            "vapi_config": _TRANSCRIPTOR_CONFIG,
            "external_call_id": None,
        }
