"""
Observability API — overview metrics, conversation debugger, cost analytics,
agent performance, handoff monitoring, alerts, health, RAG analytics, live tail.

All endpoints require ADMIN or SUPERADMIN role.
SUPERADMIN can query across all brokers (broker_id=None).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text, and_, Float, cast, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserRole
from app.models.agent_event import AgentEvent
from app.models.lead import Lead
from app.models.chat_message import ChatMessage
from app.models.llm_call import LLMCall
from app.models.observability_alert import ObservabilityAlert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/observability", tags=["observability"])


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _require_admin(user) -> None:
    role = user.get("role", "") if isinstance(user, dict) else getattr(user, "role", "")
    role_str = role.value if hasattr(role, "value") else str(role)
    if role_str.upper() not in ("ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="Admin access required")


def _broker_filter(user, broker_id: Optional[int]) -> Optional[int]:
    """Return the effective broker_id for a query."""
    role = user.get("role", "") if isinstance(user, dict) else getattr(user, "role", "")
    role_str = (role.value if hasattr(role, "value") else str(role)).upper()
    if role_str == "SUPERADMIN":
        return broker_id  # None = all brokers
    uid_broker = user.get("broker_id") if isinstance(user, dict) else getattr(user, "broker_id", None)
    return uid_broker


def _period_delta(period: str) -> timedelta:
    mapping = {"1h": timedelta(hours=1), "24h": timedelta(hours=24),
               "7d": timedelta(days=7), "30d": timedelta(days=30)}
    return mapping.get(period, timedelta(hours=24))


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get("/overview")
async def get_overview(
    period: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Overview dashboard metrics: counts, costs, response times, pipeline funnel,
    agent distribution, and time-series data.
    """
    _require_admin(current_user)
    eff_broker = _broker_filter(current_user, broker_id)
    since = datetime.now(timezone.utc) - _period_delta(period)

    # Base filter for agent_events
    def ae_where(q):
        q = q.where(AgentEvent.created_at >= since)
        if eff_broker is not None:
            q = q.where(AgentEvent.broker_id == eff_broker)
        return q

    # Active conversations (human_mode + active leads with recent messages)
    active_q = select(func.count(func.distinct(ChatMessage.lead_id))).where(
        ChatMessage.created_at >= datetime.now(timezone.utc) - timedelta(hours=1)
    )
    if eff_broker:
        active_q = active_q.where(ChatMessage.broker_id == eff_broker)
    active_conversations = (await db.execute(active_q)).scalar_one() or 0

    # LLM cost today
    cost_q = ae_where(select(func.sum(AgentEvent.llm_cost_usd)).where(
        AgentEvent.event_type == "llm_call"
    ))
    llm_cost = (await db.execute(cost_q)).scalar_one() or 0.0

    # Average response latency
    lat_q = ae_where(select(func.avg(AgentEvent.llm_latency_ms)).where(
        AgentEvent.event_type == "llm_call"
    ))
    avg_latency_ms = (await db.execute(lat_q)).scalar_one() or 0

    # Escalation count and rate
    total_msgs_q = ae_where(select(func.count()).where(AgentEvent.event_type == "llm_call"))
    total_llm = (await db.execute(total_msgs_q)).scalar_one() or 0

    esc_q = ae_where(select(func.count()).where(AgentEvent.event_type == "escalation_triggered"))
    escalations = (await db.execute(esc_q)).scalar_one() or 0
    escalation_rate = round((escalations / total_llm * 100) if total_llm else 0, 1)

    # Leads in human_mode
    hm_q = select(func.count()).where(Lead.human_mode.is_(True))
    if eff_broker:
        hm_q = hm_q.where(Lead.broker_id == eff_broker)
    human_mode_count = (await db.execute(hm_q)).scalar_one() or 0

    # Stale human_mode (>15 min without response)
    stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
    stale_q = select(func.count()).where(
        Lead.human_mode.is_(True),
        Lead.human_taken_at < stale_threshold,
    )
    if eff_broker:
        stale_q = stale_q.where(Lead.broker_id == eff_broker)
    stale_human_mode = (await db.execute(stale_q)).scalar_one() or 0

    # Token totals
    tok_q = ae_where(select(
        func.sum(AgentEvent.input_tokens),
        func.sum(AgentEvent.output_tokens),
    ).where(AgentEvent.event_type == "llm_call"))
    tok_row = (await db.execute(tok_q)).one()
    tokens = {"input": tok_row[0] or 0, "output": tok_row[1] or 0}

    # Fallbacks
    fb_q = ae_where(select(func.count()).where(AgentEvent.event_type == "fallback_triggered"))
    fallback_count = (await db.execute(fb_q)).scalar_one() or 0

    # Errors
    err_q = ae_where(select(func.count()).where(AgentEvent.event_type == "error"))
    error_count = (await db.execute(err_q)).scalar_one() or 0

    # Agent distribution (last 24h)
    agent_dist_q = ae_where(select(
        AgentEvent.agent_type,
        func.count().label("count"),
    ).where(
        AgentEvent.event_type == "agent_selected",
        AgentEvent.agent_type.isnot(None),
    ).group_by(AgentEvent.agent_type))
    agent_dist_rows = (await db.execute(agent_dist_q)).all()
    agent_distribution = [{"agent": row[0], "count": row[1]} for row in agent_dist_rows]

    # Pipeline funnel (leads per stage)
    funnel_q = select(Lead.pipeline_stage, func.count().label("count")).group_by(Lead.pipeline_stage)
    if eff_broker:
        funnel_q = funnel_q.where(Lead.broker_id == eff_broker)
    funnel_rows = (await db.execute(funnel_q)).all()
    pipeline_funnel = [{"stage": row[0], "count": row[1]} for row in funnel_rows if row[0]]

    # Messages by hour (last 48h — sampled as hourly buckets)
    msgs_hourly_q = text("""
        SELECT date_trunc('hour', created_at) AS hour,
               COUNT(*) FILTER (WHERE direction = 'in') AS inbound,
               COUNT(*) FILTER (WHERE direction = 'out') AS outbound
        FROM chat_messages
        WHERE created_at >= NOW() - INTERVAL '48 hours'
          AND (CAST(:broker_id AS int) IS NULL OR broker_id = :broker_id)
        GROUP BY 1 ORDER BY 1
    """)
    msgs_rows = (await db.execute(msgs_hourly_q, {"broker_id": eff_broker})).fetchall()
    messages_by_hour = [
        {"hour": row[0].isoformat(), "inbound": row[1], "outbound": row[2]}
        for row in msgs_rows
    ]

    return {
        "period": period,
        "active_conversations": active_conversations,
        "llm_cost_usd": round(float(llm_cost), 4),
        "avg_response_time_ms": int(avg_latency_ms),
        "escalation_rate_pct": escalation_rate,
        "leads_in_human_mode": human_mode_count,
        "leads_human_mode_stale": stale_human_mode,
        "tokens": tokens,
        "fallback_count": fallback_count,
        "error_count": error_count,
        "agent_distribution": agent_distribution,
        "pipeline_funnel": pipeline_funnel,
        "messages_by_hour": messages_by_hour,
    }


# ── Conversation debugger ─────────────────────────────────────────────────────

@router.get("/conversations/{lead_id}/trace")
async def get_conversation_trace(
    lead_id: int,
    include_prompts: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full conversation trace for the debugger.
    Returns:
      - summary: header stats (name, channel, score, stage, cost, tokens…)
      - messages: chat bubbles (lead / bot / human_agent)
      - timeline: internal events (llm_call, handoff, score_change, sentiment…)
    """
    _require_admin(current_user)

    # ── Lead ──────────────────────────────────────────────────────────────────
    lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    meta = lead.lead_metadata or {}
    lead_name = meta.get("nombre") or meta.get("name") or lead.name or lead.phone or str(lead_id)

    # ── Messages ─────────────────────────────────────────────────────────────
    msgs_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.lead_id == lead_id)
        .order_by(ChatMessage.created_at)
    )
    messages = msgs_result.scalars().all()

    # ── Agent events ──────────────────────────────────────────────────────────
    events_result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.lead_id == lead_id)
        .order_by(AgentEvent.created_at)
    )
    events = events_result.scalars().all()

    # ── Derive channel from first inbound message ─────────────────────────────
    channel = "webchat"
    for m in messages:
        if m.direction in ("in", "INBOUND") or (hasattr(m.direction, "value") and m.direction.value == "in"):
            channel = m.provider.value if hasattr(m.provider, "value") else str(m.provider)
            break

    # ── Summary ───────────────────────────────────────────────────────────────
    llm_events = [e for e in events if e.event_type == "llm_call"]
    total_tokens = sum((e.input_tokens or 0) + (e.output_tokens or 0) for e in llm_events)
    total_cost = round(sum(e.llm_cost_usd or 0 for e in llm_events), 6)

    current_agent = ""
    for ev in reversed(events):
        if ev.agent_type:
            current_agent = ev.agent_type
            break

    started_at = messages[0].created_at.isoformat() if messages else (
        events[0].created_at.isoformat() if events else None
    )
    last_activity = messages[-1].created_at.isoformat() if messages else (
        events[-1].created_at.isoformat() if events else None
    )

    summary = {
        "lead_id": lead_id,
        "lead_name": lead_name,
        "channel": channel,
        "lead_score": lead.lead_score or 0,
        "current_stage": lead.pipeline_stage or "",
        "current_agent": current_agent,
        "started_at": started_at,
        "last_activity": last_activity,
        "total_messages": len(messages),
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "human_mode": bool(lead.human_mode),
    }

    # ── Chat messages (left panel) ────────────────────────────────────────────
    chat_messages = _build_chat_messages(messages)

    # ── Internal timeline (right panel) ──────────────────────────────────────
    timeline = _build_timeline(events, include_prompts=include_prompts)

    return {
        "lead_id": lead_id,
        "summary": summary,
        "messages": chat_messages,
        "timeline": timeline,
    }


def _build_chat_messages(messages) -> List[Dict]:
    """Build the left-panel chat bubble list."""
    result = []
    for msg in messages:
        direction = msg.direction.value if hasattr(msg.direction, "value") else str(msg.direction)
        is_inbound = direction in ("in", "inbound", "INBOUND")
        ai_used = bool(msg.ai_response_used)

        if is_inbound:
            sender_type = "lead"
        elif ai_used:
            sender_type = "bot"
        else:
            sender_type = "human_agent"

        result.append({
            "id": f"msg-{msg.id}",
            "timestamp": msg.created_at.isoformat() if msg.created_at else None,
            "direction": "inbound" if is_inbound else "outbound",
            "sender_type": sender_type,
            "content": msg.message_text or "",
        })
    return result


def _build_timeline(events, include_prompts: bool = False) -> List[Dict]:
    """Build the right-panel internal event timeline."""
    items: List[Dict[str, Any]] = []

    for ev in events:
        ts = ev.created_at.isoformat() if ev.created_at else None
        base = {"id": f"ev-{ev.id}", "timestamp": ts}

        if ev.event_type == "agent_selected":
            items.append({**base, "type": "agent_selected", "agent": ev.agent_type})

        elif ev.event_type == "llm_call":
            meta = ev.event_metadata or {}
            item: Dict[str, Any] = {
                **base,
                "type": "llm_call",
                "agent": ev.agent_type,
                "provider": ev.llm_provider,
                "model": ev.llm_model,
                "input_tokens": ev.input_tokens,
                "output_tokens": ev.output_tokens,
                "total_tokens": (ev.input_tokens or 0) + (ev.output_tokens or 0),
                "latency_ms": ev.llm_latency_ms,
                "cost_usd": ev.llm_cost_usd,
                "prompt_hash": ev.system_prompt_hash,
                "completion_snippet": ev.raw_response_snippet,
                "event_metadata": ev.event_metadata,  # user_messages, rag_chunks, temperature
            }
            if meta.get("thinking_content"):
                item["thinking_content"] = meta["thinking_content"]
            items.append(item)

        elif ev.event_type == "agent_handoff":
            items.append({
                **base,
                "type": "handoff",
                "from_agent": ev.from_agent,
                "to_agent": ev.to_agent,
                "reason": ev.handoff_reason,
            })

        elif ev.event_type == "tool_called":
            items.append({
                **base,
                "type": "tool",
                "tool_name": ev.tool_name,
                "tool_input": ev.tool_input,
                "tool_output": ev.tool_output,
                "latency_ms": ev.tool_latency_ms,
                "success": ev.tool_success,
            })

        elif ev.event_type == "pipeline_stage_changed":
            items.append({
                **base,
                "type": "pipeline_stage",
                "stage_before": ev.pipeline_stage_before,
                "stage_after": ev.pipeline_stage_after,
                "score_before": ev.lead_score_before,
                "score_after": ev.lead_score_after,
            })

        elif ev.event_type in ("lead_score_changed", "qualification_analysis"):
            items.append({
                **base,
                "type": "score_change",
                "agent": ev.agent_type,
                "score_before": ev.lead_score_before,
                "score_after": ev.lead_score_after,
                "score_delta": ev.score_delta,
                "extracted_fields": ev.extracted_fields,
            })

        elif ev.event_type == "sentiment_analyzed":
            m = ev.event_metadata or {}
            items.append({
                **base,
                "type": "sentiment",
                "score": m.get("frustration_score") or m.get("score"),
                "emotions": m.get("emotions", []),
                "escalated": m.get("escalated", False),
                "event_metadata": ev.event_metadata,  # includes action_level, keywords_matched
            })

        elif ev.event_type == "escalation_triggered":
            m = ev.event_metadata or {}
            items.append({
                **base,
                "type": "escalation",
                "reason": m.get("reason") or ev.handoff_reason,
                "frustration_score": m.get("frustration_score"),
            })

        elif ev.event_type == "human_takeover":
            m = ev.event_metadata or {}
            items.append({
                **base,
                "type": "human_takeover",
                "agent_id": m.get("agent_id") or m.get("taken_by"),
                "agent_name": m.get("agent_name"),
            })

        elif ev.event_type == "human_release":
            m = ev.event_metadata or {}
            items.append({
                **base,
                "type": "human_release",
                "note": m.get("note") or m.get("human_release_note"),
                "sentiment_reset": m.get("sentiment_reset", False),
            })

        elif ev.event_type == "error":
            items.append({
                **base,
                "type": "error",
                "agent": ev.agent_type,
                "error_type": ev.error_type,
                "error_message": ev.error_message,
            })

        elif ev.event_type == "fallback_triggered":
            m = ev.event_metadata or {}
            items.append({
                **base,
                "type": "fallback",
                "provider": ev.llm_provider,
                "reason": m.get("reason"),
            })

        elif ev.event_type == "context_update":
            m = ev.event_metadata or {}
            item: Dict[str, Any] = {
                **base,
                "type": "context_update",
                "agent": ev.agent_type,
                "hop": m.get("hop", 0),
                "context_before": m.get("context_before", {}),
                "context_updates": m.get("context_updates", {}),
            }
            if m.get("handoff"):
                item["handoff"] = m["handoff"]
            items.append(item)

        # skip: appointment_created, property_search, llm_response, tool_result
        # (they're covered by the events above or not useful in the UI)

    items.sort(key=lambda x: x.get("timestamp") or "")
    return items


@router.get("/conversations/search")
async def search_conversations(
    q: Optional[str] = None,
    query: Optional[str] = None,  # alias kept for backward compat
    broker_id: Optional[int] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search conversations using the Conversation table (populated by the orchestrator)."""
    _require_admin(current_user)
    from app.models.conversation import Conversation

    search_term = q or query
    eff_broker = _broker_filter(current_user, broker_id)

    base_q = select(Conversation).join(Lead, Lead.id == Conversation.lead_id)
    if eff_broker:
        base_q = base_q.where(Conversation.broker_id == eff_broker)
    if search_term:
        like = f"%{search_term}%"
        base_q = base_q.where(
            Lead.name.ilike(like) | Lead.phone.ilike(like)
        )

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar_one()

    rows = (
        await db.execute(
            base_q
            .add_columns(Lead)
            .order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    # Fetch last message text per conversation lead in one pass
    conv_lead_ids = [row[1].id for row in rows]
    last_msgs: dict[int, str] = {}
    if conv_lead_ids:
        lm_result = await db.execute(
            select(ChatMessage.lead_id, ChatMessage.message_text)
            .where(ChatMessage.lead_id.in_(conv_lead_ids))
            .order_by(ChatMessage.lead_id, ChatMessage.id.desc())
            .distinct(ChatMessage.lead_id)
        )
        for lead_id_val, msg_text in lm_result.all():
            last_msgs[lead_id_val] = msg_text or ""

    items = []
    for row in rows:
        conv: Conversation = row[0]
        lead: Lead = row[1]
        meta = lead.lead_metadata or {}
        lead_name = meta.get("nombre") or meta.get("name") or lead.name or lead.phone or str(lead.id)
        last_activity = (
            conv.last_message_at.isoformat() if conv.last_message_at
            else (conv.started_at.isoformat() if conv.started_at else "")
        )
        items.append({
            "lead_id": conv.lead_id,
            "lead_name": lead_name,
            "current_stage": lead.pipeline_stage or "",
            "current_agent": conv.current_agent or "",
            "last_message": last_msgs.get(lead.id, ""),
            "last_activity": last_activity,
            "total_messages": conv.message_count,
            "human_mode": conv.human_mode,
        })

    return {"total": total, "items": items}


# ── Agent performance ─────────────────────────────────────────────────────────

@router.get("/agents/performance")
async def get_agent_performance(
    period: str = Query("7d", regex="^(24h|7d|30d)$"),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Comparative performance table across all agents."""
    _require_admin(current_user)
    eff_broker = _broker_filter(current_user, broker_id)
    since = datetime.now(timezone.utc) - _period_delta(period)

    rows = await db.execute(text("""
        SELECT
            agent_type,
            COUNT(*) FILTER (WHERE event_type = 'agent_selected') AS messages_handled,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY llm_latency_ms) FILTER (WHERE event_type = 'llm_call') AS latency_p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY llm_latency_ms) FILTER (WHERE event_type = 'llm_call') AS latency_p95,
            ROUND(AVG(input_tokens + output_tokens) FILTER (WHERE event_type = 'llm_call')::numeric, 0) AS avg_tokens,
            ROUND(AVG(llm_cost_usd) FILTER (WHERE event_type = 'llm_call')::numeric, 6) AS avg_cost_per_call,
            COUNT(*) FILTER (WHERE event_type = 'agent_handoff') AS handoffs_emitted,
            COUNT(*) FILTER (WHERE event_type = 'error') AS errors
        FROM agent_events
        WHERE created_at >= :since
          AND (CAST(:broker_id AS int) IS NULL OR broker_id = :broker_id)
          AND agent_type IS NOT NULL
        GROUP BY agent_type
        ORDER BY messages_handled DESC
    """), {"since": since, "broker_id": eff_broker})

    return {
        "period": period,
        "agents": [
            {
                "agent_type": row[0],
                "messages_handled": row[1] or 0,
                "latency_p50_ms": int(row[2] or 0),
                "latency_p95_ms": int(row[3] or 0),
                "avg_tokens": int(row[4] or 0),
                "avg_cost_usd": float(row[5] or 0),
                "handoffs_emitted": row[6] or 0,
                "errors": row[7] or 0,
            }
            for row in rows
        ],
    }


# ── Handoffs & escalations ────────────────────────────────────────────────────

@router.get("/handoffs/flow")
async def get_handoff_flow(
    period: str = Query("7d", regex="^(24h|7d|30d)$"),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Agent-to-agent flow data for Sankey/chord diagram."""
    _require_admin(current_user)
    eff_broker = _broker_filter(current_user, broker_id)
    since = datetime.now(timezone.utc) - _period_delta(period)

    rows = await db.execute(
        select(
            AgentEvent.from_agent,
            AgentEvent.to_agent,
            func.count().label("count"),
        ).where(
            AgentEvent.event_type == "agent_handoff",
            AgentEvent.created_at >= since,
            *([] if eff_broker is None else [AgentEvent.broker_id == eff_broker]),
        ).group_by(AgentEvent.from_agent, AgentEvent.to_agent)
    )
    return {
        "period": period,
        "flows": [{"from": row[0], "to": row[1], "count": row[2]} for row in rows],
    }


@router.get("/handoffs/escalations")
async def get_escalations(
    period: str = Query("7d", regex="^(24h|7d|30d)$"),
    status: Optional[str] = None,
    broker_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent escalations with context."""
    _require_admin(current_user)
    eff_broker = _broker_filter(current_user, broker_id)
    since = datetime.now(timezone.utc) - _period_delta(period)

    q = select(AgentEvent, Lead.name, Lead.phone).join(
        Lead, AgentEvent.lead_id == Lead.id, isouter=True
    ).where(
        AgentEvent.event_type == "escalation_triggered",
        AgentEvent.created_at >= since,
    )
    if eff_broker:
        q = q.where(AgentEvent.broker_id == eff_broker)

    rows = (await db.execute(q.order_by(AgentEvent.created_at.desc()).limit(limit))).all()

    return {
        "period": period,
        "escalations": [
            {
                "lead_id": row[0].lead_id,
                "lead_name": row[1] or row[2] or f"Lead {row[0].lead_id}",
                "reason": (row[0].event_metadata or {}).get("reason"),
                "frustration_score": (row[0].event_metadata or {}).get("frustration_score"),
                "created_at": row[0].created_at.isoformat() if row[0].created_at else None,
            }
            for row in rows
        ],
    }


# ── Cost analytics (enhanced) ─────────────────────────────────────────────────

@router.get("/costs/by-agent")
async def costs_by_agent(
    period: str = Query("7d", regex="^(24h|7d|30d)$"),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    eff_broker = _broker_filter(current_user, broker_id)
    since = datetime.now(timezone.utc) - _period_delta(period)

    rows = await db.execute(text("""
        SELECT agent_type,
               COUNT(*) AS calls,
               SUM(input_tokens) AS input_tokens,
               SUM(output_tokens) AS output_tokens,
               SUM(llm_cost_usd) AS total_cost,
               AVG(llm_latency_ms) AS avg_latency_ms
        FROM agent_events
        WHERE event_type = 'llm_call'
          AND created_at >= :since
          AND (CAST(:broker_id AS int) IS NULL OR broker_id = :broker_id)
        GROUP BY agent_type
        ORDER BY total_cost DESC
    """), {"since": since, "broker_id": eff_broker})

    agents = [
        {
            "agent_type": r[0],
            "call_count": r[1] or 0,
            "total_tokens": (r[2] or 0) + (r[3] or 0),
            "total_cost_usd": round(float(r[4] or 0), 6),
            "avg_cost_usd": round(float(r[4] or 0) / r[1], 6) if r[1] else 0.0,
        }
        for r in rows
    ]
    return {"period": period, "agents": agents}


@router.get("/costs/projection")
async def cost_projection(
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Monthly cost projection based on last 7 days of usage."""
    _require_admin(current_user)
    eff_broker = _broker_filter(current_user, broker_id)
    since = datetime.now(timezone.utc) - timedelta(days=7)

    result = await db.execute(text("""
        SELECT SUM(llm_cost_usd) AS cost_7d
        FROM agent_events
        WHERE event_type = 'llm_call'
          AND created_at >= :since
          AND (CAST(:broker_id AS int) IS NULL OR broker_id = :broker_id)
    """), {"since": since, "broker_id": eff_broker})

    cost_7d = float(result.scalar_one() or 0)
    daily_avg = cost_7d / 7
    monthly_projection = daily_avg * 30

    return {
        "cost_last_7d": round(cost_7d, 4),
        "daily_avg": round(daily_avg, 4),
        "monthly_projection": round(monthly_projection, 2),
        "currency": "USD",
    }


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertAction(BaseModel):
    note: Optional[str] = None


@router.get("/alerts")
async def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    broker_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    eff_broker = _broker_filter(current_user, broker_id)

    q = select(ObservabilityAlert)
    if status:
        q = q.where(ObservabilityAlert.status == status)
    if severity:
        q = q.where(ObservabilityAlert.severity == severity)
    if eff_broker:
        q = q.where(
            (ObservabilityAlert.related_broker_id == eff_broker) |
            (ObservabilityAlert.related_broker_id.is_(None))
        )

    alerts = (await db.execute(q.order_by(ObservabilityAlert.created_at.desc()).limit(limit))).scalars().all()
    formatted = [_fmt_alert(a) for a in alerts]
    return {"alerts": formatted, "total": len(formatted)}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    alert = await _get_alert(db, alert_id)
    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(timezone.utc)
    uid = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    alert.acknowledged_by = int(uid) if uid else None
    await db.commit()
    return _fmt_alert(alert)


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    alert = await _get_alert(db, alert_id)
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return _fmt_alert(alert)


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    alert = await _get_alert(db, alert_id)
    alert.status = "dismissed"
    await db.commit()
    return _fmt_alert(alert)


async def _get_alert(db: AsyncSession, alert_id: int) -> ObservabilityAlert:
    result = await db.execute(select(ObservabilityAlert).where(ObservabilityAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _fmt_alert(alert: ObservabilityAlert) -> Dict:
    return {
        "id": alert.id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "description": alert.description,
        "status": alert.status,
        "related_lead_id": alert.related_lead_id,
        "related_broker_id": alert.related_broker_id,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "alert_data": alert.alert_data,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


# ── RAG analytics ─────────────────────────────────────────────────────────────

@router.get("/rag/top-chunks")
async def rag_top_chunks(
    period: str = Query("7d", regex="^(24h|7d|30d)$"),
    broker_id: Optional[int] = None,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Most frequently retrieved knowledge_base chunks."""
    _require_admin(current_user)
    # RAG usage is tracked via event_metadata on llm_call events (future enhancement)
    # For now return a placeholder that indicates the feature is available
    return {"message": "RAG analytics will be populated once kb_chunk_id tracking is added to agent_events."}


@router.get("/rag/gaps")
async def rag_knowledge_gaps(
    period: str = Query("7d", regex="^(24h|7d|30d)$"),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queries where the RAG found no relevant content (knowledge gaps)."""
    _require_admin(current_user)
    eff_broker = _broker_filter(current_user, broker_id)
    since = datetime.now(timezone.utc) - _period_delta(period)

    q = select(AgentEvent).where(
        AgentEvent.event_type == "llm_call",
        AgentEvent.created_at >= since,
        AgentEvent.event_metadata["knowledge_gap"].astext == "true",
    )
    if eff_broker:
        q = q.where(AgentEvent.broker_id == eff_broker)

    events = (await db.execute(q.limit(100))).scalars().all()
    gaps = [
        {
            "lead_id": e.lead_id,
            "query": (e.event_metadata or {}).get("query", ""),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]
    return {"total": len(gaps), "gaps": gaps}


@router.get("/rag/property-search-effectiveness")
async def property_search_effectiveness(
    period: str = Query("7d", regex="^(24h|7d|30d)$"),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Property search effectiveness: searches performed vs. results shown."""
    _require_admin(current_user)
    eff_broker = _broker_filter(current_user, broker_id)
    since = datetime.now(timezone.utc) - _period_delta(period)

    q = select(
        func.count().label("total_searches"),
        func.avg(AgentEvent.search_results_count).label("avg_results"),
        func.sum(AgentEvent.search_results_count).label("total_results"),
        func.sum(
            cast(func.coalesce(AgentEvent.event_metadata["embedding_cost_usd"].astext, "0"), Float)
        ).label("total_embedding_cost"),
        func.avg(AgentEvent.tool_latency_ms).label("avg_latency_ms"),
    ).where(
        AgentEvent.event_type == "property_search",
        AgentEvent.created_at >= since,
    )
    if eff_broker:
        q = q.where(AgentEvent.broker_id == eff_broker)

    row = (await db.execute(q)).one()

    strategy_q = select(
        AgentEvent.search_strategy,
        func.count().label("search_count"),
        func.avg(AgentEvent.search_results_count).label("avg_results"),
        func.avg(AgentEvent.tool_latency_ms).label("avg_latency_ms"),
        func.sum(
            func.cast(
                func.coalesce(AgentEvent.event_metadata["embedding_cost_usd"].astext, "0"),
                type_=__import__("sqlalchemy").Float,
            )
        ).label("total_cost"),
    ).where(
        AgentEvent.event_type == "property_search",
        AgentEvent.created_at >= since,
    )
    if eff_broker:
        strategy_q = strategy_q.where(AgentEvent.broker_id == eff_broker)
    strategy_q = strategy_q.group_by(AgentEvent.search_strategy)
    strategy_rows = (await db.execute(strategy_q)).all()

    total_searches = row[0] or 0
    total_cost = float(row[3] or 0)

    return {
        "period": period,
        "total_searches": total_searches,
        "avg_results_per_search": round(float(row[1] or 0), 1),
        "total_results_shown": row[2] or 0,
        "total_embedding_cost_usd": round(total_cost, 6),
        "avg_embedding_cost_per_search_usd": round(total_cost / total_searches, 8) if total_searches else 0,
        "avg_latency_ms": round(float(row[4] or 0), 0) if row[4] else None,
        "by_strategy": [
            {
                "strategy": r[0],
                "search_count": r[1],
                "avg_results": round(float(r[2] or 0), 1),
                "avg_latency_ms": round(float(r[3]), 0) if r[3] else None,
                "total_cost_usd": round(float(r[4] or 0), 6),
            }
            for r in strategy_rows
            if r[0]
        ],
    }
