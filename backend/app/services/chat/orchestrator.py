"""
Chat orchestrator: coordinates lead resolution, analysis, score update,
metadata update, pipeline advancement, and LLM response generation.
Single entry point for chat flow to improve testability and maintainability.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, func

from app.models.lead import Lead, LeadStatus
from app.services.leads import LeadService, LeadContextService
from app.services.llm import LLMServiceFacade
from app.services.shared import ActivityService
from app.services.chat.service import ChatService
from app.services.chat.base_provider import ChatMessageData
from app.services.shared import AgentToolsService
from app.services.pipeline import PipelineService
from app.schemas.lead import LeadCreate
from app.shared.input_sanitizer import sanitize_chat_input, InputSanitizationError
from app.services.chat.state_machine import ConversationStateMachine
from app.services.llm.semantic_cache import SemanticCache
from app.core.encryption import encrypt_metadata_fields
import logging

try:
    from app.mcp.client import MCPClientAdapter
    _MCP_AVAILABLE = True
except Exception:
    MCPClientAdapter = None
    _MCP_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    response: str
    lead_id: int
    lead_score: float
    lead_status: str
    conversation_state: str = "greeting"


class ChatOrchestratorService:
    """Orchestrates the full chat message flow."""

    @staticmethod
    async def process_chat_message(
        db: AsyncSession,
        current_user: dict,
        message: str,
        lead_id: Optional[int] = None,
        provider_name: str = "webchat",
    ) -> ChatResult:
        """
        Process one chat message: get/create lead, analyze, update score/metadata,
        advance pipeline, generate AI response. Returns ChatResult.
        """
        broker_id = (current_user or {}).get("broker_id")

        # 0. Sanitize input — must happen before anything touches the message
        try:
            sanitized = sanitize_chat_input(message, source=provider_name)
            message = sanitized.text
        except InputSanitizationError as exc:
            logger.warning(
                "[Orchestrator] Input rejected by sanitizer",
                extra={"reason": exc.reason_code, "provider": provider_name},
            )
            raise ValueError(str(exc)) from exc

        # 1. Get or create lead
        if lead_id:
            lead = await LeadService.get_lead(db, lead_id)
            if not lead:
                raise ValueError("Lead not found")
        else:
            lead_data = LeadCreate(
                phone="web_chat_pending",
                name=None,
                tags=["test", "chat", "web_chat"],
            )
            lead = await LeadService.create_lead(db, lead_data, broker_id=broker_id)
        current_lead_id = lead.id

        # 2. Log inbound message
        if broker_id:
            await ChatService.log_message(
                db,
                lead_id=lead.id,
                broker_id=broker_id,
                provider_name=provider_name,
                message_data=ChatMessageData(
                    channel_user_id="0",
                    channel_username=None,
                    channel_message_id=None,
                    message_text=message,
                    direction="in",
                ),
                ai_used=False,
            )
        else:
            await ActivityService.log_telegram_message(
                db, lead_id=lead.id, telegram_user_id=0, message_text=message, direction="in"
            )
        await db.refresh(lead)

        # 2c. Broadcast new_message + typing events via WebSocket (TASK-027)
        if broker_id:
            try:
                from app.core.websocket_manager import ws_manager
                await ws_manager.broadcast(broker_id, "new_message", {
                    "lead_id": lead.id,
                    "lead_name": lead.name,
                    "message": message[:200],
                    "provider": provider_name,
                })
                await ws_manager.broadcast(broker_id, "typing", {
                    "lead_id": lead.id,
                    "is_typing": True,
                })
            except Exception as _ws_exc:
                logger.debug("[WS] Broadcast error: %s", _ws_exc)

        # 2b. Initialise state machine from persisted lead metadata
        conv_machine = ConversationStateMachine.from_lead_metadata(lead.lead_metadata)

        # 3. Get context and analyze
        context = await LeadContextService.get_lead_context(db, lead.id)
        analysis = await LLMServiceFacade.analyze_lead_qualification(
            message, context, broker_id=broker_id, lead_id=lead.id
        )

        # 3b. Advance state machine based on LLM analysis output
        try:
            conv_machine.advance_from_llm_output(analysis)
        except Exception as sm_exc:
            logger.warning("State machine advance failed: %s", sm_exc)

        # 4. Atomic score update
        score_delta = analysis.get("score_delta", 0)
        await db.execute(
            update(Lead)
            .where(Lead.id == lead.id)
            .values(
                lead_score=func.least(100, func.greatest(0, Lead.lead_score + score_delta))
            )
        )
        await db.flush()
        await db.refresh(lead)
        new_score = lead.lead_score
        old_score = new_score - score_delta

        # 5. Update lead fields and metadata from analysis
        if analysis.get("name"):
            lead.name = analysis["name"]
        if analysis.get("phone"):
            lead.phone = analysis["phone"]
        if analysis.get("email"):
            lead.email = analysis["email"]

        current_metadata = dict(lead.lead_metadata or {})
        for field in [
            "location", "timeline", "salary", "job_type", "property_type",
            "bedrooms", "dicom_status", "morosidad_amount"
        ]:
            if analysis.get(field):
                current_metadata[field] = analysis[field]
                if field == "salary":
                    current_metadata["monthly_income"] = analysis[field]

        message_lower = message.lower().strip()
        interest_confirmations = [
            "si", "sí", "yes", "claro", "por supuesto", "obvio", "porfavor",
            "por favor", "dale", "ok", "okay", "va", "si porfavor", "sí por favor", "yes please"
        ]
        is_positive_confirmation = (
            message_lower in interest_confirmations
            or any(c in message_lower for c in ["si ", "sí ", "yes ", "claro ", "ok "])
            or (message_lower.startswith("si") and len(message_lower) <= 10)
            or (message_lower.startswith("sí") and len(message_lower) <= 10)
        )
        message_history = context.get("message_history", [])
        bot_asked_about_interest = False
        if isinstance(message_history, list):
            for msg in reversed(message_history):
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "assistant" and content:
                    content_lower = content.lower()
                    if any(
                        kw in content_lower
                        for kw in ["interes", "calificas", "sigues buscando", "te gustaría"]
                    ):
                        bot_asked_about_interest = True
                        break
        elif isinstance(message_history, str):
            prev = message_history.lower()
            bot_asked_about_interest = (
                "interes" in prev or "calificas" in prev
                or "sigues buscando" in prev or "te gustaría" in prev
            )
        if is_positive_confirmation and bot_asked_about_interest:
            current_metadata["interest_confirmed"] = True
            current_metadata["interest_confirmed_at"] = datetime.now().isoformat()

        if analysis.get("salary") and not analysis.get("budget"):
            current_metadata["monthly_income"] = analysis["salary"]
            current_metadata["salary"] = analysis["salary"]
        if analysis.get("budget") and (
            "presupuesto" in message_lower or "precio" in message_lower or "valor máximo" in message_lower
        ):
            current_metadata["budget"] = analysis["budget"]
        if analysis.get("key_points"):
            current_points = current_metadata.get("key_points", []) or []
            for point in analysis["key_points"]:
                if point not in current_points:
                    current_points.append(point)
            current_metadata["key_points"] = current_points
        current_metadata["last_analysis"] = analysis
        current_metadata["source"] = "web_chat"
        # Persist conversation state
        current_metadata = conv_machine.to_metadata(current_metadata)
        # Encrypt sensitive financial fields before writing to DB
        lead.lead_metadata = encrypt_metadata_fields(current_metadata)

        has_all_info = (
            lead.name and lead.name not in ("User", "Test User")
            and lead.phone and not str(lead.phone).startswith(("web_chat_", "whatsapp_", "+569999"))
            and lead.email and str(lead.email).strip() != ""
            and lead.lead_metadata.get("location")
            and lead.lead_metadata.get("budget")
        )
        if has_all_info:
            lead.status = LeadStatus.HOT
        elif new_score < 20:
            lead.status = LeadStatus.COLD
        elif new_score < 50:
            lead.status = LeadStatus.WARM
        else:
            lead.status = LeadStatus.HOT
        if not lead.pipeline_stage:
            lead.pipeline_stage = "entrada"
            lead.stage_entered_at = datetime.now()

        await db.commit()
        await db.refresh(lead)

        # 6. Auto-advance pipeline
        try:
            async with db.begin_nested():
                await PipelineService.auto_advance_stage(db, lead.id)
                await db.refresh(lead)
        except Exception as e:
            logger.error("Error auto-advancing pipeline stage: %s", e)
        try:
            async with db.begin_nested():
                await PipelineService.actualizar_pipeline_stage(db, lead)
                await db.refresh(lead)
        except Exception as e:
            logger.error("Error updating pipeline stage: %s", e)
        await db.commit()
        await db.refresh(lead)

        # 7. Invalidate context cache so we get the latest messages, then re-fetch
        from app.core.cache import cache_delete
        await cache_delete(f"lead_context:{lead.id}")
        context = await LeadContextService.get_lead_context(db, lead.id)
        broker_id = current_user.get("broker_id") if current_user else None

        # 7b. Semantic cache check (skip for PII / complex messages)
        _semantic_cache_hit = False
        if broker_id:
            _cached_response = await SemanticCache.lookup(message, broker_id)
            if _cached_response:
                logger.debug("[Orchestrator] Semantic cache HIT for broker_id=%s", broker_id)
                _semantic_cache_hit = True
                ai_response = _cached_response
                function_calls = []

        system_prompt, contents, static_system_prompt = await LLMServiceFacade.build_llm_prompt(
            context, message, db=db, broker_id=broker_id
        )
        from google.genai import types as genai_types

        # ai_response / function_calls may already be set by semantic cache hit
        if not _semantic_cache_hit:
            if _MCP_AVAILABLE and MCPClientAdapter is not None:
                async with MCPClientAdapter() as mcp_client:
                    tool_definitions = await mcp_client.list_tools()

                    async def tool_executor(tool_name: str, arguments: dict):
                        try:
                            arguments["lead_id"] = current_lead_id
                            return await mcp_client.call_tool(tool_name, arguments)
                        except Exception as e:
                            logger.error("Error executing MCP tool %s: %s", tool_name, e)
                            return {"error": str(e), "success": False}

                    ai_response, function_calls = await LLMServiceFacade.generate_response_with_function_calling(
                        system_prompt=system_prompt,
                        contents=contents,
                        tools=tool_definitions,
                        tool_executor=tool_executor,
                        broker_id=broker_id,
                        lead_id=current_lead_id,
                        static_system_prompt=static_system_prompt,
                    )
            else:
                # Fallback without MCP: try with AgentToolsService tools; if SDK validation fails, generate without tools
                function_declarations = AgentToolsService.get_function_declarations()
                tools = [genai_types.Tool(function_declarations=function_declarations)]

                async def tool_executor(tool_name: str, arguments: dict):
                    try:
                        async with db.begin_nested():
                            return await AgentToolsService.execute_tool(
                                db=db,
                                tool_name=tool_name,
                                arguments=arguments,
                                lead_id=current_lead_id,
                                agent_id=None,
                            )
                    except Exception as e:
                        logger.error("Error executing tool %s: %s", tool_name, e)
                        return {"error": str(e), "success": False}

                try:
                    ai_response, function_calls = await LLMServiceFacade.generate_response_with_function_calling(
                        system_prompt=system_prompt,
                        contents=contents,
                        tools=tools,
                        tool_executor=tool_executor,
                        broker_id=broker_id,
                        lead_id=current_lead_id,
                        static_system_prompt=static_system_prompt,
                    )
                except Exception as e:
                    logger.warning("generate_response_with_function_calling failed (%s), retrying without tools", e)
                    ai_response, function_calls = await LLMServiceFacade.generate_response_with_function_calling(
                        system_prompt=system_prompt,
                        contents=contents,
                        tools=[],
                        tool_executor=None,
                        broker_id=broker_id,
                        lead_id=current_lead_id,
                        static_system_prompt=static_system_prompt,
                    )

            # Store non-PII responses in semantic cache for future hits
            if broker_id and ai_response:
                try:
                    await SemanticCache.store(message, ai_response, broker_id)
                except Exception as _sc_exc:
                    logger.debug("[Orchestrator] SemanticCache.store failed: %s", _sc_exc)

        if new_score != old_score:
            await ActivityService.log_activity(
                db,
                lead_id=current_lead_id,
                action_type="score_update",
                details={
                    "old_score": old_score,
                    "new_score": new_score,
                    "delta": score_delta,
                    "reason": "test_chat",
                    "analysis": analysis,
                },
            )
        if broker_id:
            await ChatService.log_message(
                db,
                lead_id=current_lead_id,
                broker_id=broker_id,
                provider_name=provider_name,
                message_data=ChatMessageData(
                    channel_user_id="0",
                    channel_username=None,
                    channel_message_id=None,
                    message_text=ai_response,
                    direction="out",
                ),
                ai_used=True,
            )
        else:
            await ActivityService.log_telegram_message(
                db, lead_id=current_lead_id, telegram_user_id=0, message_text=ai_response, direction="out"
            )
        await ActivityService.log_activity(
            db,
            lead_id=current_lead_id,
            action_type="message",
            details={
                "direction": "in",
                "message": message,
                "response": ai_response,
                "ai_used": True,
            },
        )

        # Broadcast AI response + stop typing indicator (TASK-027)
        if broker_id:
            try:
                from app.core.websocket_manager import ws_manager
                await ws_manager.broadcast(broker_id, "typing", {
                    "lead_id": current_lead_id,
                    "is_typing": False,
                })
                await ws_manager.broadcast(broker_id, "ai_response", {
                    "lead_id": current_lead_id,
                    "message": ai_response[:200],
                    "lead_score": lead.lead_score,
                    "lead_status": str(lead.status),
                })
            except Exception as _ws_exc:
                logger.debug("[WS] Broadcast error: %s", _ws_exc)

        await db.refresh(lead)

        return ChatResult(
            response=ai_response,
            lead_id=current_lead_id,
            lead_score=new_score,
            lead_status=lead.status,
            conversation_state=conv_machine.state,
        )
