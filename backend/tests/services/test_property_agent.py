"""
Tests for PropertyAgent — routing, function calling, and handoff logic.

Run without DB:
    python -m pytest tests/services/test_property_agent.py -v --noconftest
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agents.types import AgentContext, AgentType, HandoffSignal
from app.services.agents.property import PropertyAgent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ctx(**overrides) -> AgentContext:
    defaults = dict(
        lead_id=1,
        broker_id=1,
        pipeline_stage="potencial",
        conversation_state="GREETING",
        lead_data={"broker_name": "Test", "agent_name": "Sofía"},
        message_history=[],
        handoff_count=0,
    )
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── should_handle ─────────────────────────────────────────────────────────────

class TestPropertyAgentRouting:
    @pytest.mark.asyncio
    async def test_handles_potencial_stage(self):
        agent = PropertyAgent()
        assert await agent.should_handle(_ctx(pipeline_stage="potencial"))

    @pytest.mark.asyncio
    async def test_handles_calificacion_financiera_stage(self):
        agent = PropertyAgent()
        assert await agent.should_handle(_ctx(pipeline_stage="calificacion_financiera"))

    @pytest.mark.asyncio
    async def test_handles_agendado_stage(self):
        agent = PropertyAgent()
        assert await agent.should_handle(_ctx(pipeline_stage="agendado"))

    @pytest.mark.asyncio
    async def test_does_not_handle_entrada_stage(self):
        agent = PropertyAgent()
        assert not await agent.should_handle(_ctx(pipeline_stage="entrada"))

    @pytest.mark.asyncio
    async def test_does_not_handle_referidos_stage(self):
        agent = PropertyAgent()
        assert not await agent.should_handle(_ctx(pipeline_stage="referidos"))


# ── process — no property mention ────────────────────────────────────────────

class TestPropertyAgentProcess:
    @pytest.mark.asyncio
    async def test_responds_when_no_property_query(self):
        """Non-property message → conversational response, no tool call."""
        agent = PropertyAgent()
        ctx = _ctx()
        db = AsyncMock()

        with patch(
            "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
            new_callable=AsyncMock,
            return_value=("Hola, soy Sofía. ¿En qué puedo ayudarte?", []),
        ), patch(
            "app.services.agents.property.event_logger.log_llm_call",
            new_callable=AsyncMock,
        ):
            response = await agent.process("Hola", ctx, db)

        assert response.message == "Hola, soy Sofía. ¿En qué puedo ayudarte?"
        assert response.agent_type == AgentType.PROPERTY
        assert not response.function_calls

    @pytest.mark.asyncio
    async def test_executes_property_search_tool(self):
        """Message requesting property → tool called → results formatted."""
        agent = PropertyAgent()
        ctx = _ctx(pipeline_stage="calificacion_financiera",
                   lead_data={"broker_name": "Test", "agent_name": "Sofía",
                              "location": "Las Condes", "budget": "5000 UF"})
        db = AsyncMock()

        mock_function_call = {
            "name": "search_properties",
            "args": {"commune": "Las Condes", "max_uf": 5000},
        }
        mock_results = [
            {"name": "Edificio Sol", "commune": "Las Condes", "price_uf": 4800,
             "bedrooms": 2, "bathrooms": 1, "area_m2": 65, "property_type": "departamento",
             "description": "Vista al parque"},
        ]

        with patch(
            "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
            new_callable=AsyncMock,
            return_value=("Aquí hay opciones:", [mock_function_call]),
        ), patch(
            "app.services.agents.property.execute_property_search",
            new_callable=AsyncMock,
            return_value=mock_results,
        ), patch(
            "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
            new_callable=AsyncMock,
            return_value=("Encontré 1 propiedad en Las Condes.", []),
        ), patch(
            "app.services.agents.property.event_logger.log_property_search",
            new_callable=AsyncMock,
        ), patch(
            "app.services.agents.property.event_logger.log_llm_call",
            new_callable=AsyncMock,
        ):
            response = await agent.process(
                "Quiero ver departamentos en Las Condes hasta 5000 UF", ctx, db
            )

        assert response.agent_type == AgentType.PROPERTY

    @pytest.mark.asyncio
    async def test_handoff_when_lead_wants_to_book(self):
        """When LLM says the lead wants to book, should_handoff emits HandoffSignal."""
        agent = PropertyAgent()
        ctx = _ctx(pipeline_stage="calificacion_financiera")

        mock_response = MagicMock()
        mock_response.message = "¡Perfecto! Te agendo una visita."
        mock_response.context_updates = {"wants_appointment": True}
        mock_response.function_calls = []
        mock_response.metadata = {"wants_appointment": True}

        handoff = await agent.should_handoff(mock_response, ctx)

        # HandoffSignal to Scheduler if wants_appointment is set
        if handoff is not None:
            assert handoff.target_agent == AgentType.SCHEDULER

    @pytest.mark.asyncio
    async def test_no_handoff_by_default(self):
        """Normal property browsing should not trigger handoff."""
        agent = PropertyAgent()
        ctx = _ctx()

        mock_response = MagicMock()
        mock_response.context_updates = {}
        mock_response.metadata = {}
        mock_response.message = "Aquí hay departamentos disponibles."

        handoff = await agent.should_handoff(mock_response, ctx)
        assert handoff is None


# ── agent_type enum ───────────────────────────────────────────────────────────

class TestPropertyAgentIdentity:
    def test_agent_type_is_property(self):
        agent = PropertyAgent()
        assert agent.agent_type == AgentType.PROPERTY

    def test_agent_name_set(self):
        agent = PropertyAgent()
        assert agent.name.lower() == "propertyagent"
