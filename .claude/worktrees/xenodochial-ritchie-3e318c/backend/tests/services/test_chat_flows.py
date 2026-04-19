"""
Tests de flujos de chat — cobertura de escenarios de conversación.

Cada clase representa un escenario con una INTENCIÓN clara.
Cada test valida si esa intención se cumple.

Ejecutar sin DB:
    python -m pytest tests/services/test_chat_flows.py -v --noconftest

Salida esperada:
    PASSED  → intención cumplida
    FAILED  → intención NO cumplida (el mensaje de error explica por qué)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)
from app.services.agents.qualifier import QualifierAgent
from app.services.agents.property import PropertyAgent, _is_property_intent
from app.services.agents.scheduler import SchedulerAgent
from app.services.agents.supervisor import AgentSupervisor


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ctx(**overrides) -> AgentContext:
    """Base context: lead nuevo, sin datos, etapa entrada."""
    defaults = dict(
        lead_id=1,
        broker_id=1,
        pipeline_stage="entrada",
        conversation_state="GREETING",
        lead_data={"broker_name": "Inmobiliaria Test", "agent_name": "Sofía"},
        message_history=[],
        current_agent=None,
        handoff_count=0,
        current_frustration=0.0,
    )
    defaults.update(overrides)
    return AgentContext(**defaults)


def _qualified_ctx(**overrides) -> AgentContext:
    """Context con todos los campos de calificación completos y DICOM limpio."""
    data = {
        "broker_name": "Inmobiliaria Test",
        "agent_name": "Sofía",
        "name": "Gabriel González",
        "phone": "+56912345678",
        "email": "gabriel@test.com",
        "salary": "2000000",
        "location": "Las Condes",
        "dicom_status": "clean",
    }
    kwargs = dict(
        pipeline_stage="calificacion_financiera",
        conversation_state="FINANCIAL_QUAL",
        lead_data=data,
    )
    kwargs.update(overrides)
    return _ctx(**kwargs)


def _llm_qualify(extracted: dict):
    """Mock de analyze_lead_qualification que retorna los campos dados."""
    return AsyncMock(return_value=extracted)


def _llm_respond(text: str):
    """Mock de generate_response_with_function_calling que retorna texto dado."""
    return AsyncMock(return_value=(text, []))


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 1 — Flujo feliz: calificación completa de principio a fin
# ══════════════════════════════════════════════════════════════════════════════

class TestFlujoFeliz:
    """
    ESCENARIO: Lead nuevo sigue el flujo normal de calificación.
    El agente recopila nombre → contacto → datos financieros → handoff al Scheduler.
    """

    @pytest.mark.asyncio
    async def test_lead_nuevo_es_atendido_por_qualifier(self):
        """
        INTENCIÓN: Un lead que saluda sin datos debe ser atendido por el QualifierAgent.
        """
        ctx = _ctx()
        agent = QualifierAgent()
        resultado = await agent.should_handle(ctx)

        assert resultado, (
            "QualifierAgent debería manejar leads nuevos sin datos, pero retornó False"
        )

    @pytest.mark.asyncio
    async def test_qualifier_pide_nombre_primero(self):
        """
        INTENCIÓN: Si el lead aún no tiene nombre, el agente pide el nombre (no teléfono ni email).
        """
        ctx = _ctx()
        db = MagicMock()
        respuesta_llm = "¡Hola! Soy Sofía de Inmobiliaria Test. ¿Cuál es tu nombre completo?"

        with (
            patch(
                "app.services.llm.facade.LLMServiceFacade.analyze_lead_qualification",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
                new=AsyncMock(return_value=(respuesta_llm, [])),
            ),
        ):
            response = await QualifierAgent().process("hola", ctx, db)

        assert "nombre" in response.message.lower() or "llamas" in response.message.lower(), (
            f"Se esperaba que pidiera el nombre, pero respondió: {response.message!r}"
        )
        assert response.handoff is None, (
            "No debe haber handoff cuando el lead aún no tiene nombre"
        )

    @pytest.mark.asyncio
    async def test_qualifier_hace_handoff_cuando_lead_esta_calificado(self):
        """
        INTENCIÓN: Cuando el lead tiene todos los datos + DICOM limpio,
        QualifierAgent emite HandoffSignal hacia el SchedulerAgent.
        """
        ctx = _qualified_ctx()
        db = MagicMock()
        all_fields = {
            "name": "Gabriel González",
            "phone": "+56912345678",
            "email": "gabriel@test.com",
            "salary": "2000000",
            "location": "Las Condes",
            "dicom_status": "clean",
        }

        with (
            patch(
                "app.services.llm.facade.LLMServiceFacade.analyze_lead_qualification",
                new_callable=AsyncMock,
                return_value=all_fields,
            ),
            patch(
                "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
                new_callable=AsyncMock,
                return_value=("¡Excelente! Con tus datos podemos avanzar.", []),
            ),
        ):
            response = await QualifierAgent().process("mi renta es 2 millones", ctx, db)

        assert response.handoff is not None, (
            "Debería emitir handoff al Scheduler, pero no lo hizo"
        )
        assert response.handoff.target_agent == AgentType.SCHEDULER, (
            f"Handoff debe ir al Scheduler, pero va a {response.handoff.target_agent}"
        )

    @pytest.mark.asyncio
    async def test_supervisor_enruta_lead_calificado_al_scheduler(self):
        """
        INTENCIÓN: El supervisor enruta mensajes de agendamiento a SchedulerAgent
        cuando el lead está calificado.
        """
        ctx = _qualified_ctx(
            conversation_state="SCHEDULING",
            current_agent=AgentType.SCHEDULER,
        )
        db = MagicMock()
        scheduler_response = AgentResponse(
            message="¿Te acomoda el sábado a las 10:00?",
            agent_type=AgentType.SCHEDULER,
        )

        with patch.object(SchedulerAgent, "process", new_callable=AsyncMock, return_value=scheduler_response):
            result = await AgentSupervisor.process("sí, me acomoda el sábado para la visita", ctx, db)

        assert result.agent_type == AgentType.SCHEDULER, (
            f"Lead calificado con state=SCHEDULING debe ir al Scheduler, "
            f"pero fue a {result.agent_type}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 2 — Búsqueda de propiedades
# ══════════════════════════════════════════════════════════════════════════════

class TestFlujoPropiedades:
    """
    ESCENARIO: Lead pregunta por propiedades.
    PropertyAgent debe manejar la búsqueda y mantener el contexto (sticky routing).
    """

    @pytest.mark.asyncio
    async def test_mensaje_con_keyword_de_propiedad_activa_property_agent(self):
        """
        INTENCIÓN: Un mensaje con keywords de propiedad ("departamentos", "m2", "tienes algo")
        debe ser manejado por PropertyAgent, no por QualifierAgent.
        """
        ctx = _ctx(current_message="busco departamentos de más de 70 m2 en Maipú")
        agent = PropertyAgent()

        resultado = await agent.should_handle(ctx)

        assert resultado, (
            "PropertyAgent debería manejar mensajes con keywords de propiedad"
        )

    @pytest.mark.asyncio
    async def test_keywords_m2_y_metros_activan_property_agent(self):
        """
        INTENCIÓN: Las keywords 'm2' y 'metros' deben activar PropertyAgent
        para mensajes como 'tienes algo de más de 70 m2?'.
        """
        mensajes_con_intent = [
            "tienes algo de más de 70 m2?",
            "busco de mínimo 80 metros",
            "quiero algo con más m2",
            "tienes algo más grande?",
            "tienes en Ñuñoa?",
            "otras opciones?",
        ]
        for msg in mensajes_con_intent:
            assert _is_property_intent(msg), (
                f"Se esperaba que '{msg}' detectara intent de propiedad, pero no lo hizo"
            )

    @pytest.mark.asyncio
    async def test_sticky_routing_property_agent_no_necesita_keywords(self):
        """
        INTENCIÓN: Si PropertyAgent ya es el agente activo (sticky), debe manejar
        el mensaje aunque no tenga keywords explícitos de propiedad.
        """
        ctx = _ctx(current_agent=AgentType.PROPERTY)
        agent = PropertyAgent()

        resultado = await agent.should_handle(ctx)

        assert resultado, (
            "PropertyAgent sticky debe manejar el mensaje aunque no tenga keywords"
        )

    @pytest.mark.asyncio
    async def test_property_agent_sticky_no_hace_passthrough(self):
        """
        INTENCIÓN: Cuando PropertyAgent es el agente activo, no debe hacer passthrough
        ni dar el mensaje de fallback 'Un agente estará contigo pronto'.
        """
        ctx = _ctx(current_agent=AgentType.PROPERTY)
        db = MagicMock()
        respuesta_busqueda = "Encontré 2 propiedades en Ñuñoa con esas características."

        with (
            patch(
                "app.services.agents.property.execute_property_search",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
                new=AsyncMock(return_value=(respuesta_busqueda, [])),
            ),
            patch(
                "app.services.observability.event_logger.event_logger.log_property_search",
                new=AsyncMock(),
            ),
            patch(
                "app.services.observability.event_logger.event_logger.log_tool_call",
                new=AsyncMock(),
            ),
        ):
            response = await PropertyAgent().process("tienes algo más grande?", ctx, db)

        assert "agente estará contigo" not in response.message, (
            "PropertyAgent sticky no debe dar el mensaje de fallback del passthrough"
        )
        assert response.handoff is None or response.handoff.target_agent != AgentType.QUALIFIER, (
            "PropertyAgent sticky no debe hacer handoff a Qualifier por falta de keywords"
        )

    @pytest.mark.asyncio
    async def test_pregunta_financiera_pasa_al_qualifier_aunque_sea_sticky(self):
        """
        INTENCIÓN: Aunque PropertyAgent sea el agente activo (sticky),
        si el lead hace una pregunta financiera ("cuánto pie tengo que dar?"),
        debe pasarse al QualifierAgent, no intentar responderla PropertyAgent.
        """
        ctx = _ctx(current_agent=AgentType.PROPERTY)  # sticky
        db = MagicMock()

        with (
            patch(
                "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
                new=AsyncMock(return_value=("Esa info la maneja el equipo.", [])),
            ),
            patch(
                "app.services.observability.event_logger.event_logger.log_property_search",
                new=AsyncMock(),
            ),
            patch(
                "app.services.observability.event_logger.event_logger.log_tool_call",
                new=AsyncMock(),
            ),
        ):
            response = await PropertyAgent().process(
                "si me gusta la casa, cuánto pie tengo que dar?", ctx, db
            )

        assert response.handoff is not None, (
            "Una pregunta de pie/financiamiento debe hacer passthrough al Qualifier "
            "incluso cuando PropertyAgent es sticky"
        )
        assert response.handoff.target_agent == AgentType.QUALIFIER

    @pytest.mark.asyncio
    async def test_followup_zona_sticky_no_hace_passthrough(self):
        """
        INTENCIÓN: Un mensaje de refinamiento de búsqueda ("y en Ñuñoa?" sin keywords)
        siendo sticky debe ser procesado por PropertyAgent (no passthrough).
        Esta es la mejora de sticky routing que mantiene el contexto de búsqueda.
        """
        ctx = _ctx(current_agent=AgentType.PROPERTY)
        db = MagicMock()

        with (
            patch(
                "app.services.agents.property.execute_property_search",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
                new=AsyncMock(return_value=("No encontré propiedades en Ñuñoa con esas características.", [])),
            ),
            patch(
                "app.services.observability.event_logger.event_logger.log_property_search",
                new=AsyncMock(),
            ),
            patch(
                "app.services.observability.event_logger.event_logger.log_tool_call",
                new=AsyncMock(),
            ),
        ):
            response = await PropertyAgent().process("y en Ñuñoa?", ctx, db)

        # No debe hacer passthrough a Qualifier — es una búsqueda de seguimiento
        assert response.handoff is None or response.handoff.target_agent != AgentType.QUALIFIER, (
            "Un follow-up de zona ('y en Ñuñoa?') siendo sticky no debe pasarse al Qualifier"
        )

    @pytest.mark.asyncio
    async def test_property_agent_no_ofrece_agendar_visita(self):
        """
        INTENCIÓN: El PropertyAgent NO debe ofrecer agendar visitas — eso es del Scheduler.
        El prompt del agente debe prohibirlo explícitamente.
        """
        from app.services.agents.property import PropertyAgent
        ctx = _ctx()
        agent = PropertyAgent()
        prompt = agent.get_system_prompt(ctx)

        assert "NO ofrezcas agendar" in prompt or "no.*agendar" in prompt.lower(), (
            "El prompt del PropertyAgent debe prohibir explícitamente ofrecer agendar visitas"
        )

    @pytest.mark.asyncio
    async def test_property_agent_no_pregunta_datos_de_calificacion(self):
        """
        INTENCIÓN: El PropertyAgent NO debe preguntar presupuesto, renta ni DICOM.
        Esos datos los recopila el QualifierAgent.
        """
        ctx = _ctx()
        agent = PropertyAgent()
        prompt = agent.get_system_prompt(ctx)

        assert "NO preguntes sobre presupuesto" in prompt or "NO.*calificaci" in prompt, (
            "El prompt del PropertyAgent debe prohibir preguntar datos de calificación"
        )

    @pytest.mark.asyncio
    async def test_mensaje_de_telefono_activa_passthrough_al_qualifier(self):
        """
        INTENCIÓN: Cuando PropertyAgent recibe un mensaje de datos personales
        (no relacionado con propiedades) y NO es sticky, debe pasarlo al QualifierAgent.
        """
        ctx = _ctx(current_agent=AgentType.QUALIFIER)  # viene del Qualifier, no sticky
        db = MagicMock()

        with (
            patch(
                "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
                new=AsyncMock(return_value=("Anotado, gracias.", [])),
            ),
            patch(
                "app.services.observability.event_logger.event_logger.log_property_search",
                new=AsyncMock(),
            ),
            patch(
                "app.services.observability.event_logger.event_logger.log_tool_call",
                new=AsyncMock(),
            ),
        ):
            response = await PropertyAgent().process("mi teléfono es 912345678", ctx, db)

        assert response.handoff is not None, (
            "PropertyAgent no-sticky con mensaje sin keywords debe hacer handoff al Qualifier"
        )
        assert response.handoff.target_agent == AgentType.QUALIFIER


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 3 — Lead furioso / frustrado
# ══════════════════════════════════════════════════════════════════════════════

class TestFlujoFurioso:
    """
    ESCENARIO: El lead expresa frustración o enojo.
    El agente debe reconocer la emoción y no insistir en pedir datos.
    """

    @pytest.mark.asyncio
    async def test_lead_con_alta_frustracion_sigue_siendo_enrutado(self):
        """
        INTENCIÓN: Un lead furioso (frustration=1.0) sigue siendo atendido,
        no se bloquea ni genera excepción.
        """
        ctx = _ctx(current_frustration=1.0, tone_hint="empathetic")
        agent = QualifierAgent()

        resultado = await agent.should_handle(ctx)

        assert resultado, (
            "Un lead furioso debe seguir siendo atendido por el QualifierAgent"
        )

    @pytest.mark.asyncio
    async def test_supervisor_no_crashea_con_lead_furioso(self):
        """
        INTENCIÓN: El supervisor no lanza excepción con leads que tienen
        frustración máxima. Retorna respuesta válida.
        """
        ctx = _ctx(current_frustration=1.0, tone_hint="empathetic")
        db = MagicMock()
        respuesta_empatica = "Entiendo tu frustración. Déjame ayudarte lo antes posible."

        qualifier_response = AgentResponse(
            message=respuesta_empatica,
            agent_type=AgentType.QUALIFIER,
        )

        with patch.object(QualifierAgent, "process", new_callable=AsyncMock, return_value=qualifier_response):
            result = await AgentSupervisor.process("esto es un desastre, nadie me responde", ctx, db)

        assert result is not None
        assert result.message, "La respuesta a un lead furioso no debe estar vacía"

    @pytest.mark.asyncio
    async def test_lead_furioso_no_genera_handoff_al_scheduler(self):
        """
        INTENCIÓN: Un lead sin calificar que está furioso NO debe ir al Scheduler,
        aunque la palabra 'agendar' aparezca en el mensaje por frustración.
        """
        ctx = _ctx(current_frustration=1.0)
        db = MagicMock()
        respuesta = "Disculpa las molestias, con gusto te ayudo a encontrar lo que buscas."

        qualifier_response = AgentResponse(
            message=respuesta,
            agent_type=AgentType.QUALIFIER,
            handoff=None,
        )

        with patch.object(QualifierAgent, "process", new_callable=AsyncMock, return_value=qualifier_response):
            result = await AgentSupervisor.process(
                "ya quiero agendar algo, nadie me contesta", ctx, db
            )

        assert result.agent_type != AgentType.SCHEDULER, (
            "Lead no calificado no debe llegar al Scheduler aunque mencione 'agendar'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 4 — Regla DICOM (crítica)
# ══════════════════════════════════════════════════════════════════════════════

class TestReglaDICOM:
    """
    ESCENARIO: Lead con DICOM sucio.
    REGLA CRÍTICA: Nunca prometer crédito ni pre-aprobación a leads con DICOM sucio.
    """

    @pytest.mark.asyncio
    async def test_qualifier_no_hace_handoff_con_dicom_sucio(self):
        """
        INTENCIÓN: QualifierAgent NO debe hacer handoff al Scheduler si el DICOM
        del lead está sucio (has_debt / dirty), aunque tenga todos los demás datos.
        """
        ctx = _qualified_ctx()
        ctx = AgentContext(
            **{**ctx.__dict__, "lead_data": {**ctx.lead_data, "dicom_status": "dirty"}}
        )
        db = MagicMock()

        with (
            patch(
                "app.services.llm.facade.LLMServiceFacade.analyze_lead_qualification",
                new_callable=AsyncMock,
                return_value={"dicom_status": "dirty"},
            ),
            patch(
                "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
                new_callable=AsyncMock,
                return_value=("Para acceder al crédito necesitas DICOM limpio.", []),
            ),
        ):
            response = await QualifierAgent().process("tengo deudas morosas", ctx, db)

        assert response.handoff is None or response.handoff.target_agent != AgentType.SCHEDULER, (
            "¡VIOLACIÓN CRÍTICA! No se debe hacer handoff al Scheduler con DICOM sucio"
        )

    @pytest.mark.asyncio
    async def test_lead_con_dicom_sucio_no_esta_calificado(self):
        """
        INTENCIÓN: is_qualified() debe retornar False para leads con DICOM sucio,
        impidiendo avanzar en el flujo.
        """
        ctx = _qualified_ctx()
        lead_data_sucio = {**ctx.lead_data, "dicom_status": "dirty"}
        ctx_sucio = AgentContext(**{**ctx.__dict__, "lead_data": lead_data_sucio})

        assert not ctx_sucio.is_qualified(), (
            "Un lead con DICOM sucio NO debe estar calificado"
        )

    @pytest.mark.asyncio
    async def test_lead_con_dicom_limpio_si_esta_calificado(self):
        """
        INTENCIÓN: is_qualified() debe retornar True cuando DICOM está limpio
        y todos los demás datos están presentes.
        """
        ctx = _qualified_ctx()

        assert ctx.is_qualified(), (
            "Un lead con todos los datos y DICOM limpio DEBE estar calificado"
        )

    @pytest.mark.asyncio
    async def test_lead_con_dicom_desconocido_puede_calificar(self):
        """
        INTENCIÓN: Si no se conoce el DICOM ('unknown'), el lead puede avanzar
        (se le da el beneficio de la duda para no bloquear el flujo).
        """
        ctx = _qualified_ctx()
        lead_data_unknown = {**ctx.lead_data, "dicom_status": "unknown"}
        ctx_unknown = AgentContext(**{**ctx.__dict__, "lead_data": lead_data_unknown})

        assert ctx_unknown.is_qualified(), (
            "Un lead con DICOM desconocido DEBE poder calificar"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 5 — Routing edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TestRoutingEdgeCases:
    """
    ESCENARIO: Casos límite del sistema de enrutamiento.
    Verifica que cada tipo de mensaje va al agente correcto.
    """

    @pytest.mark.asyncio
    async def test_mensaje_generico_va_al_qualifier_por_defecto(self):
        """
        INTENCIÓN: Un mensaje sin keywords de propiedad ni de agendamiento
        debe ir al QualifierAgent (fallback por defecto).
        """
        ctx = _ctx()
        qualifier = QualifierAgent()
        property_agent = PropertyAgent()

        qualifier_handles = await qualifier.should_handle(ctx)
        property_handles = await property_agent.should_handle(
            AgentContext(**{**ctx.__dict__, "current_message": "hola buenas"})
        )

        assert qualifier_handles, "QualifierAgent debe manejar mensajes genéricos"
        assert not property_handles, "PropertyAgent no debe manejar 'hola buenas'"

    @pytest.mark.asyncio
    async def test_lead_sin_agente_asignado_va_al_qualifier(self):
        """
        INTENCIÓN: Si ningún agente fue asignado previamente (lead nuevo),
        el QualifierAgent debe tomar el control.
        """
        ctx = _ctx(current_agent=None)
        agent = QualifierAgent()

        assert await agent.should_handle(ctx), (
            "QualifierAgent debe manejar leads sin agente asignado"
        )

    @pytest.mark.asyncio
    async def test_calificacion_financiera_sin_scheduling_va_al_scheduler(self):
        """
        INTENCIÓN: Un lead en etapa calificacion_financiera debe ir al SchedulerAgent.
        """
        ctx = _qualified_ctx(
            current_agent=AgentType.SCHEDULER,
        )
        agent = SchedulerAgent()

        assert await agent.should_handle(ctx), (
            "SchedulerAgent debe manejar leads en etapa calificacion_financiera"
        )

    @pytest.mark.asyncio
    async def test_etapa_agendado_no_va_al_qualifier(self):
        """
        INTENCIÓN: Un lead en etapa 'agendado' NO debe ir al QualifierAgent
        (ya superó esa etapa).
        """
        ctx = _ctx(
            pipeline_stage="agendado",
            conversation_state="COMPLETED",
            current_agent=AgentType.FOLLOW_UP,  # ya tiene agente asignado post-visita
        )
        agent = QualifierAgent()

        assert not await agent.should_handle(ctx), (
            "QualifierAgent no debe manejar leads que ya agendaron visita"
        )

    @pytest.mark.asyncio
    async def test_property_agent_no_activa_en_etapa_entrada_sin_keywords(self):
        """
        INTENCIÓN: PropertyAgent en etapa 'entrada' sin keywords de propiedad
        y sin ser sticky NO debe activarse.
        """
        ctx = _ctx(
            pipeline_stage="entrada",
            current_agent=None,
            current_message="cuándo me llaman?",
        )
        agent = PropertyAgent()

        assert not await agent.should_handle(ctx), (
            "PropertyAgent no debe activarse para 'cuándo me llaman?' sin keywords"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 6 — Prevención de loops
# ══════════════════════════════════════════════════════════════════════════════

class TestPrevencionDeLoops:
    """
    ESCENARIO: El supervisor detecta y corta ciclos de handoffs entre agentes.
    """

    @pytest.mark.asyncio
    async def test_supervisor_corta_loop_property_qualifier(self):
        """
        INTENCIÓN: Si PropertyAgent hace handoff a Qualifier, y Qualifier intenta
        volver a PropertyAgent, el supervisor debe cortar el loop y retornar
        la última respuesta válida.
        """
        ctx = _ctx(current_message="busco propiedades en Maipú")
        db = MagicMock()

        property_response_with_handoff = AgentResponse(
            message="Aquí hay propiedades en Maipú.",
            agent_type=AgentType.PROPERTY,
            handoff=HandoffSignal(
                target_agent=AgentType.QUALIFIER,
                reason="Lead unqualified",
            ),
        )
        qualifier_response_with_handoff = AgentResponse(
            message="Para ayudarte mejor, ¿cuál es tu nombre?",
            agent_type=AgentType.QUALIFIER,
            handoff=HandoffSignal(
                target_agent=AgentType.PROPERTY,
                reason="Back to property",
            ),
        )

        with (
            patch.object(PropertyAgent, "process", new_callable=AsyncMock, return_value=property_response_with_handoff),
            patch.object(QualifierAgent, "process", new_callable=AsyncMock, return_value=qualifier_response_with_handoff),
        ):
            result = await AgentSupervisor.process("busco departamentos", ctx, db)

        assert result is not None, "El supervisor debe retornar resultado aunque haya loop"
        assert result.message, "La respuesta no debe estar vacía tras un loop"

    @pytest.mark.asyncio
    async def test_supervisor_respeta_limite_de_handoffs(self):
        """
        INTENCIÓN: El supervisor no debe procesar más de 3 handoffs consecutivos,
        evitando loops infinitos.
        """
        from app.services.agents.supervisor import _MAX_HANDOFFS
        assert _MAX_HANDOFFS <= 3, (
            f"_MAX_HANDOFFS={_MAX_HANDOFFS} es demasiado alto — riesgo de loops infinitos"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 7 — No re-saludo
# ══════════════════════════════════════════════════════════════════════════════

class TestNoReSaludo:
    """
    ESCENARIO: En conversaciones en curso, los agentes no deben re-saludar.
    """

    def test_qualifier_prompt_no_resaluda_cuando_hay_nombre(self):
        """
        INTENCIÓN: Cuando el lead ya tiene nombre (conversación en curso),
        el prompt del QualifierAgent debe incluir instrucción de NO re-saludar.
        """
        ctx = _ctx(lead_data={
            "broker_name": "Test",
            "agent_name": "Sofía",
            "name": "Gabriel",
        })
        agent = QualifierAgent()
        prompt = agent.get_system_prompt(ctx)

        assert "NO te presentes" in prompt or "conversación activa" in prompt, (
            "El prompt del Qualifier con nombre conocido debe prohibir el re-saludo"
        )

    def test_property_prompt_no_resaluda_siempre(self):
        """
        INTENCIÓN: El prompt del PropertyAgent siempre incluye instrucción
        de NO re-saludar (ya que solo se activa cuando hay interés en propiedades,
        que no es el primer mensaje).
        """
        ctx = _ctx()
        agent = PropertyAgent()
        prompt = agent.get_system_prompt(ctx)

        assert "NO te presentes" in prompt or "conversación activa" in prompt, (
            "El prompt del PropertyAgent debe prohibir el re-saludo"
        )

    def test_qualifier_prompt_si_puede_saludar_sin_nombre(self):
        """
        INTENCIÓN: Cuando el lead NO tiene nombre aún (primer turno),
        el QualifierAgent SÍ debe poder saludar.
        """
        ctx = _ctx()  # sin nombre
        agent = QualifierAgent()
        prompt = agent.get_system_prompt(ctx)

        # No debe tener la instrucción de "no re-saludar" en el primer turno
        assert "NO te presentes" not in prompt, (
            "En el primer turno (sin nombre), el Qualifier sí debe poder saludar"
        )
