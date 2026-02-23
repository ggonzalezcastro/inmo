---
title: API - Endpoints
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# API Endpoints

## Autenticación (`/auth`)

### POST /auth/register

Registrar nuevo broker y usuario admin.

| Campo | Tipo | Requerido | Validación |
|-------|------|-----------|------------|
| `email` | string | Sí | Formato email válido |
| `password` | string | Sí | Min 8 chars, mayúscula, minúscula, dígito |
| `broker_name` | string | Sí | Nombre de la inmobiliaria |

**Respuesta (200):**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### POST /auth/login

Autenticar usuario existente.

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `email` | string | Sí |
| `password` | string | Sí |

**Respuesta (200):** Igual que `/auth/register`

### GET /auth/me

Obtener información del usuario autenticado. Requiere `Authorization: Bearer`.

**Respuesta (200):**

```json
{
  "id": 1,
  "email": "admin@broker.com",
  "name": "Admin User",
  "role": "admin",
  "broker_id": 1,
  "is_active": true
}
```

---

## Leads (`/api/v1/leads`)

### GET /api/v1/leads

Listar leads con filtros y paginación. Filtrado por rol (ADMIN: broker, AGENT: asignados).

| Query Param | Tipo | Default | Descripción |
|-------------|------|---------|-------------|
| `status` | string | - | Filtrar por status (cold/warm/hot/converted/lost) |
| `min_score` | float | - | Score mínimo |
| `max_score` | float | - | Score máximo |
| `search` | string | - | Búsqueda por nombre, email, teléfono |
| `pipeline_stage` | string | - | Filtrar por etapa |
| `skip` | int | 0 | Offset |
| `limit` | int | 50 | Máximo registros |

**Respuesta (200):**

```json
{
  "data": [
    {
      "id": 1,
      "phone": "+521234567890",
      "name": "Juan Pérez",
      "email": "juan@email.com",
      "status": "warm",
      "lead_score": 45.5,
      "pipeline_stage": "perfilamiento",
      "tags": ["interesado", "zona-norte"],
      "metadata": {"budget": "2000000", "location": "Monterrey"},
      "last_contacted": "2026-02-20T15:30:00Z",
      "created_at": "2026-02-15T10:00:00Z"
    }
  ],
  "total": 150,
  "skip": 0,
  "limit": 50
}
```

### POST /api/v1/leads

Crear lead nuevo.

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `phone` | string | Sí | Teléfono (se normaliza a E.164) |
| `name` | string | No | Nombre completo |
| `email` | string | No | Email |
| `tags` | string[] | No | Etiquetas |
| `metadata` | object | No | Datos adicionales |

### PUT /api/v1/leads/{lead_id}

Actualizar lead.

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `name` | string | No |
| `email` | string | No |
| `status` | string | No |
| `tags` | string[] | No |
| `metadata` | object | No |

### DELETE /api/v1/leads/{lead_id}

Eliminar lead. Respuesta: `204 No Content`.

### PUT /api/v1/leads/{lead_id}/assign

Asignar lead a agente. Solo ADMIN.

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `agent_id` | int | Sí |

### PUT /api/v1/leads/{lead_id}/pipeline

Mover lead a etapa del pipeline.

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `stage` | string | Sí |

### POST /api/v1/leads/{lead_id}/recalculate

Recalcular score del lead.

**Respuesta (200):**

```json
{
  "lead_score": 65.0,
  "qualification": "warm"
}
```

### POST /api/v1/leads/bulk-import

Importar leads desde CSV (multipart form).

**Respuesta (200):**

```json
{
  "imported": 45,
  "duplicates": 3,
  "invalid": 2
}
```

---

## Chat (`/api/v1/chat`)

### POST /api/v1/chat/test

Probar respuesta del chat IA.

| Campo | Tipo | Requerido | Validación |
|-------|------|-----------|------------|
| `message` | string | Sí | 1-4000 chars, HTML sanitizado |
| `lead_id` | int | No | Lead existente |
| `provider` | string | No | Canal de chat |

**Respuesta (200):**

```json
{
  "response": "¡Hola! Soy Sofía, tu asesora inmobiliaria...",
  "lead_id": 1,
  "lead_score": 25.0,
  "lead_status": "cold"
}
```

### GET /api/v1/chat/{lead_id}/messages

Obtener historial de mensajes de un lead.

| Query Param | Tipo | Default |
|-------------|------|---------|
| `skip` | int | 0 |
| `limit` | int | 50 |
| `provider` | string | - |

### GET /api/v1/chat/verify/{lead_id}

Verificar datos del lead con mensajes y actividades.

---

## Llamadas de Voz (`/api/v1/calls`)

### POST /api/v1/calls/initiate

Iniciar llamada outbound.

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `lead_id` | int | Sí |
| `campaign_id` | int | No |
| `agent_type` | string | No |

**Respuesta (200):**

```json
{
  "id": 1,
  "lead_id": 5,
  "phone_number": "+521234567890",
  "external_call_id": "call_abc123",
  "status": "initiated",
  "created_at": "2026-02-21T10:00:00Z"
}
```

### GET /api/v1/calls/leads/{lead_id}

Historial de llamadas de un lead.

### GET /api/v1/calls/{call_id}

Detalle de llamada con transcripción.

### POST /api/v1/calls/webhooks/voice

Webhook genérico de voz (default: VAPI).

### POST /api/v1/calls/webhooks/voice/{provider_name}

Webhook de voz por proveedor (`vapi`, `bland`).

---

## Citas (`/api/v1/appointments`)

### POST /api/v1/appointments

Crear cita.

| Campo | Tipo | Requerido | Validación |
|-------|------|-----------|------------|
| `lead_id` | int | Sí | Lead existente |
| `appointment_type` | enum | No | property_visit (default) |
| `start_time` | datetime | Sí | ISO 8601 |
| `duration_minutes` | int | No | 15-480, default 60 |
| `agent_id` | int | Sí | Agente del broker |
| `location` | string | No | Dirección |
| `notes` | string | No | Notas |

### GET /api/v1/appointments

Listar citas con filtros.

| Query Param | Tipo | Descripción |
|-------------|------|-------------|
| `lead_id` | int | Filtrar por lead |
| `agent_id` | int | Filtrar por agente |
| `status` | enum | scheduled/confirmed/cancelled/completed/no_show |
| `start_date` | date | Desde fecha |
| `end_date` | date | Hasta fecha |

### GET /api/v1/appointments/available/slots

Consultar slots disponibles.

| Query Param | Tipo | Requerido |
|-------------|------|-----------|
| `start_date` | date | Sí |
| `end_date` | date | Sí |
| `agent_id` | int | No |
| `appointment_type` | enum | No |
| `duration_minutes` | int | No |

**Respuesta (200):**

```json
[
  {
    "start_time": "2026-02-25T10:00:00Z",
    "end_time": "2026-02-25T11:00:00Z",
    "duration_minutes": 60,
    "date": "2026-02-25",
    "time": "10:00"
  }
]
```

### POST /api/v1/appointments/{appointment_id}/confirm

Confirmar cita. Cambia status a `CONFIRMED`.

### POST /api/v1/appointments/{appointment_id}/cancel

Cancelar cita. Query param opcional: `reason`.

---

## Campañas (`/api/v1/campaigns`)

### POST /api/v1/campaigns

Crear campaña.

| Campo | Tipo | Requerido | Opciones |
|-------|------|-----------|----------|
| `name` | string | Sí | Max 200 chars |
| `description` | string | No | - |
| `channel` | enum | Sí | telegram, call, whatsapp, email |
| `triggered_by` | enum | No | manual (default), lead_score, stage_change, inactivity |
| `trigger_condition` | object | No | Condiciones del trigger |
| `max_contacts` | int | No | Límite de contactos (null = ilimitado) |

### POST /api/v1/campaigns/{campaign_id}/steps

Agregar paso a campaña.

| Campo | Tipo | Requerido | Opciones |
|-------|------|-----------|----------|
| `step_number` | int | Sí | Orden del paso |
| `action` | enum | Sí | send_message, make_call, schedule_meeting, update_stage |
| `delay_hours` | int | No | Default 0 |
| `message_template_id` | int | No | Template a usar |
| `conditions` | object | No | Condiciones adicionales |
| `target_stage` | string | No | Para action=update_stage |

### POST /api/v1/campaigns/{campaign_id}/apply-to-lead/{lead_id}

Aplicar campaña a un lead.

### GET /api/v1/campaigns/{campaign_id}/stats

Estadísticas de campaña.

**Respuesta (200):**

```json
{
  "campaign_id": 1,
  "total_steps": 3,
  "unique_leads": 50,
  "pending": 10,
  "sent": 35,
  "failed": 3,
  "skipped": 2,
  "success_rate": 0.875,
  "failure_rate": 0.075
}
```

---

## Pipeline (`/api/v1/pipeline`)

### POST /api/v1/pipeline/leads/{lead_id}/move-stage

Mover lead a etapa.

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `new_stage` | string | Sí |
| `reason` | string | No |

**Etapas:** `entrada`, `perfilamiento`, `calificacion_financiera`, `agendado`, `seguimiento`, `referidos`, `ganado`, `perdido`

### POST /api/v1/pipeline/leads/{lead_id}/auto-advance

Evaluar auto-avance de etapa.

### GET /api/v1/pipeline/stages/{stage}/leads

Obtener leads de una etapa.

### GET /api/v1/pipeline/metrics

Métricas del pipeline.

### GET /api/v1/pipeline/stages/{stage}/inactive

Leads inactivos en etapa. Query param: `inactivity_days` (default 7).

---

## Templates (`/api/v1/templates`)

### POST /api/v1/templates

Crear template.

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `name` | string | Sí |
| `channel` | enum | Sí |
| `content` | string | Sí |
| `agent_type` | enum | No |
| `variables` | string[] | No |

### GET /api/v1/templates/agent-type/{agent_type}

Templates por tipo de agente (`perfilador`, `calificador_financiero`, `agendador`, `seguimiento`).

---

## Configuración de Broker (`/api/broker`)

### GET /api/broker/config

Obtener configuración completa del broker. Superadmin pasa `?broker_id=N`.

### PUT /api/broker/config/prompt

Actualizar prompt del agente IA. Solo ADMIN+.

### PUT /api/broker/config/leads

Actualizar configuración de scoring. Solo ADMIN+.

### GET /api/broker/config/prompt/preview

Preview del prompt compilado.

### GET /api/broker/config/defaults

Valores por defecto de configuración.

---

## Usuarios del Broker (`/api/broker`)

### GET /api/broker/users

Listar usuarios del broker. Solo ADMIN+.

### POST /api/broker/users

Crear usuario.

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `email` | string | Sí |
| `password` | string | Sí |
| `name` | string | Sí |
| `role` | enum | Sí |

### PUT /api/broker/users/{user_id}

Actualizar usuario.

### DELETE /api/broker/users/{user_id}

Desactivar usuario (soft delete).

---

## Brokers (`/api/brokers`)

### POST /api/brokers/

Crear broker. Solo SUPERADMIN.

### GET /api/brokers/

Listar brokers.

### GET /api/brokers/{broker_id}

Detalle de broker.

### PUT /api/brokers/{broker_id}

Actualizar broker. Solo SUPERADMIN.

### DELETE /api/brokers/{broker_id}

Eliminar broker (soft delete). Solo SUPERADMIN.

---

## Webhooks (`/webhooks`)

### POST /webhooks/telegram

Webhook de Telegram. Header: `X-Telegram-Bot-Api-Secret-Hash`.

### POST /webhooks/chat/{broker_id}/{provider_name}

Webhook unificado para chat (telegram, whatsapp).

---

## Telegram (`/api/v1/telegram`)

### POST /api/v1/telegram/webhook/setup

Configurar webhook de Telegram.

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `webhook_url` | string | Sí |

### GET /api/v1/telegram/webhook/info

Obtener info del webhook actual.
