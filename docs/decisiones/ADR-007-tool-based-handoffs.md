# ADR-007: Handoffs basados en tools sobre keyword matching

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

Los agentes necesitan transferirse el control de forma confiable. La aproximación anterior usaba keyword matching: si el mensaje contenía "comprar", "casa", o "departamento", se asumía intención de búsqueda de propiedades. Este enfoque era frágil: sinónimos, errores de ortografía, y contexto no capturado causaban transfers incorrectas.

El problema era que keywords son un proxy pobre para intención. Un lead que dice "estoy vendiendo mi casa" no quiere comprar, y uno que dice "presupuesto 50 millones" está en proceso de calificación, no de búsqueda.

## Decisión

Implementar tool-based handoffs donde el LLM decide cuando transferir usando function calling. Cada agente define `_HANDOFF_TOOLS` con tools como `handoff_to_scheduler`, `handoff_to_property_agent`, etc.

Funcionamiento:
1. Agente actual tiene tools de handoff disponibles en su context
2. LLM analiza mensaje y decide si transferencia es apropiada
3. Si sí, llama tool `handoff_to_X` con parámetros de contexto
4. Tool executor captura intent en `_handoff_intent` dict
5. Se construye `HandoffSignal` con contexto actualizado
6. Supervisor transfiere a agente destino con AgentContext

`tool_mode_override` controla comportamiento:
- `"ANY"`: Fuerza function calling (agentes con acciones mandatorias)
- `"AUTO"`: LLM decide (agentes con handoff opcional)

## Consecuencias

**Pros:**
- Entendimiento semántico: LLM entiende contexto, no solo palabras
- Transferencias más precisas: basadas en intención, no en keywords
- Robusto a variaciones de lenguaje: sinónimos, errores, contexto
- Extensible: nuevo handoff tool puede ser agregado fácilmente
- Fallback graceful: si tool calling falla, permanece en agente actual
- Decision rationale disponible: tool call incluye reason del LLM

**Contras:**
- Requiere soporte de function calling en LLM (todos los providers modernos lo soportan)
- Latencia adicional: LLM procesa para decidir (generalmente mínimo)
- Complejidad en tool definitions: cada handoff tool necesita schema claro
- Possible over-transfer: LLM puede transferir prematuramente
- Testing más complejo: hay que simular decisiones de LLM
- Debugging harder: decisión de handoff no es determinística pura
