# ADR-008: Gemini Context Caching para optimización de prompts

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

Cada broker tiene un system prompt grande que incluye: instrucciones de persona (Sofía), few-shot examples de conversaciones, reglas DICOM, y contexto de la empresa. Este prompt está compuesto fresh en cada request, representando tokens y costo innecesarios ya que la porción estática (todo excepto el mensaje del lead y conversación reciente) no cambia entre requests.

Para un broker con 50 conversaciones activas, el mismo prompt de 2000 tokens se reconstruye 50 veces por minuto sin necesidad.

## Decisión

Usar Gemini Context Cache para guardar la porción estática del prompt por broker. Implementación en `app/services/llm/prompt_cache.py`:

- Static portion: system prompt completo, few-shot examples, DICOM rules
- Dynamic portion: conversación reciente (últimos N mensajes), mensaje actual
- Cache se crea/actualiza cuando config de broker cambia
- Request usa cache reference + dynamic content
- Cache invalidation cuando: broker actualiza su config, o TTL expira

La separación se hace en `LLMServiceFacade.build_llm_prompt()` que:
1. Identifica porción estática del prompt
2. Verifica si cache existe y es válido
3. Combina cached static + dynamic en request

## Consecuencias

**Pros:**
- Respuestas más rápidas: menos tokens a procesar por request
- Costos reducidos: caching cobra menos que tokens normales
- Consistencia de prompt: misma porción estática garantiza comportamiento uniforme
- Buenos niveles de cache hit: porción estática es 80-90% del total de tokens
- No afecta calidad: misma información, solo más eficiente

**Contras:**
- Complejidad de cache invalidation: saber cuando regenerar cache
- TTL management: cache puede quedar stale si no se refresca apropiadamente
- Latencia inicial: primer request de cada broker tiene overhead de crear cache
- Storage costs: caches tienen costo de almacenamiento además de uso
- Debugging harder: diferencias entre cached y non-cached requests
- Límites de provider: Gemini tiene límites en tamaño de cache y número de caches activas
