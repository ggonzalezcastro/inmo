# Sistema de Human Handoff (Escalación Humana)

**Fecha:** 17 de Abril 2026
**Estado:** Implementado

---

## Resumen

El sistema de Human Handoff permite que un agente humano tome control de una conversación de un lead, pausando la IA y habilitando la comunicación directa. El agente puede liberar la conversación cuando termine, opcionalmente marcando la interacción como trainable para alimentar la base de conocimiento.

---

## Modelo de Datos

### Campos en tabla `leads`

| Campo | Tipo | Descripción |
|---|---|---|
| `human_mode` | Boolean | Indica si un humano está actualmente atendiendo el lead |
| `human_assigned_to` | Integer (FK users.id) | ID del agente asignado; NULL si no hay nadie asignado |
| `human_taken_at` | DateTime | Timestamp de cuándo se tomó el control |
| `human_released_at` | DateTime | Timestamp de cuándo se liberó el control |
| `human_release_note` | Text | Nota opcional al liberar (razón, resumen, etc.) |

### Campos en `lead_metadata` (JSONB)

| Campo | Tipo | Descripción |
|---|---|---|
| `human_mode_notified` | Boolean | Previene mensajes de handoff duplicados del AI |
| `do_not_reply` | Boolean | Si true, la IA envía fallback fijo en lugar de procesar |

---

## Diagrama de Flujo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HUMAN MODE — TAKEOVER / RELEASE                      │
└─────────────────────────────────────────────────────────────────────────────┘

  LEAD MESSAGE INBOUND
         │
         ▼
  ┌──────────────────┐
  │ lead.human_mode? │
  └────────┬─────────┘
           │
     YES   │   NO
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌────────────┐   ┌─────────────────────────────────────────────────────────┐
│ human_mode │   │                    ORCHESTRATOR AI                      │
│ NOTIFIED?  │   │                                                         │
└─────┬──────┘   │  ┌─────────────┐    ┌─────────────┐    ┌───────────┐  │
      │          │  │ Qualifier   │───▶│ Scheduler   │───▶│ FollowUp  │  │
YES   │NO         │  │   Agent     │    │   Agent     │    │   Agent   │  │
┌─────┴────┐     │  └─────────────┘    └─────────────┘    └───────────┘  │
│          │     │         │                  │                   │       │
▼          ▼     │         ▼                  ▼                   ▼       │
┌────────────┐   │  ┌──────────────────────────────────────────────────┐  │
│  RETURN    │   │  │          AI RESPONSE + TOOLS                     │  │
│ "[human_   │   │  └──────────────────────────────────────────────────┘  │
│   mode]"   │   │                         │                               │
│  (SILENT)  │   │                         ▼                               │
└────────────┘   │              ┌──────────────────────┐                   │
                 │              │  do_not_reply flag?  │                   │
                 │              └──────────┬───────────┘                   │
                 │                   YES   │   NO                           │
                 │                  ┌───────┴────────┐                       │
                 │                  ▼                 ▼                       │
                 │           ┌──────────┐    ┌──────────────┐                │
                 │           │ SEND     │    │ SEND AI      │                │
                 │           │ FALLBACK │    │ RESPONSE     │                │
                 │           └──────────┘    └──────────────┘                │
                 └─────────────────────────────────────────────────────────┘
                       ▲
                       │
        ┌──────────────┴──────────────┐
        │      POST /takeover          │
        │      (Agent Takes Over)      │
        └──────────────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  1. human_mode = TRUE                                           │
  │  2. human_assigned_to = current_user.id                         │
  │  3. human_taken_at = now()                                      │
  │  4. human_metadata["human_mode_notified"] = TRUE                 │
  │  5. COMMIT                                                       │
  │  6. WS: broadcast human_mode_changed to broker                   │
  └─────────────────────────────────────────────────────────────────┘
                       │
                       ▼
           AGENT SENDS MESSAGE VIA /send-message
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  1. Verify human_mode == TRUE                                   │
  │  2. Get channel from last ChatMessage                           │
  │  3. Format with agent attribution (WhatsApp: "*Name:*\\n msg") │
  │  4. Send via provider (WhatsApp/Telegram/other)                 │
  │  5. Log to ChatMessage (ai_response_used=FALSE)                 │
  │  6. WS: broadcast new_message                                    │
  │  7. Return message_id                                           │
  └─────────────────────────────────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │      POST /release          │
        │      (Agent Releases)       │
        └──────────────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  1. human_mode = FALSE                                          │
  │  2. human_assigned_to = NULL                                    │
  │  3. human_taken_at = NULL                                       │
  │  4. human_released_at = now()                                   │
  │  5. human_release_note = body.note (optional)                   │
  │  6. Clear human_mode_notified from metadata                     │
  │  7. Reset sentiment: jsonb_set(metadata, '{sentiment}', '{}')  │
  │  8. If trainable + resolution_summary:                          │
  │        → RAGService.add_document() with source_subtype=         │
  │          "resolution"                                            │
  │  9. WS: broadcast human_mode_changed to broker                  │
  └─────────────────────────────────────────────────────────────────┘
```

---

## Operaciones de API

### 1. Takeover — POST /conversations/leads/{lead_id}/takeover

Toma control de una conversación de lead.

**Request Body:** (vacío o nulo)

**Pasos ejecutados:**

1. `lead.human_mode = True`
2. `lead.human_assigned_to = current_user.id`
3. `lead.human_taken_at = now()`
4. `lead_metadata["human_mode_notified"] = True` — previene que la IA envíe el mensaje genérico de handoff
5. Commit a la base de datos
6. Broadcast evento WebSocket `human_mode_changed` a todo el broker

**WebSocket broadcast (`human_mode_changed`):**

```json
{
  "event": "human_mode_changed",
  "lead_id": 123,
  "human_mode": true,
  "taken_by": 456,
  "taken_at": "2026-04-17T10:30:00Z"
}
```

---

### 2. Release — POST /conversations/leads/{lead_id}/release

Libera una conversación previamente tomada.

**Request Body:**

```json
{
  "note": "Lead qualificado, presupuesto 50M CLP, buscar departamentos en Providencia",
  "trainable": true,
  "resolution_summary": "Lead buscaba departamento en Providencia hasta 50M CLP, scheduling para este sábado"
}
```

**Pasos ejecutados:**

1. `lead.human_mode = False`
2. `lead.human_assigned_to = None`
3. `lead.human_taken_at = None`
4. `lead.human_released_at = now()`
5. `lead.human_release_note = body.note` (opcional)
6. Eliminar `human_mode_notified` del lead_metadata
7. Resetear sentiment via SQL: `jsonb_set(metadata, '{sentiment}', '{}')`
8. Si `body.trainable=True` y `body.resolution_summary` presente:
   - Crear entrada en KnowledgeBase via `RAGService.add_document()`
   - `source_subtype = "resolution"`
9. Broadcast evento WebSocket `human_mode_changed`

**WebSocket broadcast (`human_mode_changed`):**

```json
{
  "event": "human_mode_changed",
  "lead_id": 123,
  "human_mode": false,
  "released_at": "2026-04-17T11:00:00Z",
  "release_note": "Lead qualificado, presupuesto 50M CLP"
}
```

---

### 3. Send Message — POST /conversations/leads/{lead_id}/send-message

Envía un mensaje de agente humano al lead.

**Request Body:**

```json
{
  "message": "Hola Juan! Te contactamos de Inmobiliaria XYZ. Cuéntanos, aún estás interesado en departamentos en Providencia?"
}
```

**Pasos ejecutados:**

1. Verificar que `lead.human_mode == True`; si no, retornar error 400
2. Obtener channel del último ChatMessage (provider, channel_user_id)
3. Formatear mensaje con atribución al agente:
   - **WhatsApp:** `*Nombre Agente:*\n{mensaje}`
   - **Telegram/otro:** mensaje plano
4. Enviar via proveedor correspondiente:
   - WhatsApp → `WhatsAppService.send_text_message()`
   - Telegram/otro → `ChatService.send_message()`
5. Registrar mensaje en tabla `ChatMessage` con `ai_response_used=False`
6. Broadcast evento WebSocket `new_message`
7. Retornar `message_id`

**Respuesta exitosa (200):**

```json
{
  "message_id": "msg_abc123",
  "sent_at": "2026-04-17T11:05:00Z"
}
```

---

### 4. Do Not Reply — POST /conversations/leads/{lead_id}/do-not-reply

Activa el modo do_not_reply para un lead.

**Request Body:** (vacío)

**Efecto:** `lead_metadata["do_not_reply"] = true`

La próxima vez que llegue un mensaje inbound, en lugar de procesarlo con IA, se envía un fallback fijo configurado por el broker.

**Desactivar:** DELETE /conversations/leads/{lead_id}/do-not-reply

---

## Bandera `human_mode_notified`

### Propósito

Cuando un agente humano toma control manualmente (takeover), se setea `human_mode_notified=True` para que la IA **nunca** dispare el mensaje genérico de escalación ("Entiendo tu frustración...").

Sin esta bandera, el próximo mensaje inbound del lead provocaría que la IA envíe el aviso de handoff genérico, lo cual es confuso para leads que no están frustrados y ya tienen un asesor escribiéndoles.

### Lógica en Orchestrator

```python
if lead.human_mode:
    if not lead_metadata.get("human_mode_notified"):
        # Enviar mensaje de handoff configurable del broker
        # Luego setear human_mode_notified = True
        send_handoff_message()
        set_human_mode_notified()
    else:
        # IA silenciosa — retornar "[human_mode]"
        return "[human_mode]"
```

### Mensaje de Handoff (Escalación)

**Default:** `"Entiendo tu frustración. Un agente de nuestra inmobiliaria se pondrá en contacto contigo muy pronto para ayudarte. 🙏"`

**Personalizable** via `BrokerPromptConfig.message_templates["escalation_handoff"]`

---

## Modo `do_not_reply`

El flag `do_not_reply` en `lead_metadata` actúa como un bypass completo del procesamiento IA.

### Activación

- Manual: POST /conversations/leads/{lead_id}/do-not-reply
- Automático: Se activa después de 3 mensajes off-topic o intentos de prompt-injection (lógica en orchestrator)

### Comportamiento

Cuando `do_not_reply == true`:

1. El mensaje inbound del lead **no se procesa** por ningún agent
2. Se envía al lead un mensaje fallback fijo (configurado por broker)
3. No se avanza pipeline, no se registra actividad de IA

### Casos de Uso

- Lead solicita expresamente no ser contactado
- Número inválido o fuera de servicio
- Protección contra mensajes spam/inyección después de 3 intentos fallidos

---

## Reglas de Visibilidad

### List Conversations (`GET /conversations/`)

| Estado del Lead | Visibilidad |
|---|---|
| `human_mode=False` (gestionado por IA) | Visible para todo el equipo |
| `human_mode=True` con `human_assigned_to` definido | **Solo visible para el agente asignado** |
| `human_mode=True` sin `human_assigned_to` (auto-escalado) | Visible para todo el equipo |

### Justificación

- **IA activa:** cualquiera puede ver y tomar el lead
- **Tomado por agente específico:** solo ese agente ve el lead (evita duplicated work)
- **Auto-escalado:** emergencia o handoff automático sin agente designado — todos deben poder verlo

---

## Eventos WebSocket

### `human_mode_changed`

Broadcast a todos los clientes conectados del broker cuando un lead cambia de estado human_mode.

**Payload (takeover):**
```json
{
  "event": "human_mode_changed",
  "lead_id": 123,
  "human_mode": true,
  "taken_by": 456,
  "taken_at": "2026-04-17T10:30:00Z"
}
```

**Payload (release):**
```json
{
  "event": "human_mode_changed",
  "lead_id": 123,
  "human_mode": false,
  "released_at": "2026-04-17T11:00:00Z",
  "release_note": "Lead qualificado"
}
```

---

### `human_mode_incoming`

Enviado al agente asignado cuando llega un nuevo mensaje de un lead en human_mode.

**Payload:**
```json
{
  "event": "human_mode_incoming",
  "lead_id": 123,
  "lead_name": "Juan Pérez",
  "phone": "+56912345678",
  "message_text": "Hola, tengo interés en el depto de Providencia",
  "channel": "telegram",
  "assigned_to": 456
}
```

---

## Limitaciones y Problemas Conocidos

### 1. Sin Timeout — Lead Atascado

**Problema:** Si un agente toma control pero nunca responde, el lead queda atrapado en human_mode indefinidamente.

**Impacto:** El lead no recibe respuestas de la IA ni del humano.

**Workaround actual:** El agente debe liberar manualmente o usar la bandera `do_not_reply` como solución temporal.

---

### 2. Limitación Webchat

**Problema:** Cuando un lead está en human_mode via webchat (no WhatsApp/Telegram), no existe un canal real para enviar mensajes.

**Impacto:** El sistema solo loguea el mensaje en la DB; no hay entrega real al lead.

**Nota:** El endpoint `/send-message` igualmente intenta enviar, pero el provider de webchat no soporta outbound.

---

### 3. Sin Reconciliation Automática

**Problema:** Si el agente cierra sesión sin liberar (`/release`), el lead permanece en human_mode.

**Impacto:** El lead queda en estado inconsistente hasta que otro proceso o admin lo libere.

---

### 4. Duplicación de `human_assigned_to` en metadata

**Nota:** Existe redundancia entre `human_assigned_to` (columna FK) y `lead_metadata["human_assigned_to"]` en algunos puntos del código. La columna FK es la fuente oficial de verdad.

---

## Tabla de Flags de Lead

```
┌─────────────────────────────────────────────────────────────────────┐
│                        lead_metadata JSONB                          │
├─────────────────────────┬───────────────────────────────────────────┤
│ human_mode_notified     │ Boolean — previene msg de handoff duplicado│
│ do_not_reply            │ Boolean — bypass IA, envía fallback fijo   │
│ sentiment               │ {} — reseteado al release                   │
│ human_assigned_to       │ (redundante con columna FK)                │
└─────────────────────────┴───────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     TABLA LEADS (columnas)                          │
├─────────────────────────┬───────────────────────────────────────────┤
│ human_mode              │ Boolean — estado principal                 │
│ human_assigned_to        │ Integer FK — agente assigned              │
│ human_taken_at          │ DateTime — cuando se tomó                   │
│ human_released_at       │ DateTime — cuando se liberó                 │
│ human_release_note      │ Text — nota opcional al liberar           │
└─────────────────────────┴───────────────────────────────────────────┘
```

---

## Changelog

| Fecha | Cambio |
|---|---|
| 2026-04-17 | Documentación inicial creada |
| 2026-04-17 | Flag `human_mode_notified` documentado — previene mensajes de handoff duplicados |
| 2026-04-17 | Agregado modo `do_not_reply` con activacion manual y automática (3 strikes) |
| 2026-04-17 | Reglas de visibilidad diferenciadas por estado de asignación |
| 2026-04-17 | Limitaciones: no timeout, webchat sin outbound, no reconciliation automática |
