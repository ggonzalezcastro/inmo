"""ReferralAgent — captures referrals only from won leads."""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent
from app.services.agents.prompts.referral_prompt import REFERRAL_SYSTEM_PROMPT
from app.services.agents.types import AgentContext, AgentResponse, AgentType
from app.services.llm.base_provider import LLMToolDefinition
from app.shared.pipeline_stages import PIPELINE_STAGE_WON

logger = logging.getLogger(__name__)


_REFERRAL_TOOLS = [
    LLMToolDefinition(
        name="register_referral",
        description=(
            "Registra un referido cuando el cliente entregó claramente el nombre y teléfono "
            "de la otra persona."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del referido"},
                "phone": {"type": "string", "description": "Teléfono del referido"},
            },
            "required": ["name", "phone"],
        },
    ),
    LLMToolDefinition(
        name="decline_referral",
        description=(
            "Registra que el cliente no desea o no puede entregar un referido. "
            "Úsala ante cualquier negativa explícita."
        ),
        parameters={"type": "object", "properties": {}},
    ),
]


class ReferralAgent(BaseAgent):
    """Won-only specialist that requests and records referral contact details."""

    agent_type = AgentType.REFERRAL
    name = "ReferralAgent"

    def get_system_prompt(self, context: AgentContext) -> str:
        metadata = context.lead_data
        referral_ids = metadata.get("referral_lead_ids") or []
        return REFERRAL_SYSTEM_PROMPT.format(
            agent_name=metadata.get("agent_name") or "Sofía",
            broker_name=metadata.get("broker_name") or "la inmobiliaria",
            lead_name=metadata.get("name") or "cliente",
            referral_status=metadata.get("referral_status") or "pending",
            outreach_status=metadata.get("referral_outreach_status") or "pending",
            referral_count=len(referral_ids) if isinstance(referral_ids, list) else 0,
        )

    async def should_handle(self, context: AgentContext) -> bool:
        return context.pipeline_stage == PIPELINE_STAGE_WON

    async def process(
        self,
        message: str,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResponse:
        if context.pipeline_stage != PIPELINE_STAGE_WON:
            return AgentResponse(
                message="Voy a derivar tu consulta al equipo correspondiente.",
                agent_type=AgentType.REFERRAL,
            )

        from app.services.agents.qualifier import _build_messages
        from app.services.leads.referral_service import ReferralService
        from app.services.llm.facade import LLMServiceFacade

        context_updates: dict = {"current_agent": AgentType.REFERRAL.value}

        async def tool_executor(tool_name: str, args: dict) -> dict:
            if tool_name == "register_referral":
                try:
                    result = await ReferralService.register(
                        db,
                        source_lead_id=context.lead_id,
                        broker_id=context.broker_id,
                        name=args.get("name", ""),
                        phone=args.get("phone", ""),
                    )
                    context_updates["referral_status"] = "collected"
                    return {"status": "ok", **result}
                except ValueError as exc:
                    return {"status": "error", "message": str(exc)}
                except Exception as exc:
                    logger.error("Could not register referral: %s", exc, exc_info=True)
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    return {
                        "status": "error",
                        "message": "No pude guardar el referido en este momento",
                    }
            if tool_name == "decline_referral":
                try:
                    await ReferralService.decline(
                        db,
                        source_lead_id=context.lead_id,
                        broker_id=context.broker_id,
                    )
                    context_updates["referral_status"] = "declined"
                    return {"status": "ok"}
                except Exception as exc:
                    logger.error("Could not decline referral: %s", exc, exc_info=True)
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    return {"status": "error", "message": "No pude guardar la respuesta"}
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

        try:
            response_text, function_calls = (
                await LLMServiceFacade.generate_response_with_function_calling(
                    system_prompt=self.get_system_prompt(context),
                    contents=_build_messages(context.message_history, message),
                    tools=_REFERRAL_TOOLS,
                    tool_executor=tool_executor,
                    tool_mode_override="AUTO",
                    broker_id=context.broker_id,
                    lead_id=context.lead_id,
                    agent_type=self.agent_type.value,
                    db=db,
                )
            )
        except Exception as exc:
            logger.error("ReferralAgent LLM failure: %s", exc, exc_info=True)
            referral_status = context.lead_data.get("referral_status")
            if referral_status == "declined":
                response_text = "Gracias por responder. No volveré a insistir con este tema."
            elif referral_status == "collected":
                response_text = "Muchas gracias nuevamente por el referido que compartiste."
            else:
                response_text = (
                    "Gracias por escribir. Si conoces a alguien que esté buscando una propiedad "
                    "y te acomoda compartirlo, solo necesito su nombre y teléfono. Sin compromiso."
                )
            function_calls = []

        return AgentResponse(
            message=response_text,
            agent_type=AgentType.REFERRAL,
            context_updates=context_updates,
            function_calls=function_calls or [],
        )
