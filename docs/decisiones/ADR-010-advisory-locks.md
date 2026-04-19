# ADR-010: PostgreSQL advisory locks para procesamiento concurrente de mensajes

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

En un sistema multi-tenant con procesamiento asíncrono, es posible recibir múltiples mensajes del mismo lead en paralelo: el lead envía por WhatsApp, Telegram, y la plataforma web simultáneamente, o bien mensajes quedan en queue y se procesan concurrentemente. Sin coordinación, dos workers podrían:
- Generar respuestas contradictorias
- Actualizar estado del lead de forma inconsistente
- Crear duplicación de appointments
- Perder mensajes o estados intermedios

El challenge es prevenir race conditions sin introducir latency significativa ni complejidad excesiva de distributed locking.

## Decisión

Usar PostgreSQL advisory locks (`pg_try_advisory_lock`) para serializar procesamiento de mensajes del mismo lead. Implementación:

1. Worker recibe mensaje para lead_id X
2. Intenta adquirir lock: `SELECT pg_try_advisory_lock(lead_id)`
3. Si lock adquirido:
   - Procesar mensaje normalmente
   - Liberar lock al terminar: `SELECT pg_advisory_unlock(lead_id)`
4. Si lock no adquirido (otro worker procesando):
   - Retry con backoff (hasta 3 intentos)
   - Si aún así no se adquiere, proceder sin lock (trade-off: aceptamos race window)
5. Lock key es el lead_id mismo, simplicando gestión

La tabla de lock usa `BIGINT` como key type, que acomoda lead IDs de cualquier tamaño.

## Consecuencias

**Pros:**
- Serializa procesamiento: mensajes del mismo lead se procesan en orden
- Previene data corruption: no más respuestas contradictorias o estados inconsistentes
- Utiliza PostgreSQL: no requiere infraestructura adicional (Redis distributed locks)
- No blocking total: si lock no disponible, retry y procede, no deadlock
- Simple de implementar: solo dos chamadas SQL (try y unlock)
- Transparente para aplicación: lógica de negocio no cambia, solo el wrapper

**Contras:**
- Bloqueo implícito: workers pueden quedar bloqueados esperando lock
- Retry overhead: cuando hay contención alta, latency puede aumentar
- No es true distributed lock: solo funciona intra-database, no cross-instance
- Posible starvation: si un worker fallaholding lock, otros esperan timeout
- Overhead de conexión: cada lock requiere transacción separada
- Contención extrema puede causar pile-up: muchos workers esperando mismo lock
