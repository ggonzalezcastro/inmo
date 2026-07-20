"""
Tests for call_purpose threading into agent prompts (Llamadas page).

Run with:
    python -m pytest tests/services/test_agents_call_purpose.py -v --noconftest
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.agents.types import AgentContext
from app.services.agents.qualifier import QualifierAgent
from app.services.agents.scheduler import SchedulerAgent
from app.services.agents import build_context


def _context(**overrides) -> AgentContext:
    defaults = dict(
        lead_id=1,
        broker_id=1,
        pipeline_stage="entrada",
        conversation_state="GREETING",
        lead_data={"broker_name": "Inmobiliaria Test", "agent_name": "Sofía"},
        message_history=[],
        current_agent=None,
        handoff_count=0,
    )
    defaults.update(overrides)
    return AgentContext(**defaults)


class TestInjectCallPurpose:
    def test_injects_on_voice_channel_with_purpose(self):
        agent = QualifierAgent()
        ctx = _context(channel="voice", call_purpose="confirmacion_visita")
        result = agent._inject_call_purpose("BASE PROMPT", ctx)
        assert "OBJETIVO DE ESTA LLAMADA" in result
        assert "visita" in result

    def test_noop_on_chat_channel(self):
        agent = QualifierAgent()
        ctx = _context(channel="chat", call_purpose="confirmacion_visita")
        assert agent._inject_call_purpose("BASE PROMPT", ctx) == "BASE PROMPT"

    def test_noop_without_purpose(self):
        agent = QualifierAgent()
        ctx = _context(channel="voice", call_purpose=None)
        assert agent._inject_call_purpose("BASE PROMPT", ctx) == "BASE PROMPT"

    def test_noop_on_unknown_purpose(self):
        agent = QualifierAgent()
        ctx = _context(channel="voice", call_purpose="not_a_purpose")
        assert agent._inject_call_purpose("BASE PROMPT", ctx) == "BASE PROMPT"

    def test_get_system_prompt_includes_objective(self):
        agent = SchedulerAgent()
        ctx = _context(
            channel="voice",
            call_purpose="confirmacion_reunion",
            pipeline_stage="calificacion_financiera",
        )
        prompt = agent.get_system_prompt(ctx)
        assert "OBJETIVO DE ESTA LLAMADA" in prompt


class TestBuildContextCallPurpose:
    def _lead(self):
        lead = MagicMock()
        lead.id = 1
        lead.name = "Juan Pérez"
        lead.phone = "+56912345678"
        lead.email = "juan@example.com"
        lead.pipeline_stage = "entrada"
        lead.lead_metadata = {}
        lead.human_release_note = None
        return lead

    def test_call_purpose_lands_on_context(self):
        ctx = build_context(
            self._lead(), broker_id=1, channel="voice", call_purpose="reactivacion"
        )
        assert ctx.call_purpose == "reactivacion"
        assert ctx.channel == "voice"

    def test_default_is_none(self):
        ctx = build_context(self._lead(), broker_id=1)
        assert ctx.call_purpose is None
