"""
Multi-agent system POC tests (TASK-026).

Tests the QualifierAgent → SchedulerAgent handoff without real LLM calls.
All LLM interactions are mocked.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)
from app.services.agents.qualifier import QualifierAgent
from app.services.agents.scheduler import SchedulerAgent, _is_appointment_confirmed
from app.services.agents.follow_up import FollowUpAgent
from app.services.agents.supervisor import AgentSupervisor
from app.services.agents import (
    build_context,
    get_priority_agents,
    qualifier_agent_instance,
    scheduler_agent_instance,
    follow_up_agent_instance,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _new_lead_context(**overrides) -> AgentContext:
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


def _qualified_context() -> AgentContext:
    """Context where all qualification fields are present and DICOM is clean."""
    return _new_lead_context(
        pipeline_stage="perfilamiento",
        conversation_state="FINANCIAL_QUAL",
        lead_data={
            "broker_name": "Inmobiliaria Test",
            "agent_name": "Sofía",
            "name": "Juan Pérez",
            "phone": "+56912345678",
            "salary": "1500000",
            "location": "Las Condes",
            "dicom_status": "clean",
        },
    )


def _dirty_dicom_context() -> AgentContext:
    """Context where lead has dirty DICOM — no handoff should happen."""
    ctx = _qualified_context()
    ctx.lead_data = {**ctx.lead_data, "dicom_status": "dirty"}
    return ctx


# ── AgentContext tests ────────────────────────────────────────────────────────

class TestAgentContext:
    def test_is_qualified_true_when_all_fields_present(self):
        ctx = _qualified_context()
        assert ctx.is_qualified()

    def test_is_qualified_false_when_missing_name(self):
        ctx = _new_lead_context(lead_data={"phone": "+56912345678", "salary": "1M"})
        assert not ctx.is_qualified()

    def test_is_qualified_false_with_dirty_dicom(self):
        ctx = _dirty_dicom_context()
        assert not ctx.is_qualified()

    def test_is_appointment_ready_requires_location(self):
        ctx = _qualified_context()
        ctx_no_location = AgentContext(
            lead_id=ctx.lead_id,
            broker_id=ctx.broker_id,
            pipeline_stage=ctx.pipeline_stage,
            conversation_state=ctx.conversation_state,
            lead_data={k: v for k, v in ctx.lead_data.items() if k != "location"},
            message_history=[],
        )
        assert not ctx_no_location.is_appointment_ready()
        assert ctx.is_appointment_ready()

    def test_missing_fields_lists_uncollected_data(self):
        ctx = _new_lead_context(lead_data={"name": "Juan"})
        missing = ctx.missing_fields()
        assert "teléfono" in missing
        assert "renta / presupuesto" in missing
        assert "nombre" not in missing  # already collected


# ── QualifierAgent routing ────────────────────────────────────────────────────

class TestQualifierAgent:
    @pytest.mark.asyncio
    async def test_should_handle_new_lead(self):
        agent = QualifierAgent()
        ctx = _new_lead_context()
        assert await agent.should_handle(ctx)

    @pytest.mark.asyncio
    async def test_should_handle_perfilamiento_stage(self):
        agent = QualifierAgent()
        ctx = _new_lead_context(pipeline_stage="perfilamiento")
        assert await agent.should_handle(ctx)

    @pytest.mark.asyncio
    async def test_should_not_handle_agendado_stage(self):
        agent = QualifierAgent()
        ctx = _new_lead_context(
            pipeline_stage="agendado",
            conversation_state="SCHEDULING",
            current_agent=AgentType.SCHEDULER,
        )
        assert not await agent.should_handle(ctx)

    def test_system_prompt_contains_agent_name(self):
        agent = QualifierAgent()
        ctx = _new_lead_context(lead_data={"agent_name": "Lucía", "broker_name": "Activa"})
        prompt = agent.get_system_prompt(ctx)
        assert "Lucía" in prompt
        assert "Activa" in prompt

    def test_system_prompt_contains_dicom_rule(self):
        agent = QualifierAgent()
        ctx = _new_lead_context()
        prompt = agent.get_system_prompt(ctx)
        assert "DICOM" in prompt
        assert "CRÍTICA" in prompt.upper() or "crítica" in prompt.lower()

    @pytest.mark.asyncio
    async def test_process_emits_handoff_when_qualified(self):
        agent = QualifierAgent()
        ctx = _qualified_context()

        mock_analysis = {
            "name": "Juan Pérez",
            "phone": "+56912345678",
            "dicom_status": "clean",
            "location": "Las Condes",
        }
        mock_response = ("¡Perfecto, Juan! Ya tenemos todo. ¿Cuándo te viene bien visitar?", [])

        with (
            patch(
                "app.services.llm.facade.LLMServiceFacade.analyze_lead_qualification",
                AsyncMock(return_value=mock_analysis),
            ),
            patch(
                "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
                AsyncMock(return_value=mock_response),
            ),
        ):
            db = MagicMock()
            response = await agent.process("Tengo DICOM limpio", ctx, db)

        assert response.agent_type == AgentType.QUALIFIER
        assert response.handoff is not None
        assert response.handoff.target_agent == AgentType.SCHEDULER

    @pytest.mark.asyncio
    async def test_process_no_handoff_with_dirty_dicom(self):
        agent = QualifierAgent()
        ctx = _dirty_dicom_context()

        mock_analysis = {"dicom_status": "dirty"}
        mock_response = ("Entiendo. Para acceder al crédito necesitas DICOM limpio.", [])

        with (
            patch(
                "app.services.llm.facade.LLMServiceFacade.analyze_lead_qualification",
                AsyncMock(return_value=mock_analysis),
            ),
            patch(
                "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
                AsyncMock(return_value=mock_response),
            ),
        ):
            db = MagicMock()
            response = await agent.process("Tengo DICOM activo", ctx, db)

        assert response.handoff is None, "Should NOT handoff when DICOM is dirty"

    @pytest.mark.asyncio
    async def test_process_graceful_on_llm_error(self):
        agent = QualifierAgent()
        ctx = _new_lead_context()

        with (
            patch(
                "app.services.llm.facade.LLMServiceFacade.analyze_lead_qualification",
                AsyncMock(side_effect=Exception("LLM timeout")),
            ),
            patch(
                "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
                AsyncMock(side_effect=Exception("LLM timeout")),
            ),
        ):
            db = MagicMock()
            response = await agent.process("Hola", ctx, db)

        # Should not raise — returns graceful message
        assert response.message
        assert response.agent_type == AgentType.QUALIFIER


# ── SchedulerAgent ────────────────────────────────────────────────────────────

class TestSchedulerAgent:
    @pytest.mark.asyncio
    async def test_should_handle_calificacion_stage(self):
        agent = SchedulerAgent()
        ctx = _new_lead_context(pipeline_stage="calificacion_financiera")
        assert await agent.should_handle(ctx)

    @pytest.mark.asyncio
    async def test_should_handle_after_qualifier_handoff(self):
        agent = SchedulerAgent()
        ctx = _qualified_context()
        ctx_with_agent = AgentContext(
            lead_id=ctx.lead_id,
            broker_id=ctx.broker_id,
            pipeline_stage=ctx.pipeline_stage,
            conversation_state=ctx.conversation_state,
            lead_data=ctx.lead_data,
            message_history=[],
            current_agent=AgentType.QUALIFIER,
        )
        assert await agent.should_handle(ctx_with_agent)

    def test_system_prompt_contains_lead_info(self):
        agent = SchedulerAgent()
        ctx = _qualified_context()
        prompt = agent.get_system_prompt(ctx)
        assert "Juan Pérez" in prompt
        assert "Las Condes" in prompt

    @pytest.mark.asyncio
    async def test_process_signals_handoff_when_appointment_confirmed(self):
        agent = SchedulerAgent()
        ctx = _qualified_context()

        mock_response = ("¡Confirmado! Te esperamos el sábado a las 10:00.", [])
        with patch(
            "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
            AsyncMock(return_value=mock_response),
        ):
            db = MagicMock()
            response = await agent.process(
                "Perfecto, ese horario me acomoda", ctx, db
            )

        assert response.handoff is not None
        assert response.handoff.target_agent == AgentType.FOLLOW_UP

    @pytest.mark.asyncio
    async def test_process_no_handoff_when_not_confirmed(self):
        agent = SchedulerAgent()
        ctx = _qualified_context()

        mock_response = ("¿Te acomodaría el sábado a las 10 o el lunes a las 14?", [])
        with patch(
            "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
            AsyncMock(return_value=mock_response),
        ):
            db = MagicMock()
            response = await agent.process("¿Tienen horario el sábado?", ctx, db)

        assert response.handoff is None


class TestAppointmentConfirmation:
    def test_confirmed_when_user_says_ok_and_agent_confirms(self):
        assert _is_appointment_confirmed("Perfecto, ese horario me acomoda", "Confirmado, te esperamos el sábado.")

    def test_not_confirmed_when_only_user_agrees(self):
        assert not _is_appointment_confirmed("Dale", "¿Qué horario prefieres?")

    def test_not_confirmed_when_neither_confirms(self):
        assert not _is_appointment_confirmed("¿Tienen el viernes?", "Tenemos viernes y sábado disponibles.")


# ── AgentSupervisor ───────────────────────────────────────────────────────────

class TestAgentSupervisor:
    @pytest.mark.asyncio
    async def test_routes_new_lead_to_qualifier(self):
        ctx = _new_lead_context()
        mock_response = AgentResponse(
            message="¡Hola! ¿Cuál es tu nombre?",
            agent_type=AgentType.QUALIFIER,
        )
        with patch.object(qualifier_agent_instance, "process", AsyncMock(return_value=mock_response)):
            db = MagicMock()
            result = await AgentSupervisor.process("Hola", ctx, db)

        assert result.agent_type == AgentType.QUALIFIER

    @pytest.mark.asyncio
    async def test_executes_handoff_from_qualifier_to_scheduler(self):
        """
        Full POC: QualifierAgent signals handoff → Supervisor routes to SchedulerAgent.
        """
        ctx = _qualified_context()

        qualifier_response = AgentResponse(
            message="¡Perfecto! Ahora te paso con nuestra asesora de visitas.",
            agent_type=AgentType.QUALIFIER,
            handoff=HandoffSignal(
                target_agent=AgentType.SCHEDULER,
                reason="All fields collected, DICOM clean.",
            ),
        )
        scheduler_response = AgentResponse(
            message="¡Hola! ¿Cuándo te viene bien visitarnos?",
            agent_type=AgentType.SCHEDULER,
        )

        with (
            patch.object(
                qualifier_agent_instance,
                "process",
                AsyncMock(return_value=qualifier_response),
            ),
            patch.object(
                scheduler_agent_instance,
                "process",
                AsyncMock(return_value=scheduler_response),
            ),
            patch.object(
                scheduler_agent_instance,
                "should_handle",
                AsyncMock(return_value=True),
            ),
        ):
            db = MagicMock()
            result = await AgentSupervisor.process(
                "Tengo todo listo, DICOM limpio", ctx, db
            )

        # The supervisor should return the Scheduler's response after handoff
        assert result.agent_type == AgentType.SCHEDULER

    @pytest.mark.asyncio
    async def test_no_infinite_loop_on_repeated_handoffs(self):
        """Guard: supervisor stops after _MAX_HANDOFFS even if agent keeps signalling."""
        ctx = _new_lead_context()

        infinite_handoff = AgentResponse(
            message="Still routing...",
            agent_type=AgentType.QUALIFIER,
            handoff=HandoffSignal(
                target_agent=AgentType.QUALIFIER,  # routes back to itself
                reason="loop test",
            ),
        )
        with patch.object(qualifier_agent_instance, "process", AsyncMock(return_value=infinite_handoff)):
            db = MagicMock()
            # Must not raise; must terminate
            result = await AgentSupervisor.process("loop me", ctx, db)

        assert result is not None  # returned something


# ── Agent registry ────────────────────────────────────────────────────────────

class TestAgentRegistry:
    def test_all_agents_registered(self):
        from app.services.agents.base import get_all_agents
        agents = get_all_agents()
        agent_types = {a.agent_type for a in agents}
        assert AgentType.QUALIFIER in agent_types
        assert AgentType.SCHEDULER in agent_types
        assert AgentType.FOLLOW_UP in agent_types

    def test_priority_order(self):
        agents = get_priority_agents()
        types = [a.agent_type for a in agents]
        # FollowUp > Scheduler > Qualifier
        assert types.index(AgentType.FOLLOW_UP) < types.index(AgentType.QUALIFIER)
        assert types.index(AgentType.SCHEDULER) < types.index(AgentType.QUALIFIER)


# ── build_context helper ──────────────────────────────────────────────────────

class TestBuildContext:
    def test_build_context_from_lead_stub(self):
        lead = MagicMock()
        lead.id = 42
        lead.name = "María González"
        lead.phone = "+56987654321"
        lead.email = "maria@example.com"
        lead.lead_metadata = {
            "pipeline_stage": "perfilamiento",
            "conversation_state": {"state": "DATA_COLLECTION"},
            "location": "Ñuñoa",
        }

        ctx = build_context(lead, broker_id=5)

        assert ctx.lead_id == 42
        assert ctx.broker_id == 5
        assert ctx.pipeline_stage == "perfilamiento"
        assert ctx.conversation_state == "DATA_COLLECTION"
        assert ctx.lead_data["name"] == "María González"
        assert ctx.lead_data["location"] == "Ñuñoa"
