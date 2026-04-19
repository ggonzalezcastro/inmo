# ADR-003: Multi-agent Supervisor pattern

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

El sistema debe manejar diferentes comportamientos para distintas fases de la conversación con leads de real estate. Un solo agente monolítico tendría que manejar: calificación de presupuesto, búsqueda de propiedades, agendamiento de visitas, y seguimiento post-visita. Mezclar toda esta lógica resulta en código difícil de mantener, testear y extender.

Se necesita una arquitectura que permita a diferentes especialistas manejar diferentes aspectos de la conversación, pero manteniendo contexto compartido y transiciones fluidas entre agentes.

## Decisión

Implementar el patrón Supervisor con cuatro agentes especialistas:

- **QualifierAgent**: Maneja las etapas de entrada y perfilamiento. Recopila información del lead: presupuesto, ubicación deseada, tipo de propiedad, timeline de compra.

- **PropertyAgent**: Maneja búsqueda de propiedades. Se activa cuando el lead muestra intención de buscar propiedades específicas.

- **SchedulerAgent**: Maneja agendamiento de visitas. Activo en la etapa de calificación financiera, coordina con Google Calendar y servicios de voz (VAPI).

- **FollowUpAgent**: Maneja seguimiento post-visita y referidos. Activo en etapas de agendado, seguimiento y referidos.

El `AgentSupervisor` dirige el flujo:
1. Usa tabla `_STAGE_TO_AGENT` para enrutamiento inicial determinístico basado en etapa del lead
2. Mantiene `current_agent` sticky para no cambiar agente prematuramente
3. Recibe `HandoffSignal` cuando un agente determina que otro debe tomar el control
4. Transfiere contexto immutable (`AgentContext`) entre agentes

## Consecuencias

**Pros:**
- Separación de concerns clara: cada agente tiene responsabilidad única y código cohesivo
- Mantenibilidad: cambios en lógica de calificación no afectan lógica de agendamiento
- Testabilidad: cada agente puede ser probado aisladamente con mocks apropiados
- Extensibilidad: nuevo agente (e.g., NegotiatorAgent) puede ser agregado sin modificar existentes
- Código más pequeño por agente facilita code reviews y debugging
- Posibilidad de asignar agentes especializados a humanos para fallback

**Contras:**
- Complejidad arquitectónica mayor: más archivos, más interacciones, más conceptos
- Transferencia de contexto entre agentes puede perder información sutil
- Overhead de comunicación entre componentes
- Curva de aprendizaje para nuevos desarrolladores
- Debugging distribuidos: tracing de issues puede requerir seguir trail entre agentes
- Posible inconsistencia si dos agentes tienen expectativas diferentes sobre el estado
