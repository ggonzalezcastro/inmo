# ADR-002: Gemini as primary LLM with Claude/OpenAI fallback

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

El sistema requiere un LLM confiable para producción que maneje clasificación de leads, generación de respuestas, y decisiones de agente. La disponibilidad y costo son críticos, ya que el sistema procesa conversaciones en tiempo real con clientes de real estate.

Se necesita un mecanismo de failover automático porque los servicios de LLM pueden tener interrupciones, y un solo proveedor sería un single point of failure.

## Decisión

Implementar `LLMServiceFacade` con el patrón Router que usa Gemini como proveedor primario, con circuit breaker y reintentos automáticos hacia Claude (Opus/Sonnet), y finalmente OpenAI (GPT-4o) como último recurso.

La cadena de fallback funciona así:
1. Intentar Gemini con reintentos configurables (3 intentos, exponential backoff)
2. Si Gemini falla después de reintentos o retorna error de circuit breaker, intentar Claude
3. Si Claude también falla, intentar OpenAI
4. Si todos fallan, retornar error estructurado

El circuit breaker previene llamadas repetidas a proveedores con outages.

## Consecuencias

**Pros:**
- Costo efectivo: Gemini tiene precios competitivos para la calidad ofrecida
- Calidad suficiente: El rendimiento de Gemini es comparable a otros proveedores para tareas de clasificación y generación
- Failover automático: Sin intervención manual cuando un proveedor tiene problemas
- Resiliencia probada: Circuit breaker evita cascadas de errores
- Latencia optimizada: Proveedor primario es generalmente el más rápido

**Contras:**
- Latencia adicional cuando ocurre fallback (puede agregar 1-3 segundos)
- Diferencias sutiles en outputs entre proveedores pueden afectar consistencia
- Complejidad en testing: Hay que verificar comportamiento con todos los proveedores
- Costos de monitoreo: Necesidad de trackear costos por proveedor
- Coordenación de features: No todas las features están disponibles en todos los proveedores (e.g., function calling)
