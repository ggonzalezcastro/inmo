# Bugs Conocidos y Tech Debt

> Última actualización: 2026-04-18

---

## Bugs de Severidad ALTA

### 1. WhatsApp campaign integration not implemented

**Archivo:** `backend/app/tasks/campaign_executor.py:233`

```python
# TODO: integrate WhatsApp service
log.status = CampaignLogStatus.SENT
log.response = {"channel": "whatsapp", "phone": phone, "message": message_text}
```

**Contexto:** El paso de campaña tipo `whatsapp` no envía mensajes real. Solo marca como `SENT` y loguea. El mensaje nunca llega al lead.

**Impacto:** Campañas que usan canal WhatsApp no funcionan. Los leads no reciben mensajes.

**Solución propuesta:** Implementar `WhatsAppService` y llamar API de WhatsApp Business Graph API.

---

## Bugs de Severidad MEDIA

### 2. Schedule_meeting action not implemented

**Archivo:** `backend/app/tasks/campaign_executor.py:265`

```python
async def _execute_schedule_meeting(db: AsyncSession, campaign, step, lead, log):
    """Schedule meeting — not yet implemented."""
    log.status = CampaignLogStatus.FAILED
    log.response = {"error": "schedule_meeting not yet implemented"}
    logger.warning("schedule_meeting action not yet implemented")
```

**Contexto:** La acción `schedule_meeting` en pasos de campaña falla permanentemente.

**Impacto:** No se pueden crear campañas que agenden reuniones automáticamente.

---

### 3. Advisory lock race condition

**Archivo:** `backend/app/services/chat/orchestrator.py:94-116`

```python
# G7: Acquire a session-level PostgreSQL advisory lock to serialize concurrent
# message processing for the same lead. Use pg_try_advisory_lock to avoid
# indefinite blocking when a prior request leaked the lock. If the lock can't
# be acquired after a few retries we proceed without it — better to risk a
# race than to hang the request forever.
```

**Contexto:** Si no se puede adquirir el lock después de 3 intentos, se continúa sin él.

**Impacto:** Bajo alta carga concurrente, múltiples mensajes del mismo lead podrían procesarse simultáneamente, causando estados inconsistentes.

---

### 4. Conversation debugger relies on task-based LLM call logging

**Archivo:** `backend/app/services/llm/call_logger.py`

**Contexto:** El conversation debugger en el frontend depende de que las llamadas LLM se logueen asíncronamente via `asyncio.ensure_future`. Si el proceso termina antes de que se complete el logging, ciertos eventos podrían perderse.

**Impacto:** El conversation debugger podría mostrar información incompleta en algunos casos.

---

## Bugs de Severidad BAJA

### 5. Type hint mismatch in GeminiProvider

**Archivo:** `backend/app/services/llm/providers/gemini_provider.py:178`

```python
# Signature declares -> Tuple[str, List[Dict[str, Any]]] (2-tuple)
# Implementation returns (text, function_calls, usage) (3-tuple)
```

**Contexto:** La función dice que retorna 2 valores pero retorna 3. La fachada maneja esto con `len(result) >= 3`.

**Impacto:** Confusión en IDEs, pero no causa errores funcionales.

**Solución propuesta:** Actualizar signature a `-> Tuple[str, List[Dict[str, Any]], Optional[Dict]]`

---

### 6. Redundant variable initialization in SchedulerAgent

**Archivo:** `backend/app/services/agents/scheduler.py:163`

```python
tools: list = list(_HANDOFF_TOOLS)  # immediately overwritten on line 178
```

**Contexto:** Variable declarada y reasignada sin uso intermedio.

**Impacto:** Legibilidad del código.

---

### 7. Missing tool_mode_override in SchedulerAgent LLM call

**Archivo:** `backend/app/services/agents/scheduler.py:203-211`

```python
# Missing explicit tool_mode_override="ANY" in LLM facade call
# Other agents (Qualifier, FollowUp) explicitly set "AUTO" for consistency
```

**Contexto:** Los otros agentes settean `tool_mode_override` explícitamente. Scheduler no.

**Impacto:** Comportamiento inconsistente, pero funcional (defaults a "ANY").

---

### 8. Agent name field - historical

**Archivo:** `backend/app/routes/appointments.py:273`

```python
agent_name = agent.name  # was agent.broker_name (bug: field does not exist)
```

**Contexto:** El código original usaba `agent.broker_name` que no existía. Ya corregido a `agent.name`.

**Impacto:** Histórico. Ya resuelto.

---

### 9. WhatsApp message attribution inconsistency

**Archivo:** `backend/app/routes/conversations.py:449`

```python
# NOTE: The ChatService branch (Telegram / other channels) intentionally
# omits the attribution prefix — ChatService may also write the message to
# the DB, and we want the plain text stored there. Telegram's own chat UI
# already shows the sender name, so the prefix is unnecessary.
```

**Contexto:** Solo WhatsApp agrega prefijo `*Name:*\n`. Telegram omite porque ya muestra el nombre.

**Impacto:** Consistencia de UI entre canales. Bajo.

---

### 10. source_type='property' deprecation warning

**Archivo:** `backend/app/routes/knowledge_base.py:111`

```python
response.headers["X-Deprecation"] = (
    "source_type='property' is deprecated. Use POST /api/v1/properties instead."
)
```

**Contexto:** Crear entries de KB con `source_type='property'` aún funciona pero genera warning.

**Impacto:** Deprecation warning en logs. La funcionalidad existe pero se desaconseja.

---

### 11. Telegram messages fallback

**Archivo:** `backend/app/routes/chat.py:146`

```python
# If chat_messages table has no rows, fallback to telegram_messages
```

**Contexto:** Si `chat_messages` no tiene filas para el lead, se cae a `telegram_messages`.

**Impacto:** Compatibilidad hacia atrás. Funciona como se espera.

---

### 12. MCP transport stdio mode

**Archivo:** `backend/app/mcp/server.py:266`

```python
MCP_TRANSPORT=http python -m app.mcp.server
transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
```

**Contexto:** Default es `stdio` para desarrollo local. HTTP recomendado para producción.

**Impacto:** INFO. Configuración de desarrollo vs producción.

---

## Deprecations Activas

| Campo/Feature | Archivo | Alternativa |
|---|---|---|
| `source_type='property'` | `routes/knowledge_base.py:111` | `POST /api/v1/properties` |
| `agent.broker_name` | `routes/appointments.py:273` | `agent.name` |

---

## Changelog

| Fecha | Descripción |
|---|---|
| 2026-04-18 | Agregado bug #4 (conversation debugger) y #12 (MCP transport) |
| 2026-04-17 | Creación del documento. phase-3.1 tool-based handoffs |
| 2026-04-17 | Corregido bug #8 (agent.broker_name → agent.name) — ya resuelto en código |
