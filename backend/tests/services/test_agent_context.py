"""
Tests for AgentContext new fields introduced in Phase 2g, and supervisor
context propagation across hops.

Run without DB:
    python -m pytest tests/services/test_agent_context.py -v --noconftest
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.services.agents.types import (
    AgentContext, AgentResponse, AgentType, HandoffSignal,
)
from app.services.agents.supervisor import AgentSupervisor


# ── Helper ────────────────────────────────────────────────────────────────────

def _ctx(**overrides) -> AgentContext:
    defaults = dict(
        lead_id=1,
        broker_id=1,
        pipeline_stage="potencial",
        conversation_state="GREETING",
        lead_data={"broker_name": "T", "agent_name": "S"},
        message_history=[],
    )
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── New field defaults ────────────────────────────────────────────────────────

class TestAgentContextDefaults:
    def test_property_preferences_defaults_empty_dict(self):
        ctx = _ctx()
        assert ctx.property_preferences == {}

    def test_current_frustration_defaults_zero(self):
        ctx = _ctx()
        assert ctx.current_frustration == 0.0

    def test_tone_hint_defaults_none(self):
        ctx = _ctx()
        assert ctx.tone_hint is None

    def test_human_release_note_defaults_none(self):
        ctx = _ctx()
        assert ctx.human_release_note is None

    def test_last_agent_note_defaults_none(self):
        ctx = _ctx()
        assert ctx.last_agent_note is None


# ── recent_messages ───────────────────────────────────────────────────────────

class TestRecentMessages:
    def test_empty_history_returns_empty(self):
        ctx = _ctx(message_history=[])
        assert ctx.recent_messages == []

    def test_returns_last_five(self):
        history = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
        ctx = _ctx(message_history=history)
        recent = ctx.recent_messages
        assert len(recent) == 5
        assert recent[0]["content"] == "msg 5"
        assert recent[-1]["content"] == "msg 9"

    def test_fewer_than_five_returns_all(self):
        history = [{"role": "user", "content": "only one"}]
        ctx = _ctx(message_history=history)
        assert len(ctx.recent_messages) == 1

    def test_exactly_five_returns_all_five(self):
        history = [{"role": "user", "content": f"m{i}"} for i in range(5)]
        ctx = _ctx(message_history=history)
        assert len(ctx.recent_messages) == 5

    def test_original_history_unchanged(self):
        history = [{"role": "user", "content": f"m{i}"} for i in range(8)]
        ctx = _ctx(message_history=history)
        _ = ctx.recent_messages
        assert len(ctx.message_history) == 8


# ── property_preferences usage ────────────────────────────────────────────────

class TestPropertyPreferences:
    def test_can_set_property_preferences(self):
        ctx = _ctx(property_preferences={"commune": "Las Condes", "max_uf": 5000})
        assert ctx.property_preferences["commune"] == "Las Condes"

    def test_frustration_range(self):
        ctx = _ctx(current_frustration=0.75)
        assert 0.0 <= ctx.current_frustration <= 1.0


# ── Supervisor propagates new fields across hops ──────────────────────────────

class TestSupervisorContextPropagation:
    @pytest.mark.asyncio
    async def test_new_fields_preserved_after_handoff(self):
        """
        Simulate a single handoff and verify property_preferences, tone_hint,
        and current_frustration are preserved in the next agent's context.
        """
        initial_ctx = _ctx(
            pipeline_stage="calificacion_financiera",
            property_preferences={"commune": "Ñuñoa", "max_uf": 4500},
            current_frustration=0.3,
            tone_hint="empathetic",
        )

        # Mock the event_logger used in supervisor
        with patch(
            "app.services.observability.event_logger.event_logger.log_agent_selected",
            new_callable=AsyncMock,
        ), patch(
            "app.services.observability.event_logger.event_logger.log_handoff",
            new_callable=AsyncMock,
        ):
            supervisor = AgentSupervisor()

            # Track what context was passed to the second agent
            captured_contexts = []

            async def mock_process_1(message, ctx, db):
                captured_contexts.append(("agent1", ctx))
                return AgentResponse(
                    message="pase al scheduler",
                    agent_type=AgentType.PROPERTY,
                    context_updates={"something": "updated"},
                    handoff=HandoffSignal(
                        target_agent=AgentType.SCHEDULER,
                        reason="lead wants appointment",
                    ),
                )

            async def mock_process_2(message, ctx, db):
                captured_contexts.append(("agent2", ctx))
                return AgentResponse(
                    message="cita agendada",
                    agent_type=AgentType.SCHEDULER,
                )

            async def mock_should_handle_property(ctx):
                return ctx.pipeline_stage == "calificacion_financiera"

            async def mock_should_handle_scheduler(ctx):
                return True

            async def mock_should_handle_false(ctx):
                return False

            # Patch the priority agent list used by supervisor
            from app.services.agents.property import PropertyAgent
            from app.services.agents.scheduler import SchedulerAgent

            property_mock = AsyncMock(spec=PropertyAgent)
            property_mock.agent_type = AgentType.PROPERTY
            property_mock.name = "PropertyAgent"
            property_mock.should_handle = mock_should_handle_property
            property_mock.process = mock_process_1
            property_mock.should_handoff = AsyncMock(return_value=None)

            scheduler_mock = AsyncMock(spec=SchedulerAgent)
            scheduler_mock.agent_type = AgentType.SCHEDULER
            scheduler_mock.name = "SchedulerAgent"
            scheduler_mock.should_handle = mock_should_handle_scheduler
            scheduler_mock.process = mock_process_2
            scheduler_mock.should_handoff = AsyncMock(return_value=None)

            with patch(
                "app.services.agents.get_priority_agents",
                return_value=[property_mock, scheduler_mock],
            ):
                db = AsyncMock()
                result = await supervisor.process("quiero visitar", initial_ctx, db)

        # Verify second agent's context retained new fields
        assert len(captured_contexts) == 2
        _, ctx2 = captured_contexts[1]
        assert ctx2.property_preferences == {"commune": "Ñuñoa", "max_uf": 4500}
        assert ctx2.current_frustration == 0.3
        assert ctx2.tone_hint == "empathetic"


# ── AgentResponse metadata field ─────────────────────────────────────────────

class TestAgentResponseMetadata:
    def test_metadata_defaults_empty_dict(self):
        resp = AgentResponse(
            message="test",
            agent_type=AgentType.QUALIFIER,
        )
        assert resp.metadata == {}

    def test_metadata_can_carry_agent_note(self):
        resp = AgentResponse(
            message="test",
            agent_type=AgentType.QUALIFIER,
            metadata={"agent_note": "lead parece interesado en zona oriente"},
        )
        assert resp.metadata["agent_note"] == "lead parece interesado en zona oriente"
