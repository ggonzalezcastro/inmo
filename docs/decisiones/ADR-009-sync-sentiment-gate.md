# ADR-009: Sentiment gate sincrónico antes de respuesta AI

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

Cuando un lead expresa frustración, enojo, o distress financiero (e.g., "estoy desesperado", "esto es una scam", "no puedo pagar más"), el sistema debe escalar inmediatamente a un agente humano o aplicar protocolos de contención. No puede esperar una vuelta completa del LLM para descubrir que el mensaje era negativo.

El análisis de sentiment no puede ser asíncrono (publicado a Celery) porque la respuesta de escalamiento necesita ocurrir ANTES de que la AI responda normalmente. Un turno de delay en escalar puede significar perder al lead.

## Decisión

Ejecutar análisis de sentiment sincrónico en el orquestador antes de invocar el LLM. Implementación:

1. Mensaje recibido del lead
2. Regex pattern matching rápido para detectar:
   - Keywords de distress financiero
   - Sentimiento negativo obvio
   - Flags de urgencia
3. Si sentiment gate dispara:
   - Immediately marcar lead con flag de escalation
   - Enviar notificación WebSocket a agentes
   - Generar respuesta de contención predefinida
   - Skip LLM call normal
4. Si gate no dispara:
   - Continuar con flujo normal de LLM

El gate es regex-based (no LLM) para garantizar:
- Latencia mínima (<10ms)
- Determinismo
- No depende de disponibilidad de LLM

## Consecuencias

**Pros:**
- Escalamiento inmediato: cero delay entre mensaje negativo y acción
2. No hay gap de un-turno: contención sucede antes de respuesta AI normal
- Confiabilidad: regex no falla por issues de LLM provider
- Latencia controlada: gate es rápido, no bloquea flujo principal
- Costo cero: no usa tokens de LLM
- Testabilidad: patterns de regex son fáciles de verificar

**Contras:**
- Falsos positivos: keywords pueden coincidir en contextos no problemáticos
- Falsos negativos: sentiment sutil puede no activar regex
- Mantenimiento de patterns: regex necesita actualizado manualmente
- No entiende contexto: "estoy desesperado por encontrar casa" es diferente de "estoy desesperado financiero"
- Solo detecta negatif muy obvio: no hay análisis fino de sentiment
- Rough granularity: solo binario (escalate o no), no niveles de urgencia
