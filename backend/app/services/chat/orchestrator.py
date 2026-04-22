"""
Chat orchestrator: coordinates lead resolution, analysis, score update,
metadata update, pipeline advancement, and LLM response generation.
Single entry point for chat flow to improve testability and maintainability.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, func

from app.models.lead import Lead, LeadStatus
from app.services.leads import LeadService, LeadContextService
from app.services.llm import LLMServiceFacade
from app.services.shared import ActivityService
from app.services.chat.service import ChatService
from app.services.chat.base_provider import ChatMessageData
from app.services.pipeline import PipelineService
from app.schemas.lead import LeadCreate
from app.shared.input_sanitizer import sanitize_chat_input, InputSanitizationError
from app.services.chat.state_machine import ConversationStateMachine
from app.services.conversations.conversation_service import ConversationService
from app.core.encryption import encrypt_metadata_fields
from sqlalchemy.future import select as _sa_select
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
        skip_inbound_log: bool = False,
        # File attachment — populated by Telegram/WhatsApp callers when the
        # incoming message contains a photo, document, or other media.
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None,
        attachment_mime_type: Optional[str] = None,
    ) -> ChatResult:
        """
        Process one chat message: get/create lead, analyze, update score/metadata,
        advance pipeline, generate AI response. Returns ChatResult.
        """
        broker_id = (current_user or {}).get("broker_id")
        logger.info(
            "[Orchestrator] START broker_id=%s lead_id=%s provider=%s skip_inbound=%s msg=%r",
            broker_id, lead_id, provider_name, skip_inbound_log, (message or "")[:60],
        )

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
        logger.info("[Orchestrator] Step 1 done — lead_id=%s stage=%s", lead.id, lead.pipeline_stage)

        # 1b-ai: Process file attachment if present (fire-and-forget, non-blocking).
        # Telegram/WhatsApp callers pass attachment_bytes when the message includes
        # a photo or document.  We process it here — after lead resolution but before
        # the advisory lock — so document intake doesn't interfere with the AI flow.
        if attachment_bytes and attachment_filename and broker_id:
            try:
                from app.models.broker import BrokerLeadConfig as _BrokerLeadConfig
                from sqlalchemy.future import select as _sel_blc
                from app.services.deals.intake import process_ai_file_attachment

                _blc_res = await db.execute(
                    _sel_blc(_BrokerLeadConfig).where(_BrokerLeadConfig.broker_id == broker_id)
                )
                _broker_lead_cfg = _blc_res.scalar_one_or_none()
                await process_ai_file_attachment(
                    db=db,
                    broker_id=broker_id,
                    lead_id=current_lead_id,
                    file_bytes=attachment_bytes,
                    filename=attachment_filename,
                    mime_type=attachment_mime_type or "application/octet-stream",
                    broker_lead_config=_broker_lead_cfg,
                )
                await db.commit()
            except Exception as _intake_exc:
                logger.warning("[Orchestrator] AI file intake error (non-fatal): %s", _intake_exc)
                try:
                    await db.rollback()
                except Exception:
                    pass


        # G7: Acquire a session-level PostgreSQL advisory lock to serialize concurrent
        # message processing for the same lead.  Use pg_try_advisory_lock to avoid
        # indefinite blocking when a prior request leaked the lock (e.g. connection
        # returned to pool before explicit unlock).  If the lock can't be acquired
        # after a few retries we proceed without it — better to risk a race than to
        # hang the request forever.
        _lock_state = [False]  # [0] = currently locked
        try:
            from sqlalchemy import text as _adv_sql
            import asyncio as _aio
            _MAX_LOCK_ATTEMPTS = 3
            for _attempt in range(_MAX_LOCK_ATTEMPTS):
                _got_lock = await db.execute(
                    _adv_sql("SELECT pg_try_advisory_lock(:lid)"), {"lid": current_lead_id}
                )
                if _got_lock.scalar():
                    _lock_state[0] = True
                    logger.debug("[Orchestrator] Advisory lock acquired for lead_id=%s (attempt=%s)", current_lead_id, _attempt)
                    break
                logger.info("[Orchestrator] Advisory lock busy for lead_id=%s (attempt=%s/%s), retrying…", current_lead_id, _attempt + 1, _MAX_LOCK_ATTEMPTS)
                await _aio.sleep(1.5)
            if not _lock_state[0]:
                logger.warning("[Orchestrator] Could not acquire advisory lock for lead_id=%s after %s attempts — proceeding without lock", current_lead_id, _MAX_LOCK_ATTEMPTS)
        except Exception as _adv_exc:
            logger.warning(
                "[Orchestrator] pg_advisory_lock unavailable for lead_id=%s (continuing): %s",
                current_lead_id, _adv_exc,
            )

        async def _release_lock() -> None:
            """Release the session-level advisory lock (G7). Idempotent."""
            if _lock_state[0]:
                _lock_state[0] = False
                try:
                    from sqlalchemy import text as _adv_u
                    await db.execute(_adv_u("SELECT pg_advisory_unlock(:lid)"), {"lid": current_lead_id})
                except Exception as _ul_exc:
                    logger.warning(
                        "[Orchestrator] pg_advisory_unlock failed lead_id=%s: %s",
                        current_lead_id, _ul_exc,
                    )

        # 1b. Get or create Conversation record (tracks this chat session)
        _conversation = None
        if broker_id:
            try:
                _conversation = await ConversationService.get_or_create(
                    db=db,
                    lead_id=lead.id,
                    broker_id=broker_id,
                    channel=provider_name or "webchat",
                )
                await db.flush()
            except Exception as _conv_exc:
                logger.warning("[Orchestrator] ConversationService.get_or_create failed (continuing): %s", _conv_exc)

        # 2. Log inbound message (skip if caller already logged it, e.g. whatsapp_tasks)
        if broker_id and not skip_inbound_log:
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
        logger.info("[Orchestrator] Step 2 done — inbound message logged")

        # ── Sync heuristic sentiment gate ────────────────────────────────────
        # Run fast regex heuristics (microseconds, zero LLM calls) BEFORE the
        # AI responds. Handles explicit human requests and loop detection with
        # immediate escalation, before sentiment scoring.
        try:
            from app.config import settings as _cfg_s
            if getattr(_cfg_s, "SENTIMENT_ANALYSIS_ENABLED", True) and broker_id:
                from app.services.sentiment.heuristics import quick_analyze as _quick_analyze
                from app.services.sentiment.scorer import (
                    ActionLevel as _AL,
                    compute_action_level as _compute_action,
                    empty_sentiment as _empty_sent,
                )
                from app.services.sentiment.escalation import apply_escalation_action as _apply_action

                # Fetch last 5 inbound messages for loop detection (lightweight query)
                _recent_inbound: list[str] = []
                try:
                    from sqlalchemy import text as _sa_text_loop
                    _loop_rows = await db.execute(
                        _sa_text_loop(
                            "SELECT message_text FROM chat_messages "
                            "WHERE lead_id = :lid AND direction = 'in' "
                            "ORDER BY created_at DESC LIMIT 5"
                        ),
                        {"lid": lead.id},
                    )
                    _recent_inbound = [r[0] for r in _loop_rows.fetchall() if r[0]]
                except Exception:
                    pass  # Loop detection is best-effort

                _quick_result = _quick_analyze(message, _recent_inbound)
                _h_result = _quick_result.sentiment
                _current_meta_sent = (lead.lead_metadata or {}).get("sentiment") or _empty_sent()

                # Build a temporary sentiment snapshot using the raw per-message
                # heuristic score (not the accumulated window) to compute the action
                # level. This is a fast gate only — the Celery task still runs the
                # full sliding-window analysis afterward.
                _temp_sent = {
                    "frustration_score": _h_result.score,
                    "escalated": _current_meta_sent.get("escalated", False),
                    "message_scores": [{"score": _h_result.score, "emotions": _h_result.emotions, "ts": ""}],
                    "tone_hint": None,
                }
                _action = _compute_action(_temp_sent)

                # Log sentiment for the conversation debugger
                if _h_result.score > 0.1 or _h_result.emotions:
                    try:
                        from app.services.observability.event_logger import event_logger
                        import asyncio as _aio
                        _aio.ensure_future(event_logger.log_sentiment_analyzed(
                            lead_id=lead.id,
                            broker_id=broker_id,
                            frustration_score=_h_result.score,
                            action_level=_action.value if hasattr(_action, "value") else str(_action),
                            emotions=list(_h_result.emotions),
                        ))
                    except Exception:
                        pass

                # Immediate escalation for explicit human request — never let the AI reply.
                if _quick_result.explicit_human_request and not lead.human_mode:
                    logger.info(
                        "[Orchestrator] explicit_human_request detected — escalating lead_id=%s", lead.id
                    )
                    await _apply_action(
                        db=db,
                        lead_id=lead.id,
                        broker_id=broker_id,
                        action=_AL.ESCALATE,
                        sentiment=_current_meta_sent,
                        last_message=message,
                        channel=provider_name or "webchat",
                        reason="explicit_request",
                    )
                    await db.refresh(lead)

                # Immediate escalation for loop detection — lead is going in circles.
                elif _quick_result.loop_detected and not lead.human_mode:
                    logger.info(
                        "[Orchestrator] loop_detected — escalating lead_id=%s", lead.id
                    )
                    await _apply_action(
                        db=db,
                        lead_id=lead.id,
                        broker_id=broker_id,
                        action=_AL.ESCALATE,
                        sentiment=_current_meta_sent,
                        last_message=message,
                        channel=provider_name or "webchat",
                        reason="loop_detected",
                    )
                    await db.refresh(lead)

                # Sensitive topic (legal threat, money complaint) + high frustration → escalate.
                elif _quick_result.sensitive_topic and _h_result.score >= 0.4 and not lead.human_mode:
                    logger.info(
                        "[Orchestrator] sensitive_topic + score=%.2f — escalating lead_id=%s",
                        _h_result.score, lead.id
                    )
                    await _apply_action(
                        db=db,
                        lead_id=lead.id,
                        broker_id=broker_id,
                        action=_AL.ESCALATE,
                        sentiment=_current_meta_sent,
                        last_message=message,
                        channel=provider_name or "webchat",
                        reason="sensitive_topic",
                    )
                    await db.refresh(lead)

                elif _action == _AL.ESCALATE:
                    # Escalate immediately — fall through to human_mode block below
                    # which will send the handoff message and return early.
                    await _apply_action(
                        db=db,
                        lead_id=lead.id,
                        broker_id=broker_id,
                        action=_AL.ESCALATE,
                        sentiment=_current_meta_sent,
                        last_message=message,
                        channel=provider_name or "webchat",
                    )
                    await db.refresh(lead)

                elif _action == _AL.ADAPT_TONE:
                    # Inject tone_hint so the agent uses softer language on this turn.
                    _tone = (
                        "calm"
                        if "confusion" in _h_result.emotions
                        and "abandonment_threat" not in _h_result.emotions
                        else "empathetic"
                    )
                    import json as _json
                    from sqlalchemy import text as _sa_text
                    _sentiment_with_hint = dict(_current_meta_sent)
                    _sentiment_with_hint["tone_hint"] = _tone
                    await db.execute(
                        _sa_text(
                            "UPDATE leads SET metadata = jsonb_set("
                            "COALESCE(metadata,'{}'), '{sentiment}',"
                            " CAST(:val AS jsonb), true) WHERE id = :lid"
                        ),
                        {"val": _json.dumps(_sentiment_with_hint), "lid": lead.id},
                    )
                    await db.commit()
                    await db.refresh(lead)

                # Off-topic / prompt injection: auto-increment counter, enable
                # do_not_reply after 3 detected messages.
                if _quick_result.off_topic_detected:
                    import json as _json
                    from sqlalchemy import text as _sa_text
                    _off_count = int((lead.lead_metadata or {}).get("off_topic_count", 0)) + 1
                    await db.execute(
                        _sa_text(
                            "UPDATE leads SET metadata = jsonb_set("
                            "jsonb_set(COALESCE(metadata,'{}'), '{off_topic_count}',"
                            " CAST(:cnt AS jsonb), true),"
                            " '{do_not_reply}', CAST(:dnr AS jsonb), true)"
                            " WHERE id = :lid"
                        ),
                        {
                            "cnt": _json.dumps(_off_count),
                            "dnr": "true" if _off_count >= 3 else "false",
                            "lid": lead.id,
                        },
                    )
                    await db.commit()
                    await db.refresh(lead)
                    if _off_count >= 3:
                        logger.info(
                            "[Orchestrator] auto do_not_reply set for lead_id=%s (off_topic_count=%d)",
                            lead.id, _off_count,
                        )

                # G14: Pre-escalation for leads with accumulated high frustration.
                # The async Celery sentiment task (Step 11) can only escalate AFTER
                # the AI has already responded, leaving a one-turn gap.  Instead of
                # a static heuristic, project the real sliding-window score with the
                # current message and escalate if the projected action is ESCALATE.
                if not lead.human_mode and _h_result.score > 0:
                    from app.services.sentiment.scorer import (
                        update_sentiment_window as _update_window,
                        compute_action_level as _compute_g14,
                    )
                    _projected = _update_window(
                        _current_meta_sent, _h_result.score, list(_h_result.emotions)
                    )
                    _projected_action = _compute_g14(_projected)
                    if _projected_action == _AL.ESCALATE:
                        logger.info(
                            "[Orchestrator] G14 pre-escalation: projected_frust=%.2f "
                            "→ escalating lead_id=%s before AI response",
                            _projected.get("frustration_score", 0), lead.id,
                        )
                        await _apply_action(
                            db=db,
                            lead_id=lead.id,
                            broker_id=broker_id,
                            action=_AL.ESCALATE,
                            sentiment=_projected,
                            last_message=message,
                            channel=provider_name or "webchat",
                            reason="accumulated_frustration",
                        )
                        await db.refresh(lead)
        except Exception as _sync_sent_exc:
            logger.debug("[Sentiment] Sync heuristic gate error: %s", _sync_sent_exc)
        logger.info("[Orchestrator] Step 2b done — sentiment gate passed, human_mode=%s", lead.human_mode)

        # ── Human mode: AI silenced ──────────────────────────────────────────
        # If a human agent has taken control, skip AI processing entirely.
        # On the FIRST message after escalation, send a one-time handoff notice.
        # After that, stay silent so the human agent can take over.
        #
        # Re-read lead with a row-level lock to get the current human_mode value
        # before acting on it. This prevents a race condition where a Celery task
        # or concurrent request updates human_mode between the initial refresh
        # (above) and this check.
        await db.execute(_sa_select(Lead).where(Lead.id == lead.id).with_for_update())
        await db.refresh(lead)
        if lead.human_mode:
            meta = lead.lead_metadata or {}
            if broker_id:
                try:
                    from app.core.websocket_manager import ws_manager
                    # Only send human_mode_incoming — it includes message_text so
                    # the frontend doesn't need a separate new_message event.
                    await ws_manager.broadcast(broker_id, "human_mode_incoming", {
                        "lead_id": lead.id,
                        "lead_name": lead.name or lead.phone,
                        "phone": lead.phone,
                        "message_text": message[:300],
                        "channel": provider_name,
                        "assigned_to": lead.human_assigned_to,
                    })
                except Exception as _ws_exc:
                    logger.debug("[WS] Human mode broadcast error: %s", _ws_exc)

            # First time in human_mode → send handoff message once
            if not meta.get("human_mode_notified"):
                # Load broker-configurable handoff message (fallback to default)
                from app.models.broker import BrokerPromptConfig
                from sqlalchemy.future import select as sa_select
                _cfg_res = await db.execute(
                    sa_select(BrokerPromptConfig).where(
                        BrokerPromptConfig.broker_id == broker_id
                    )
                )
                prompt_cfg = _cfg_res.scalar_one_or_none()
                _templates = (prompt_cfg.message_templates or {}) if prompt_cfg else {}
                _default_handoff = (
                    "Entiendo tu frustración. Un agente de nuestra inmobiliaria "
                    "se pondrá en contacto contigo muy pronto para ayudarte "
                    "personalmente. 🙏"
                )
                handoff_message = _templates.get("escalation_handoff", _default_handoff)

                # Mark as notified so future messages stay silent
                from sqlalchemy import text as sa_text
                await db.execute(
                    sa_text("""
                        UPDATE leads
                        SET metadata = jsonb_set(
                            COALESCE(metadata, '{}'),
                            '{human_mode_notified}',
                            CAST('true' AS jsonb),
                            true
                        )
                        WHERE id = :lead_id
                    """),
                    {"lead_id": lead.id},
                )
                await db.commit()
                logger.info("[Orchestrator] human_mode handoff notice sent lead_id=%s", lead.id)
                await _release_lock()
                return ChatResult(
                    response=handoff_message,
                    lead_id=lead.id,
                    lead_score=lead.lead_score or 0,
                    lead_status=str(lead.status) if lead.status else "cold",
                )

            await _release_lock()
            return ChatResult(
                response="[human_mode]",
                lead_id=lead.id,
                lead_score=lead.lead_score or 0,
                lead_status=str(lead.status) if lead.status else "cold",
            )
        # ─────────────────────────────────────────────────────────────────────

        # ── Do-not-reply mode ─────────────────────────────────────────────────
        # Silences the AI for this lead and sends a configurable fallback message
        # instead of going through the LLM. Activated manually from the dashboard
        # or automatically after 3 off-topic/prompt-injection messages.
        _dnr_meta = lead.lead_metadata or {}
        if _dnr_meta.get("do_not_reply"):
            logger.info("[Orchestrator] do_not_reply active for lead_id=%s — skipping AI", lead.id)
            from app.models.broker import BrokerPromptConfig
            from sqlalchemy.future import select as sa_select_dnr
            _cfg_res_dnr = await db.execute(
                sa_select_dnr(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
            )
            _prompt_cfg_dnr = _cfg_res_dnr.scalar_one_or_none()
            _templates_dnr = (_prompt_cfg_dnr.message_templates or {}) if _prompt_cfg_dnr else {}
            _default_dnr = "Gracias por tu mensaje. Solo puedo ayudarte con consultas sobre propiedades e inmuebles. 🏠"
            fallback_dnr = _templates_dnr.get("do_not_reply_fallback", _default_dnr)
            await _release_lock()
            return ChatResult(
                response=fallback_dnr,
                lead_id=lead.id,
                lead_score=lead.lead_score or 0,
                lead_status=str(lead.status) if lead.status else "cold",
            )
        # ─────────────────────────────────────────────────────────────────────

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
        logger.info("[Orchestrator] Step 3 — fetching lead context for lead_id=%s", lead.id)
        try:
            context = await LeadContextService.get_lead_context(db, lead.id)
            logger.info("[Orchestrator] Step 3a — context fetched, history_len=%s", len(context.get("message_history") or []))
        except Exception as _ctx_exc:
            logger.error("[Orchestrator] Step 3a FAILED — get_lead_context error: %s", _ctx_exc, exc_info=True)
            await _release_lock()
            raise

        # G5: Skip the expensive LLM qualification analysis for leads that are
        # already past the qualification stages — saves ~4-5 s and tokens per message.
        _QUALIFICATION_STAGES = {"entrada", "perfilamiento", "calificacion_financiera", "potencial"}
        _effective_stage = lead.pipeline_stage or "entrada"
        if _effective_stage in _QUALIFICATION_STAGES:
            logger.info("[Orchestrator] Step 3b — calling analyze_lead_qualification")
            try:
                analysis = await LLMServiceFacade.analyze_lead_qualification(
                    message, context, broker_id=broker_id, lead_id=lead.id
                )
            except Exception as _anlz_exc:
                logger.error("[Orchestrator] Step 3b FAILED — analyze_lead_qualification error: %s", _anlz_exc, exc_info=True)
                await _release_lock()
                raise
        else:
            logger.info("[Orchestrator] Step 3b — skipping analyze_lead_qualification (stage=%s)", lead.pipeline_stage)
            analysis = {}
        logger.info("[Orchestrator] Step 3 done — analysis score_delta=%s qualified=%s", analysis.get("score_delta"), analysis.get("qualified"))

        # 3b. Advance state machine based on LLM analysis output
        try:
            conv_machine.advance_from_llm_output(analysis)
        except Exception as sm_exc:
            logger.warning("State machine advance failed: %s", sm_exc)

        # 4. Refresh lead before score update (the row-level lock was already
        # acquired at the human_mode check above; re-using the same lock here).
        logger.info("[Orchestrator] Step 4 — updating score and metadata")
        try:
            await db.refresh(lead)

            # Atomic score update (protected by the lock above)
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
            logger.info("[Orchestrator] Step 4 done — score old=%s new=%s delta=%s", old_score, new_score, score_delta)
        except Exception as _score_exc:
            logger.error("[Orchestrator] Step 4 FAILED — score update error: %s", _score_exc, exc_info=True)
            await _release_lock()
            raise

        logger.info("[Orchestrator] Step 5 — updating lead metadata, status")
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

        # Use LLM analysis to detect interest confirmation — no keyword matching needed.
        # interest_level >= 7 or timeline == "immediate"/"30days" signals confirmed intent.
        if analysis.get("interest_level", 0) >= 7 or analysis.get("timeline") in ("immediate", "30days"):
            current_metadata["interest_confirmed"] = True
            current_metadata["interest_confirmed_at"] = datetime.now().isoformat()

        if analysis.get("salary") and not analysis.get("budget"):
            current_metadata["monthly_income"] = analysis["salary"]
            current_metadata["salary"] = analysis["salary"]
        if analysis.get("budget"):
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
        # Track when the lead was last contacted by the AI
        lead.last_contacted = datetime.now()

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

        try:
            await db.commit()
            await db.refresh(lead)
        except Exception as _commit_exc:
            logger.error("[Orchestrator] Step 5 FAILED — metadata commit error: %s", _commit_exc, exc_info=True)
            await _release_lock()
            raise
        logger.info("[Orchestrator] Step 5 done — metadata updated, status=%s", lead.status)

        # 6. Auto-advance pipeline
        logger.info("[Orchestrator] Step 6 — pipeline advancement")
        try:
            await PipelineService.auto_advance_stage(db, lead.id)
            await db.refresh(lead)
        except Exception as e:
            logger.error("Error auto-advancing pipeline stage: %s", e)
            await db.rollback()
        try:
            await PipelineService.actualizar_pipeline_stage(db, lead)
            await db.refresh(lead)
        except Exception as e:
            logger.error("Error updating pipeline stage: %s", e)
            await db.rollback()
        await db.commit()
        await db.refresh(lead)
        logger.info("[Orchestrator] Step 6 done — pipeline stage=%s", lead.pipeline_stage)

        # 7. Build AgentSupervisor context.
        # We intentionally REUSE the context dict from step 3 instead of
        # re-fetching it from the DB.  Reasons:
        #   • The inbound message was already logged by the caller (whatsapp_task /
        #     telegram_task) before invoking the orchestrator, so step-3 context
        #     already contains the full current history.
        #   • Re-fetching would trigger a second round of context-window compression
        #     (≥ 10 messages), which makes a synchronous LLM call inside the asyncio
        #     event loop and causes the worker to hang.
        #   • The `lead` ORM object is already up-to-date (refreshed in steps 5 & 6).
        # We still invalidate the Redis cache so the *next* request gets fresh data.
        logger.info("[Orchestrator] Step 7 — invalidating cache and calling AgentSupervisor")
        try:
            from app.core.cache import cache_delete
            await cache_delete(f"lead_context:{lead.id}")
            logger.info("[Orchestrator] Step 7a — cache invalidated (reusing step-3 context)")
        except Exception as _cache_exc:
            logger.warning("[Orchestrator] Step 7a cache invalidation error (continuing): %s", _cache_exc)
        broker_id = current_user.get("broker_id") if current_user else None

        # ── Multi-agent path: AgentSupervisor generates the response ─────────
        from app.services.agents import AgentSupervisor, build_context
        from app.models.broker import BrokerPromptConfig
        from sqlalchemy.future import select as _select

        # Load broker config: prompt overrides + broker_name + agent_name
        _broker_overrides: dict = {}
        _broker_name = ""
        _agent_name = "Sofía"
        try:
            from app.models.broker import Broker
            _cfg_res = await db.execute(
                _select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
            )
            _broker_cfg = _cfg_res.scalars().first()
            if _broker_cfg:
                if isinstance(_broker_cfg.situation_handlers, dict):
                    for _k, _v in _broker_cfg.situation_handlers.items():
                        if _k.startswith("_agent_") and _v:
                            _broker_overrides[_k[len("_agent_"):]] = _v
                        elif _k.startswith("_skill_") and _v:
                            # strip leading _ only: _skill_qualifier → skill_qualifier
                            _broker_overrides[_k[1:]] = _v
                _agent_name = _broker_cfg.agent_name or "Sofía"
            # Load broker name from Broker table
            _br_res = await db.execute(
                _select(Broker).where(Broker.id == broker_id)
            )
            _broker = _br_res.scalars().first()
            if _broker:
                _broker_name = _broker.name or ""
            logger.info("[Orchestrator] Step 7b — broker config loaded: agent=%s broker=%r", _agent_name, _broker_name)
        except Exception as _ov_exc:
            logger.warning("[Orchestrator] Step 7b could not load broker config (continuing): %s", _ov_exc)

        # message_history comes from ChatMessage records (already fetched above)
        _message_history = context.get("message_history", [])
        logger.info("[Orchestrator] Step 7c — building AgentContext history_len=%s", len(_message_history))

        agent_context = build_context(
            lead, broker_id,
            broker_overrides=_broker_overrides,
            message_history=_message_history,
            broker_name=_broker_name,
            agent_name=_agent_name,
            pre_analysis=analysis,
        )
        logger.info("[Orchestrator] Step 7d — calling AgentSupervisor.process stage=%s", agent_context.pipeline_stage)
        try:
            agent_result = await AgentSupervisor.process(message, agent_context, db)
        except Exception as _agent_exc:
            logger.error("[Orchestrator] Step 7 FAILED — AgentSupervisor error: %s", _agent_exc, exc_info=True)
            await _release_lock()
            raise
        ai_response = agent_result.message
        function_calls = agent_result.function_calls or []
        logger.info(
            "[Orchestrator] Step 7 done — agent=%s response_len=%d response=%r",
            agent_result.agent_type, len(ai_response or ""), (ai_response or "")[:80],
        )

        # Always persist current_agent + any context_updates from the agent.
        # G3: Use atomic jsonb_set operations to avoid overwriting concurrent
        # Celery writes (e.g. sentiment).  Each sub-field is set independently
        # so a concurrent jsonb_set on '{sentiment}' won't be clobbered.
        import json as _json_g3
        from sqlalchemy import text as _sa_text_g3

        # Build the merged metadata dict in Python (for agent_history computation)
        # but persist via individual jsonb_set calls instead of full-object replacement.
        await db.refresh(lead)
        _step8_meta = dict(lead.lead_metadata or {})

        # H5: accumulated context_updates from all hops
        _ctx_updates = dict(agent_result.context_updates or {})
        # Respect explicit current_agent override from agents (e.g. PropertyAgent
        # zero-results sets current_agent → qualifier so next turn qualifies the lead).
        if "current_agent" not in _ctx_updates:
            _ctx_updates["current_agent"] = agent_result.agent_type.value

        # H6: build full agent_history array
        agents_chain = (agent_result.metadata or {}).get("agents_chain", [agent_result.agent_type.value])
        agent_history = list(_step8_meta.get("agent_history") or [])
        for _agent_name_chain in agents_chain:
            agent_history.append({
                "agent": _agent_name_chain,
                "at": datetime.now(timezone.utc).isoformat(),
                "stage": lead.pipeline_stage,
            })
        _ctx_updates["agent_history"] = agent_history[-20:]

        # G8: mark handoff context as consumed so it won't be re-injected next turn
        _handoff_at = _ctx_updates.get("_handoff_at") or _step8_meta.get("_handoff_at")
        if _handoff_at:
            _ctx_updates["_last_consumed_handoff_at"] = _handoff_at

        # Encrypt sensitive fields before persisting (salary, dicom_status, etc.)
        # so jsonb_set does not bypass the encryption layer.
        from app.core.encryption import SENSITIVE_FIELDS as _SENS, encrypt_value as _enc_val
        for _skey in _SENS:
            if _skey in _ctx_updates and _ctx_updates[_skey] is not None:
                _ctx_updates[_skey] = _enc_val(_ctx_updates[_skey])

        # Atomic jsonb_set: chain all updates into a single UPDATE statement.
        # Each key is set via nested jsonb_set so the write is atomic.
        _set_expr = "COALESCE(metadata, '{}'::jsonb)"
        _params: dict = {"lid": lead.id}
        for _idx, (_key, _val) in enumerate(_ctx_updates.items()):
            _pkey = f"k{_idx}"
            _pval = f"v{_idx}"
            _set_expr = f"jsonb_set({_set_expr}, ARRAY[:{_pkey}], CAST(:{_pval} AS jsonb), true)"
            _params[_pkey] = _key
            _params[_pval] = _json_g3.dumps(_val)

        try:
            await db.execute(
                _sa_text_g3(f"UPDATE leads SET metadata = {_set_expr} WHERE id = :lid"),
                _params,
            )
            await db.commit()
            await db.refresh(lead)
            logger.info("[Orchestrator] Step 8 done — agent metadata persisted (atomic jsonb_set)")
        except Exception as _meta_commit_exc:
            logger.error(
                "[Orchestrator] Step 8 commit failed — agent_history/context_updates NOT persisted: %s",
                _meta_commit_exc,
                exc_info=True,
            )
            try:
                await db.rollback()
            except Exception:
                pass
            # Degrade gracefully: AI response was already generated.
            # Next request will rebuild context from the last committed state.

        # 8a-post: When scheduler created an appointment, advance to agendado directly.
        # Step 6 runs before Step 7 so the appointment doesn't exist yet during the
        # normal advancement check — we must re-check here regardless of current stage.
        if agent_result.context_updates and agent_result.context_updates.get("appointment_pending"):
            _terminal_stages = {"agendado", "ganado", "perdido", "seguimiento", "referidos"}
            if lead.pipeline_stage not in _terminal_stages:
                try:
                    from app.services.pipeline.advancement_service import move_lead_to_stage
                    await move_lead_to_stage(db, lead.id, "agendado", "Auto: cita confirmada por agente")
                    await db.refresh(lead)
                    logger.info("[Orchestrator] Step 8a-post — advanced to agendado (stage was %s)", lead.pipeline_stage)
                except Exception as _post_adv_exc:
                    logger.warning("[Orchestrator] Step 8a-post advancement failed: %s", _post_adv_exc)

        # 8b. Update Conversation stats (message count, last_message_at, agent state)
        if _conversation:
            try:
                await ConversationService.on_message(db, _conversation.id)
                await ConversationService.update_agent_state(
                    db,
                    _conversation.id,
                    current_agent=agent_result.agent_type.value,
                    conversation_state=(lead.lead_metadata or {}).get("conversation_state"),
                )
                await db.commit()
            except Exception as _conv_upd_exc:
                logger.warning("[Orchestrator] ConversationService update failed (continuing): %s", _conv_upd_exc)

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

        # ── Response-time metrics + fast-responder tag (on_message) ─────────
        # Recompute bot→lead turnaround after every exchange and apply/remove
        # the ``respuesta_rapida`` tag. The full lead_score recalculation
        # remains in the daily Celery task; here we only persist the tag and
        # the metrics dict for real-time UI.
        try:
            from app.services.leads.response_metrics import (
                update_lead_response_metrics,
            )
            from app.services.leads.constants import FAST_RESPONDER_TAG

            _result = await update_lead_response_metrics(db, current_lead_id)
            await db.commit()
            await db.refresh(lead)

            if _result["tag_changed"]:
                # Activity log for auditability
                try:
                    await ActivityService.log_activity(
                        db,
                        lead_id=current_lead_id,
                        action_type="tag_changed",
                        details={
                            "tag": FAST_RESPONDER_TAG,
                            "applied": _result["applied"],
                            "metrics": _result["metrics"],
                        },
                    )
                except Exception as _act_exc:
                    logger.debug("[ResponseMetrics] activity log failed: %s", _act_exc)

                # WS broadcast so the frontend updates the badge immediately
                if broker_id:
                    try:
                        from app.core.websocket_manager import ws_manager
                        await ws_manager.broadcast(broker_id, "lead_tag_changed", {
                            "lead_id": current_lead_id,
                            "tags": _result["new_tags"],
                            "tag": FAST_RESPONDER_TAG,
                            "applied": _result["applied"],
                            "response_metrics": _result["metrics"],
                        })
                    except Exception as _ws_exc:
                        logger.debug("[ResponseMetrics] WS broadcast failed: %s", _ws_exc)
        except Exception as _rm_exc:
            logger.warning("[ResponseMetrics] computation failed (non-fatal): %s", _rm_exc)
            try:
                await db.rollback()
            except Exception:
                pass

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

        # ── Sentiment analysis (background, non-blocking) ─────────────────────
        try:
            from app.config import settings as _cfg
            if getattr(_cfg, "SENTIMENT_ANALYSIS_ENABLED", True) and broker_id:
                from app.tasks.sentiment_tasks import analyze_sentiment
                analyze_sentiment.apply_async(
                    kwargs={
                        "lead_id": current_lead_id,
                        "message": message,
                        "broker_id": broker_id,
                        "channel": provider_name or "webchat",
                    },
                    ignore_result=True,
                )
        except Exception as _sent_exc:
            logger.debug("[Sentiment] Could not dispatch task: %s", _sent_exc)

        await db.refresh(lead)

        logger.info(
            "[Orchestrator] COMPLETE lead_id=%s score=%s state=%s",
            current_lead_id, new_score, conv_machine.state,
        )
        await _release_lock()
        return ChatResult(
            response=ai_response,
            lead_id=current_lead_id,
            lead_score=new_score,
            lead_status=lead.status,
            conversation_state=conv_machine.state,
        )
