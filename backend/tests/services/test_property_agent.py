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
        """Non-property message → conversational response via LLM passthrough, then handoff."""
        agent = PropertyAgent()
        ctx = _ctx()
        db = AsyncMock()

        with patch(
            "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
            new_callable=AsyncMock,
            return_value=("Hola, soy Sofía. ¿En qué puedo ayudarte?", []),
        ):
            response = await agent.process("Hola", ctx, db)

        assert response.message == "Hola, soy Sofía. ¿En qué puedo ayudarte?"
        assert response.agent_type == AgentType.PROPERTY
        # Non-property message triggers handoff to Qualifier
        assert response.handoff is not None
        assert response.handoff.target_agent == AgentType.QUALIFIER

    @pytest.mark.asyncio
    async def test_executes_property_search_tool(self):
        """Message requesting property → tool called → results formatted."""
        agent = PropertyAgent()
        ctx = _ctx(pipeline_stage="calificacion_financiera",
                   lead_data={"broker_name": "Test", "agent_name": "Sofía",
                              "location": "Las Condes", "budget": "5000 UF"})
        db = AsyncMock()

        mock_results = [
            {"name": "Edificio Sol", "commune": "Las Condes", "price_uf": 4800,
             "bedrooms": 2, "bathrooms": 1, "area_m2": 65, "property_type": "departamento",
             "description": "Vista al parque"},
        ]

        with patch(
            "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
            new_callable=AsyncMock,
            return_value=("Encontré 1 propiedad en Las Condes.", []),
        ), patch(
            "app.services.agents.property.execute_property_search",
            new_callable=AsyncMock,
            return_value=mock_results,
        ), patch(
            "app.services.observability.event_logger.event_logger.log_property_search",
            new_callable=AsyncMock,
        ), patch(
            "app.services.observability.event_logger.event_logger.log_tool_call",
            new_callable=AsyncMock,
        ):
            response = await agent.process(
                "Quiero ver departamentos en Las Condes hasta 5000 UF", ctx, db
            )

        assert response.agent_type == AgentType.PROPERTY
        assert response.message == "Encontré 1 propiedad en Las Condes."

    @pytest.mark.asyncio
    async def test_handoff_when_lead_wants_to_book(self):
        """should_handoff returns response.handoff — HandoffSignal to Scheduler when set."""
        agent = PropertyAgent()
        ctx = _ctx(pipeline_stage="calificacion_financiera")

        scheduler_handoff = HandoffSignal(
            target_agent=AgentType.SCHEDULER,
            reason="Lead wants to visit a specific property",
        )
        from app.services.agents.types import AgentResponse
        mock_response = AgentResponse(
            message="¡Perfecto! Te agendo una visita.",
            agent_type=AgentType.PROPERTY,
            handoff=scheduler_handoff,
        )

        handoff = await agent.should_handoff(mock_response, ctx)

        assert handoff is not None
        assert handoff.target_agent == AgentType.SCHEDULER

    @pytest.mark.asyncio
    async def test_no_handoff_by_default(self):
        """Normal property browsing (no schedule intent) → no handoff."""
        agent = PropertyAgent()
        ctx = _ctx()

        from app.services.agents.types import AgentResponse
        mock_response = AgentResponse(
            message="Aquí hay departamentos disponibles.",
            agent_type=AgentType.PROPERTY,
            handoff=None,
        )

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
