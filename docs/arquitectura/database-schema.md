# Esquema de Base de Datos — Sistema Inmo CRM

**Versión:** 1.0
**Fecha:** 2026-04-17
**Proyecto:** Inmo CRM (Multi-agente para corretaje inmobiliario)
**Motor:** PostgreSQL 16+ con pgvector (extensión vectorial)

---

## 1. Resumen General

El sistema utiliza **multi-tenencia basada en `broker_id`**. Toda tabla que almacena datos de negocio incluye una FK a `brokers.id`. Las consultas siempre filtran por este campo; nunca se exponen datos de un broker a otro.

### Convenciones de nomenclatura

| Convención | Ejemplo |
|---|---|
| Tablas | `snake_case`, plural: `leads`, `chat_messages` |
| PKs | `id` (int, autoincrement, PK) |
| FKs | `<tabla>_id`: `lead_id`, `broker_id`, `user_id` |
| Timestamps | `created_at`, `updated_at` (DateTime, timezone=True) |
| Soft deletes | No se usa; se emplean flags `is_active` donde corresponde |
| Enum storage | `String(N)` con constraint CHECK en PostgreSQL, no ENUM type |
| JSONB para datos flexibles | `metadata`, `config`, `tags` |

### Extensiones PostgreSQL

```sql
CREATE EXTENSION IF NOT EXISTS vector;  -- embeddings de 768 dims para RAG
```

---

## 2. Modelo de Datos

---

## Tabla: `brokers`

- **Descripción:** Representa una corredora/banca inmobilaria. Cada broker es un tenant completamente aislado. Toda tabla de negocio tiene `broker_id` como FK.
- ** motor: ** SQLAlchemy (async) con `UuidPrimaryKeyMixin` (id int serial)

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `name` | String(200) | No | — | — | — |
| `slug` | String(100) | Yes | — | UNIQUE, INDEX | — |
| `contact_phone` | String(20) | Yes | — | — | — |
| `contact_email` | String(200) | Yes | — | — | — |
| `business_hours` | JSONB | Yes | — | — | — |
| `service_zones` | JSONB | Yes | — | — | — |
| `is_active` | Boolean | No | `True` | INDEX | — |
| `plan_id` | Integer | Yes | — | INDEX | `broker_plans.id` |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Relaciones

- `plan` → `BrokerPlan` (muchos a uno)
- `users` → `User` (uno a muchos)
- `prompt_config` → `BrokerPromptConfig` (uno a uno, back_populates="broker", uselist=False)
- `lead_config` → `BrokerLeadConfig` (uno a uno, uselist=False)
- `voice_config` → `BrokerVoiceConfig` (uno a uno, uselist=False)
- `chat_config` → `BrokerChatConfig` (uno a uno, uselist=False)
- `chat_messages` → `ChatMessage` (uno a muchos)
- `voice_templates` → `AgentVoiceTemplate` (uno a muchos)
- `prompt_versions` → `PromptVersion` (uno a muchos)
- `knowledge_base_entries` → `KnowledgeBase` (uno a muchos)

### Índices

- `idx_broker_slug` ON (`slug`) — lookup por slug en URLs
- `idx_broker_plan` ON (`plan_id`) — filtrar por plan
- `idx_broker_active` ON (`is_active`) — listar solo activas

---

## Tabla: `users`

- **Descripción:** Usuarios del sistema (agentes, admins, superadmins). Pertenecen a un broker. El rol determina los permisos a nivel de API. Cada agente puede tener un `AgentVoiceProfile` vinculado para llamadas VAPI.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `email` | String(100) | No | — | UNIQUE, INDEX | — |
| `hashed_password` | String(255) | No | — | — | — |
| `name` | String(100) | No | — | — | — |
| `role` | Enum(UserRole) | No | `AGENT` | INDEX | — |
| `broker_id` | Integer | Yes | — | INDEX | `brokers.id` |
| `is_active` | Boolean | No | `True` | INDEX | — |
| `assignment_priority` | Integer | Yes | — | — | — |
| `google_calendar_id` | String(255) | Yes | — | — | — |
| `google_calendar_connected` | Boolean | No | `False` | — | — |
| `google_refresh_token` | String | Yes | — | — | — |
| `google_calendar_email` | String(255) | Yes | — | — | — |
| `outlook_refresh_token` | String | Yes | — | — | — |
| `outlook_calendar_id` | String(500) | Yes | — | — | — |
| `outlook_calendar_email` | String(255) | Yes | — | — | — |
| `outlook_calendar_connected` | Boolean | No | `False` | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Roles (UserRole enum)

- `SUPERADMIN` — acceso total, sin restricción por broker
- `ADMIN` — acceso total dentro de su broker
- `AGENT` — acceso limitado a leads asignados

### Relaciones

- `broker` → `Broker` (muchos a uno)
- `assigned_leads` → `Lead` (uno a muchos, via `assigned_to`)
- `appointments` → `Appointment` (uno a muchos, via `agent_id`)
- `voice_profile` → `AgentVoiceProfile` (uno a uno, cascade delete)
- `availability_slots` → `AvailabilitySlot` (uno a muchos)
- `appointment_blocks` → `AppointmentBlock` (uno a muchos)

### Índices

- `idx_user_email` ON (`email`) — login
- `idx_user_broker` ON (`broker_id`) — filtro por broker
- `idx_user_role` ON (`role`) — filtro por rol

### Notas

- `assignment_priority`: menor número = mayor prioridad en la cola de asignación (NULL = fuera de la cola)
- `google_refresh_token` y `outlook_refresh_token` están encriptados con `encrypt_value()`
- `google_calendar_connected` / `outlook_calendar_connected`: flag que incluye al agente en round-robin de agenda

---

## Tabla: `broker_plans`

- **Descripción:** Planes de suscripción (ej. Básico, Profesional, Enterprise). Define límites y features disponibles por broker.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `name` | String(100) | No | — | — | — |
| `max_agents` | Integer | No | 0 | — | — |
| `max_leads` | Integer | No | 0 | — | — |
| `features` | JSONB | No | `{}` | — | — |
| `monthly_cost` | Numeric(10,2) | No | 0 | — | — |
| `created_at` | DateTime | No | now() | — | — |

### Relaciones

- `brokers` → `Broker` (uno a muchos)

---

## Tabla: `leads`

- **Descripción:** Prospecto inmobiliario. Es la entidad central del CRM. Contiene datos de contacto, scoring, pipeline stage y metadata flexible en JSONB.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `phone` | String(20) | No | — | INDEX | — |
| `name` | String(100) | Yes | — | — | — |
| `email` | String(100) | Yes | — | — | — |
| `status` | String(20) | No | `cold` | INDEX | — |
| `lead_score` | Float | No | `0.0` | INDEX | — |
| `lead_score_components` | JSONB | Yes | — | — | — |
| `last_contacted` | DateTime | Yes | — | INDEX | — |
| `pipeline_stage` | String(50) | Yes | — | INDEX | — |
| `stage_entered_at` | DateTime | Yes | — | INDEX | — |
| `campaign_history` | JSONB | Yes | — | — | — |
| `assigned_to` | Integer | Yes | — | INDEX | `users.id` |
| `broker_id` | Integer | Yes | — | INDEX | `brokers.id` |
| `treatment_type` | String(30) | Yes | — | INDEX | — |
| `next_action_at` | DateTime | Yes | — | INDEX | — |
| `close_reason` | String(100) | Yes | — | — | — |
| `close_reason_detail` | Text | Yes | — | — | — |
| `closed_at` | DateTime | Yes | — | — | — |
| `closed_from_stage` | String(50) | Yes | — | — | — |
| `notes` | Text | Yes | — | — | — |
| `tags` | JSONB | No | `[]` | — | — |
| `lead_metadata` | JSONB | No | `{}` | — | — |
| `human_mode` | Boolean | No | `False` | INDEX | — |
| `human_assigned_to` | Integer | Yes | — | INDEX | `users.id` |
| `human_taken_at` | DateTime | Yes | — | — | — |
| `human_released_at` | DateTime | Yes | — | — | — |
| `human_release_note` | Text | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Status (lead_status)

| Valor | Descripción |
|---|---|
| `cold` | Lead recién creado, sin interacción significativa |
| `warm` | Ha mostrado interés, score moderado |
| `hot` | Alto interés, score alto, listo para calificación |
| `converted` | Se convirtió en cliente (compró/arriendló) |
| `lost` | Se perdió como oportunidad |

### Pipeline Stages

```
entrada → perfilamiento → calificacion_financiera → potencial → agendado → ganado/perdido
```

| Stage | Descripción |
|---|---|
| `entrada` | Lead nuevo, en espera de primer contacto |
| `perfilamiento` | Recopilando datos del lead (presupuesto, zona, tipo de propiedad) |
| `calificacion_financiera` | Verificando capacidad financiera (DICOM, ingresos) |
| `potencial` | Calificado como potencial comprador/inquilino |
| `agendado` | Visita o reunión agendada |
| `seguimiento` | Post-visita, nurturing |
| `referidos` | Generando referidos |
| `ganado` | Cerrado como venta |
| `perdido` | Cerrado como perdido |

### Treatment Types

| Valor | Descripción |
|---|---|
| `AUTOMATED_TELEGRAM` | Hilo conversacional automatizado por Sofía via Telegram |
| `AUTOMATED_CALL` | Llamada automatizada via VAPI |
| `MANUAL_FOLLOW_UP` | Agente humano hace seguimiento manual |
| `HOLD` | En pausa, no contactar |

### `lead_score_components` — Estructura JSONB

```json
{
  "base": 0,
  "behavior": 0,
  "engagement": 0,
  "stage": 0,
  "financial": 0,
  "penalties": 0
}
```

Cada componente es un Float que se suma para obtener `lead_score` (0–100).

### `campaign_history` — Estructura JSONB

```json
[
  {
    "campaign_id": 42,
    "applied_at": "2026-04-01T10:00:00Z",
    "trigger": "lead_score",
    "steps_completed": 3
  }
]
```

### `lead_metadata` — Estructura JSONB

```json
{
  "budget": {
    "min": 15000000,
    "max": 30000000,
    "currency": "CLP",
    "financing_needed": true
  },
  "location": {
    "commune": "Providencia",
    "region": "Metropolitana",
    "zones_preferred": ["Las Condes", "Vitacura"]
  },
  "dicom_status": "clean",
  "dicom_detail": {
    "protests": 0,
    "last_protest_date": null,
    "endorsed": false
  },
  "monthly_income": 1200000,
  "employment_type": "dependiente",
  "property_type": "departamento",
  "bedrooms_min": 2,
  "area_min": 60,
  "parking": true,
  "sentiment": "interested",
  "conversation_state": {
    "last_stage": "perfilamiento",
    "last_agent": "QualifierAgent",
    "pending_fields": ["budget", "location"]
  },
  "conversation_summary": "Lead interesado en depto en Las Condes, presupuesto 20-30M...",
  "message_history": [
    {"from": "lead", "text": "...", "timestamp": "2026-04-01T10:00:00Z"},
    {"from": "agent", "text": "...", "timestamp": "2026-04-01T10:01:00Z"}
  ],
  "calificacion": {
    "score": 72,
    "dicom_checked": true,
    "income_verified": true,
    "budget_confirmed": true
  },
  "human_mode_notified": false,
  "off_topic_count": 0,
  "do_not_reply": false,
  "telegram_user_id": "123456789",
  "whatsapp_id": "56912345678",
  "source": "telegram",
  "first_contact_at": "2026-04-01T09:00:00Z",
  "preferences": {
    "visit_schedule": "weekends",
    "contact_method": "telegram"
  }
}
```

### Relaciones

- `telegram_messages` → `TelegramMessage` (cascade delete)
- `chat_messages` → `ChatMessage` (cascade delete)
- `activities` → `ActivityLog` (cascade delete)
- `appointments` → `Appointment` (cascade delete)
- `campaign_logs` → `CampaignLog` (cascade delete)
- `voice_calls` → `VoiceCall` (cascade delete)
- `assigned_agent` → `User` (muchos a uno, via `assigned_to`)
- `human_agent` → `User` (muchos a uno, via `human_assigned_to`)
- `broker` → `Broker` (muchos a uno)

### Índices

| Índice | Columnas | Propósito |
|---|---|---|
| `idx_leads_phone` | `phone` | Búsqueda por teléfono (identificador único de lead) |
| `idx_leads_status_score` | `status, lead_score` | Dashboard, ordenar por score dentro de status |
| `idx_leads_pipeline_stage` | `pipeline_stage, stage_entered_at` | Kanban, filtro por etapa |
| `idx_leads_assigned_treatment` | `assigned_to, treatment_type` | Filtro de agentes + tipo de trato |
| `idx_leads_next_action` | `next_action_at, treatment_type` | Cola de próximas acciones |
| `idx_leads_human_mode` | `human_mode` | Filtro de leads en modo humano |
| `idx_leads_broker` | `broker_id` | Aislamiento multi-tenant |

---

## Tabla: `broker_prompt_configs`

- **Descripción:** Configuración deprompting para la IA Sofía de un broker. Define personalidad, instrucciones, herramientas, templates de mensajes y calendarios.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | No | — | UNIQUE, INDEX | `brokers.id` |
| `agent_name` | String(100) | No | `Sofía` | — | — |
| `agent_role` | String(200) | No | `asesora inmobiliaria` | — | — |
| `identity_prompt` | Text | Yes | — | — | — |
| `business_context` | Text | Yes | — | — | — |
| `agent_objective` | Text | Yes | — | — | — |
| `data_collection_prompt` | Text | Yes | — | — | — |
| `behavior_rules` | Text | Yes | — | — | — |
| `restrictions` | Text | Yes | — | — | — |
| `situation_handlers` | JSONB | Yes | — | — | — |
| `output_format` | Text | Yes | — | — | — |
| `full_custom_prompt` | Text | Yes | — | — | — |
| `enable_appointment_booking` | Boolean | No | `True` | — | — |
| `tools_instructions` | Text | Yes | — | — | — |
| `benefits_info` | JSONB | Yes | — | — | — |
| `qualification_requirements` | JSONB | Yes | — | — | — |
| `follow_up_messages` | JSONB | Yes | — | — | — |
| `additional_fields` | JSONB | Yes | — | — | — |
| `meeting_config` | JSONB | Yes | — | — | — |
| `message_templates` | JSONB | Yes | — | — | — |
| `google_refresh_token` | Text | Yes | — | — | — |
| `google_calendar_id` | String(255) | Yes | — | — | — |
| `google_calendar_email` | String(255) | Yes | — | — | — |
| `outlook_refresh_token` | Text | Yes | — | — | — |
| `outlook_calendar_id` | String(255) | Yes | — | — | — |
| `outlook_calendar_email` | String(255) | Yes | — | — | — |
| `calendar_provider` | String(20) | No | `google` | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### `situation_handlers` — Estructura JSONB

```json
{
  "no_interesado": {
    "respuesta": "Entiendo. Quedo atenta si cambias de opinión...",
    "tag": "no_interesado"
  },
  "ya_compro": {
    "respuesta": "¡Qué bueno! Si conoces a alguien más...",
    "tag": "referido"
  }
}
```

### `benefits_info` — Estructura JSONB

```json
{
  "bono_pie_0": {
    "name": "Bono pie 0%",
    "active": true,
    "conditions": "Para departamentos-selected"
  },
  "subsidio_ds1": {
    "name": "Subsidio DS1",
    "active": true,
    "max_amount": 12000000
  }
}
```

### `qualification_requirements` — Estructura JSONB

```json
{
  "dicom": {
    "required": true,
    "min_months_clean": 6,
    "max_protests": 0
  },
  "income": {
    "min": 500000,
    "currency": "CLP"
  }
}
```

### `follow_up_messages` — Estructura JSONB

```json
{
  "no_response_24h": "Hola {{name}}, no tuvimos respuesta. ¿Podemos conversar?",
  "no_response_72h": "Hola {{name}}, te escribo nuevamente...",
  "post_visit": "¡Gracias por la visita! ¿Te gustó la propiedad?"
}
```

### `meeting_config` — Estructura JSONB

```json
{
  "platform": "google_meet",
  "duration_minutes": 60,
  "buffer_minutes": 15,
  "auto_confirm": false
}
```

### `message_templates` — Estructura JSONB

```json
{
  "greeting": "¡Hola! Soy Sofía, tu asesora. ¿En qué puedo ayudarte hoy?",
  "appointment_scheduled": "✅ ¡Cita agendada para el {{date}} a las {{time}}!",
  "reminder_24h": "Te recuerdo tu visita mañana a las {{time}}..."
}
```

### Relaciones

- `broker` → `Broker` (uno a uno, back_populates="prompt_config")

---

## Tabla: `broker_lead_configs`

- **Descripción:** Configuración de scoring y alertas para leads de un broker. Define umbrales de status, pesos de campos y alertas.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | No | — | UNIQUE, INDEX | `brokers.id` |
| `field_weights` | JSONB | No | `{}` | — | — |
| `cold_max_score` | Integer | No | `20` | — | — |
| `warm_max_score` | Integer | No | `50` | — | — |
| `hot_min_score` | Integer | No | `50` | — | — |
| `qualified_min_score` | Integer | No | `75` | — | — |
| `field_priority` | JSONB | No | `[]` | — | — |
| `qualification_criteria` | JSONB | Yes | — | — | — |
| `max_acceptable_debt` | Integer | No | `0` | — | — |
| `scoring_config` | JSONB | Yes | — | — | — |
| `alert_on_hot_lead` | Boolean | No | `True` | — | — |
| `alert_score_threshold` | Integer | No | `70` | — | — |
| `alert_on_qualified` | Boolean | No | `True` | — | — |
| `alert_email` | String(200) | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### `field_weights` — Estructura JSONB

```json
{
  "name": 10,
  "phone": 15,
  "email": 10,
  "location": 15,
  "budget": 20
}
```

### `scoring_config` — Estructura JSONB

```json
{
  "engagement_multiplier": 1.2,
  "stage_bonus": {
    "perfilamiento": 5,
    "calificacion_financiera": 10,
    "potencial": 15
  },
  "penalty_decay_days": 7
}
```

### Relaciones

- `broker` → `Broker` (uno a uno)

---

## Tabla: `broker_voice_configs`

- **Descripción:** Configuración de voz (VAPI) para un broker. Estructura similar a `BrokerPromptConfig` pero para llamadas de voz.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | No | — | UNIQUE, INDEX | `brokers.id` |
| `vapi_api_key` | String(255) | Yes | — | — | — |
| `vapi_assistant_id` | String(255) | Yes | — | — | — |
| `voice_id` | String(100) | Yes | — | — | — |
| `voice_model` | String(50) | Yes | — | — | — |
| `temperature` | Float | Yes | `0.3` | — | — |
| `max_duration_seconds` | Integer | Yes | `300` | — | — |
| `welcome_message` | Text | Yes | — | — | — |
| `post_call_message` | Text | Yes | — | — | — |
| `recording_enabled` | Boolean | No | `True` | — | — |
| `transcription_enabled` | Boolean | No | `True` | — | — |
| `provider` | String(20) | No | `vapi` | — | — |
| `config` | JSONB | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Relaciones

- `broker` → `Broker` (uno a uno)

---

## Tabla: `broker_chat_configs`

- **Descripción:** Configuración de chat (canales, webhooks) para un broker.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | No | — | UNIQUE, INDEX | `brokers.id` |
| `telegram_token` | String(255) | Yes | — | — | — |
| `whatsapp_business_id` | String(255) | Yes | — | — | — |
| `whatsapp_token` | String(255) | Yes | — | — | — |
| `instagram_username` | String(100) | Yes | — | — | — |
| `instagram_password` | String(255) | Yes | — | — | — |
| `webchat_enabled` | Boolean | No | `True` | — | — |
| `webchat_webhook_url` | String(500) | Yes | — | — | — |
| `channels_enabled` | JSONB | Yes | — | — | — |
| `config` | JSONB | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### `channels_enabled` — Estructura JSONB

```json
{
  "telegram": true,
  "whatsapp": true,
  "instagram": false,
  "webchat": true
}
```

### Relaciones

- `broker` → `Broker` (uno a uno)

---

## Tabla: `conversations`

- **Descripción:** Agrupa mensajes de chat en conversaciones. Una conversación = un hilo con un lead en un canal específico.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `lead_id` | Integer | No | — | INDEX | `leads.id` |
| `provider` | String(20) | No | — | INDEX | — |
| `channel_user_id` | String(255) | No | — | INDEX | — |
| `status` | String(20) | No | `active` | INDEX | — |
| `started_at` | DateTime | No | now() | — | — |
| `ended_at` | DateTime | Yes | — | — | — |
| `last_message_at` | DateTime | Yes | — | INDEX | — |
| `message_count` | Integer | No | `0` | — | — |
| `metadata` | JSONB | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |

### Relaciones

- `broker` → `Broker` (muchos a uno)
- `lead` → `Lead` (muchos a uno)
- `messages` → `ChatMessage` (uno a muchos)

### Índices

- `idx_conversation_broker_provider_user` ON (`broker_id, provider, channel_user_id`) — lookup único por canal

---

## Tabla: `chat_messages`

- **Descripción:** Mensaje individual en un canal de chat. Un lead puede tener múltiples mensajes en múltiples canales.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `lead_id` | Integer | No | — | INDEX | `leads.id` |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `conversation_id` | Integer | Yes | — | INDEX | `conversations.id` |
| `provider` | String(20) | No | — | INDEX | — |
| `channel_user_id` | String(255) | No | — | INDEX | — |
| `channel_username` | String(255) | Yes | — | — | — |
| `channel_message_id` | String(255) | Yes | — | INDEX | — |
| `message_text` | Text | No | — | — | — |
| `direction` | String(20) | No | — | INDEX | — |
| `status` | String(20) | No | `pending` | INDEX | — |
| `provider_metadata` | JSONB | Yes | — | — | — |
| `attachments` | JSONB | Yes | — | — | — |
| `ai_response_used` | Boolean | No | `True` | — | — |
| `prompt_version_id` | Integer | Yes | — | INDEX | `prompt_versions.id` |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Proveedores (ChatProvider)

`TELEGRAM`, `WHATSAPP`, `INSTAGRAM`, `FACEBOOK`, `TIKTOK`, `WEBCHAT`

### Dirección (MessageDirection)

| Valor | Descripción |
|---|---|
| `INBOUND` | Mensaje del lead al sistema |
| `OUTBOUND` | Respuesta del sistema (o agente) al lead |

### Estatus (MessageStatus)

`PENDING`, `SENT`, `DELIVERED`, `READ`, `FAILED`

### `provider_metadata` — Estructura JSONB

```json
{
  "telegram_message_id": 123456,
  "telegram_chat_id": 123456789,
  "whatsapp_msg_id": "wamid.xxx",
  "edit_date": null,
  "reply_to_message_id": null
}
```

### `attachments` — Estructura JSONB

```json
[
  {
    "type": "image",
    "url": "https://...",
    "file_id": "abc123"
  },
  {
    "type": "document",
    "url": "https://...",
    "file_name": "presupuesto.pdf"
  }
]
```

### Relaciones

- `lead` → `Lead` (muchos a uno)
- `broker` → `Broker` (muchos a uno)
- `conversation` → `Conversation` (muchos a uno)
- `prompt_version` → `PromptVersion` (muchos a uno)

### Índices

| Índice | Columnas | Propósito |
|---|---|---|
| `idx_chat_lead_provider` | `lead_id, provider` | Historial por lead y canal |
| `idx_chat_broker_provider` | `broker_id, provider` | Estadísticas por canal |
| `idx_chat_channel_user` | `provider, channel_user_id` | Routing de mensajes entrantes |
| `idx_chat_prompt_version` | `prompt_version_id` | Auditar qué versión de prompt respondió |

---

## Tabla: `telegram_messages`

- **Descripción:** Mensajes específicos de Telegram. coexist with `chat_messages` (hay redundancia controlada). Se mantiene para compatibilidad con lógica legacy.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `lead_id` | Integer | No | — | INDEX | `leads.id` |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `telegram_chat_id` | String(50) | No | — | INDEX | — |
| `telegram_message_id` | String(50) | Yes | — | INDEX | — |
| `message_text` | Text | Yes | — | — | — |
| `message_type` | String(20) | No | `text` | — | — |
| `from_user` | Boolean | No | `True` | — | — |
| `created_at` | DateTime | No | now() | INDEX | — |

### Relaciones

- `lead` → `Lead` (muchos a uno)
- `broker` → `Broker` (muchos a uno)

---

## Tabla: `appointments`

- **Descripción:** Citas vinculadas a leads (visitas a propiedades, reuniones, llamadas). Se sincronizan con Google Calendar.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `lead_id` | Integer | No | — | INDEX | `leads.id` |
| `agent_id` | Integer | Yes | — | INDEX | `users.id` |
| `appointment_type` | String(30) | No | — | INDEX | — |
| `status` | String(20) | No | `scheduled` | INDEX | — |
| `start_time` | DateTime | No | — | INDEX | — |
| `end_time` | DateTime | No | — | — | — |
| `duration_minutes` | Integer | No | `60` | — | — |
| `location` | String(500) | Yes | — | — | — |
| `property_address` | String(500) | Yes | — | — | — |
| `meet_url` | String(500) | Yes | — | — | — |
| `google_event_id` | String(255) | Yes | — | INDEX | — |
| `notes` | Text | Yes | — | — | — |
| `lead_notes` | Text | Yes | — | — | — |
| `reminder_sent_24h` | Boolean | No | `False` | — | — |
| `reminder_sent_1h` | Boolean | No | `False` | — | — |
| `cancelled_at` | DateTime | Yes | — | — | — |
| `cancellation_reason` | Text | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Tipos de Cita (AppointmentType)

`PROPERTY_VISIT`, `VIRTUAL_MEETING`, `PHONE_CALL`, `OFFICE_MEETING`, `OTHER`

### Estatus (AppointmentStatus)

`SCHEDULED`, `CONFIRMED`, `CANCELLED`, `COMPLETED`, `NO_SHOW`

### Relaciones

- `lead` → `Lead` (muchos a uno)
- `agent` → `User` (muchos a uno)

### Índices

| Índice | Columnas | Propósito |
|---|---|---|
| `idx_appointment_lead_status` | `lead_id, status` | Historial de citas del lead |
| `idx_appointment_agent_status` | `agent_id, status` | Agenda del agente |
| `idx_appointment_datetime` | `start_time, end_time` | Disponibilidad, detección de overlaps |
| `idx_appointment_google_event` | `google_event_id` | Sincronización con calendario |

---

## Tabla: `availability_slots`

- **Descripción:** Bloques de disponibilidad recurring para agentes. Define horas específicas por día de la semana.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | Yes | — | INDEX | `brokers.id` |
| `agent_id` | Integer | Yes | — | INDEX | `users.id` |
| `day_of_week` | Integer | No | — | — | — |
| `start_time` | Time | No | — | — | — |
| `end_time` | Time | No | — | — | — |
| `valid_from` | Date | No | today | — | — |
| `valid_until` | Date | Yes | — | — | — |
| `appointment_type` | String(30) | Yes | — | — | — |
| `slot_duration_minutes` | Integer | No | `60` | — | — |
| `max_appointments_per_slot` | Integer | No | `1` | — | — |
| `is_active` | Boolean | No | `True` | INDEX | — |
| `notes` | Text | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Notas

- `agent_id = NULL` → el slot aplica a todos los agentes del broker
- `day_of_week`: 0=Lunes, 6=Domingo

### Relaciones

- `agent` → `User` (muchos a uno, opcional)

---

## Tabla: `appointment_blocks`

- **Descripción:** Bloques de tiempo no disponible (vacaciones, meetings, etc.) que impiden agendar citas.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | Yes | — | INDEX | `brokers.id` |
| `agent_id` | Integer | Yes | — | INDEX | `users.id` |
| `start_time` | DateTime | No | — | INDEX | — |
| `end_time` | DateTime | No | — | INDEX | — |
| `is_recurring` | Boolean | No | `False` | — | — |
| `recurrence_pattern` | String(100) | Yes | — | — | — |
| `recurrence_end_date` | Date | Yes | — | — | — |
| `reason` | String(200) | Yes | — | — | — |
| `notes` | Text | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Relaciones

- `agent` → `User` (muchos a uno, opcional)

### Índices

- `idx_block_datetime` ON (`start_time, end_time`) — detección de overlaps

---

## Tabla: `knowledge_base`

- **Descripción:** Base de conocimiento RAG con embeddings vectoriales (pgvector, 768 dims). Alimenta las búsquedas semánticas de Sofía.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `title` | String(255) | No | — | — | — |
| `content` | Text | No | — | — | — |
| `embedding` | Vector(768) | Yes | — | IVFFLAT | — |
| `source_type` | String(50) | No | `custom` | INDEX | — |
| `kb_metadata` | JSONB | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Source Types

`property`, `faq`, `policy`, `subsidy`, `custom`

### `kb_metadata` — Estructura JSONB

```json
{
  "property_id": 123,
  "address": "Av. Providencia 123, Depto 401",
  "price": 25000000,
  " bedrooms": 3,
  "bathrooms": 2,
  "area": 75,
  "commune": "Providencia",
  "property_type": "departamento",
  "images": ["url1", "url2"],
  "available": true
}
```

### Índices

```sql
-- Búsqueda vectorial por similitud coseno
CREATE INDEX idx_knowledge_base_embedding
ON knowledge_base
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Filtrado por broker y tipo
CREATE INDEX idx_knowledge_base_broker_source
ON knowledge_base (broker_id, source_type);
```

### Relaciones

- `broker` → `Broker` (muchos a uno)

### Notas

- Embeddings generados con Gemini `text-embedding-004` (768 dims)
- Búsqueda: `cosine_distance(embedding, query_embedding) < threshold`

---

## Tabla: `campaigns`

- **Descripción:** Campañas de nurturing/marketing que ejecutan secuencias de pasos (mensajes, llamadas, cambios de stage) sobre leads.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `name` | String(200) | No | — | — | — |
| `description` | Text | Yes | — | — | — |
| `channel` | String(20) | No | — | INDEX | — |
| `status` | String(20) | No | `draft` | INDEX | — |
| `triggered_by` | String(20) | No | `manual` | INDEX | — |
| `trigger_condition` | JSONB | Yes | — | — | — |
| `max_contacts` | Integer | Yes | — | — | — |
| `created_by` | Integer | Yes | — | INDEX | `users.id` |
| `approved_by` | Integer | Yes | — | INDEX | `users.id` |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Canales (CampaignChannel)

`TELEGRAM`, `CALL`, `WHATSAPP`, `EMAIL`

### Estatus (CampaignStatus)

`DRAFT`, `PENDING_REVIEW`, `ACTIVE`, `PAUSED`, `COMPLETED`

### Triggers (CampaignTrigger)

`MANUAL`, `LEAD_SCORE`, `STAGE_CHANGE`, `INACTIVITY`

### `trigger_condition` — Estructuras según trigger

```json
// LEAD_SCORE
{ "score_min": 30, "score_max": 70 }

// STAGE_CHANGE
{ "stage": "perfilamiento" }

// INACTIVITY
{ "inactivity_days": 7 }
```

### Relaciones

- `broker` → `User` (muchos a uno — broker como entity, no como FK user)
- `creator` → `User` (muchos a uno, via `created_by`)
- `approver` → `User` (muchos a uno, via `approved_by`)
- `steps` → `CampaignStep` (uno a muchos, ordenados por step_number)
- `logs` → `CampaignLog` (uno a muchos)

### Índices

- `idx_campaign_broker_status` ON (`broker_id, status`)
- `idx_campaign_trigger` ON (`triggered_by, status`)

---

## Tabla: `campaign_steps`

- **Descripción:** Pasos individuales de una campaña. Cada paso define una acción, delay y condiciones.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `campaign_id` | Integer | No | — | INDEX | `campaigns.id` |
| `step_number` | Integer | No | — | — | — |
| `action` | String(30) | No | — | INDEX | — |
| `message_template_id` | Integer | Yes | — | INDEX | `message_templates.id` |
| `message_text` | Text | Yes | — | — | — |
| `use_ai_message` | Boolean | No | `False` | — | — |
| `step_channel` | String(20) | Yes | — | — | — |
| `delay_hours` | Integer | No | `0` | — | — |
| `conditions` | JSONB | Yes | — | — | — |
| `target_stage` | String(50) | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Acciones (CampaignStepAction)

`SEND_MESSAGE`, `MAKE_CALL`, `SCHEDULE_MEETING`, `UPDATE_STAGE`

### `conditions` — Estructura JSONB

```json
{
  "min_score": 20,
  "max_score": 80,
  "required_fields": ["phone", "budget"],
  "exclude_tags": ["no_interesado"]
}
```

### Relaciones

- `campaign` → `Campaign` (muchos a uno)
- `message_template` → `MessageTemplate` (muchos a uno, opcional)

### Índices

- `idx_campaign_step_order` ON (`campaign_id, step_number`)

---

## Tabla: `campaign_logs`

- **Descripción:** Log de ejecución de cada paso de campaña sobre cada lead. Registra si se envió, falló o saltó.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `campaign_id` | Integer | No | — | INDEX | `campaigns.id` |
| `lead_id` | Integer | No | — | INDEX | `leads.id` |
| `step_number` | Integer | No | — | — | — |
| `status` | String(20) | No | `pending` | INDEX | — |
| `response` | JSONB | Yes | — | — | — |
| `created_at` | DateTime | No | now() | INDEX | — |
| `executed_at` | DateTime | Yes | — | — | — |

### Estatus (CampaignLogStatus)

`PENDING`, `SENT`, `FAILED`, `SKIPPED`

### `response` — Estructura JSONB

```json
{
  "message_id": "telegram_123",
  "error": null,
  "llm_used": true,
  "prompt_version": 5
}
```

### Relaciones

- `campaign` → `Campaign` (muchos a uno)
- `lead` → `Lead` (muchos a uno)

### Índices

| Índice | Columnas | Propósito |
|---|---|---|
| `idx_campaign_log_lead` | `lead_id, status` | Estado de lead en campaña |
| `idx_campaign_log_campaign_lead` | `campaign_id, lead_id` | Lookup único por campaña+lead |
| `idx_campaign_log_created` | `created_at` | Limpieza de logs antiguos |

---

## Tabla: `message_templates`

- **Descripción:** Plantillas de mensaje reutilizables para campañas y respuestas automáticas.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `name` | String(200) | No | — | — | — |
| `content` | Text | No | — | — | — |
| `channel` | String(20) | No | `telegram` | INDEX | — |
| `variables` | JSONB | Yes | — | — | — |
| `is_active` | Boolean | No | `True` | INDEX | — |
| `created_by` | Integer | Yes | — | INDEX | `users.id` |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### `variables` — Estructura JSONB

```json
["name", "agent_name", "property_address", "appointment_date"]
```

### Relaciones

- `broker` → `Broker` (muchos a uno)
- `creator` → `User` (muchos a uno)
- `campaign_steps` → `CampaignStep` (uno a muchos)

---

## Tabla: `voice_calls`

- **Descripción:** Registro de llamadas de voz realizadas via VAPI. Incluye duración, transcript, recording y costo.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `lead_id` | Integer | No | — | INDEX | `leads.id` |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `campaign_id` | Integer | Yes | — | INDEX | `campaigns.id` |
| `external_call_id` | String(255) | Yes | — | — | — |
| `phone_number` | String(20) | No | — | — | — |
| `status` | String(20) | No | `initiated` | INDEX | — |
| `duration` | Integer | Yes | — | — | — |
| `recording_url` | String(500) | Yes | — | — | — |
| `transcript` | Text | Yes | — | — | — |
| `cost_usd` | Numeric(10,6) | Yes | — | — | — |
| `started_at` | DateTime | Yes | — | — | — |
| `ended_at` | DateTime | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Estatus (CallStatus)

`INITIATED`, `RINGING`, `ANSWERED`, `COMPLETED`, `FAILED`, `NO_ANSWER`, `BUSY`, `CANCELLED`

### Relaciones

- `lead` → `Lead` (muchos a uno)
- `broker` → `Broker` (muchos a uno)
- `campaign` → `Campaign` (muchos a uno, opcional)

---

## Tabla: `activity_logs`

- **Descripción:** Log inmutable de todas las acciones relevantes sobre un lead (cambios de stage, asignaciones, notas). Alimenta el timeline del frontend.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `lead_id` | Integer | No | — | INDEX | `leads.id` |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `action_type` | String(50) | No | — | INDEX | — |
| `details` | JSONB | Yes | — | — | — |
| `timestamp` | DateTime | No | now() | INDEX | — |

### `action_type` valores comunes

`stage_change`, `assignment`, `note_added`, `appointment_scheduled`, `call_completed`, `campaign_enrolled`, `human_mode_engaged`, `human_mode_released`, `score_updated`, `tag_added`, `tag_removed`

### `details` — Estructura JSONB (ejemplo stage_change)

```json
{
  "from_stage": "entrada",
  "to_stage": "perfilamiento",
  "trigger": "qualifier_agent",
  "agent_id": null,
  "reason": null
}
```

### Relaciones

- `lead` → `Lead` (muchos a uno)
- `broker` → `Broker` (muchos a uno)

### Índices

- `idx_activity_lead_timestamp` ON (`lead_id, timestamp DESC`) — timeline del lead
- `idx_activity_broker_timestamp` ON (`broker_id, timestamp DESC`) — auditoría global

---

## Tabla: `prompt_versions`

- **Descripción:** Control de versiones de prompts. Cada vez que se modifica `BrokerPromptConfig`, se crea una nueva versión. Permite auditar quéprompt respondió cada mensaje.

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `version_number` | Integer | No | — | — | — |
| `full_prompt_text` | Text | No | — | — | — |
| `prompt_hash` | String(64) | No | — | — | — |
| `is_active` | Boolean | No | `True` | INDEX | — |
| `created_at` | DateTime | No | now() | — | — |

### Notas

- `prompt_hash` = SHA256 del `full_prompt_text` para detectar cambios sin comparar texto
- `is_active = False` para versiones anteriores (no se usan para nuevas respuestas, pero se mantienen para auditoría)

### Relaciones

- `broker` → `Broker` (muchos a uno)
- `chat_messages` → `ChatMessage` (uno a muchos)

---

## Tabla: `agent_voice_templates`

- **Descripción:** Plantillas de voz a nivel de broker. Define la configuración base que los agentes no pueden editar (business_prompt, transcriber, límites) y las opciones que sí pueden elegir (voices, tones).

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `broker_id` | Integer | No | — | INDEX | `brokers.id` |
| `name` | String(200) | No | — | — | — |
| `business_prompt` | Text | Yes | — | — | — |
| `qualification_criteria` | JSONB | Yes | — | — | — |
| `niche_instructions` | Text | Yes | — | — | — |
| `language` | String(20) | No | `es` | — | — |
| `transcriber_config` | JSONB | Yes | — | — | — |
| `max_duration_seconds` | Integer | No | `600` | — | — |
| `max_silence_seconds` | Float | No | `30.0` | — | — |
| `recording_policy` | String(20) | No | `enabled` | — | — |
| `available_voice_ids` | JSONB | No | `[]` | — | — |
| `available_tones` | JSONB | No | `[]` | — | — |
| `default_call_mode` | String(20) | No | `transcriptor` | — | — |
| `is_active` | Boolean | No | `True` | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Campos relevantes

| Campo | Descripción |
|---|---|
| `business_prompt` | Prompt base de negocio — agentes no pueden editarlo |
| `qualification_criteria` | Criterios de calificación (JSONB, configurable por broker) |
| `transcriber_config` | Dict de config Deepgram para transcripción |
| `recording_policy` | `"enabled"` \| `"optional"` \| `"disabled"` |
| `available_voice_ids` | Lista de voces VAPI disponibles para el agente elegir |
| `available_tones` | Lista de tonos (ej. `"formal"`, `"friendly"`) |
| `default_call_mode` | `"ai_agent"` \| `"transcriptor"` cuando agente no tiene preferencia |
| `default_call_mode` | `"ai_agent"` \| `"transcriptor"` cuando agente no tiene preferencia |

### Relaciones

- `broker` → `Broker` (muchos a uno)
- `profiles` → `AgentVoiceProfile` (uno a muchos)

### Notas

- `AgentVoiceProfile` (per-user) hereda de `AgentVoiceTemplate` (per-broker) y anula `voice_id` y `tone`
- El `business_prompt` es inmutable por agente — solo editable por ADMIN del broker

---

## Tabla: `agent_voice_profiles`

- **Descripción:** Perfil de voz por agente individual. Hereda de `AgentVoiceTemplate` y define preferencias personales (voz seleccionada, tono, modo de llamada). Cada usuario tiene a lo sumo un profile (unique en `user_id`).

### Columnas

| Columna | Tipo | Nullable | Default | Índice | FK |
|---|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | PK | — |
| `user_id` | Integer | No | — | UNIQUE, INDEX | `users.id` |
| `template_id` | Integer | No | — | INDEX | `agent_voice_templates.id` |
| `selected_voice_id` | String(255) | Yes | — | — | — |
| `selected_tone` | String(50) | Yes | — | — | — |
| `assistant_name` | String(100) | Yes | — | — | — |
| `opening_message` | Text | Yes | — | — | — |
| `preferred_call_mode` | String(20) | Yes | — | — | — |
| `vapi_assistant_id` | String(255) | Yes | — | — | — |
| `created_at` | DateTime | No | now() | — | — |
| `updated_at` | DateTime | No | now() | — | — |

### Restricciones

- `selected_voice_id` debe estar en `template.available_voice_ids`
- `selected_tone` debe estar en `template.available_tones`
- `preferred_call_mode`: `"ai_agent"` \| `"transcriptor"` \| NULL (hereda del template)

### Relaciones

- `user` → `User` (uno a uno, back_populates="voice_profile")
- `template` → `AgentVoiceTemplate` (muchos a uno, back_populates="profiles")

### Notas

- `vapi_assistant_id` es gestionado por el backend, nunca expuesto al frontend
- `assistant_name` + `opening_message`: persona IA mostrada al lead en llamadas

---

## 3. Diagrama Relacional Simplificado

```
brokers ───┬── users
           ├── broker_prompt_configs (1:1)
           ├── broker_lead_configs (1:1)
           ├── broker_voice_configs (1:1)
           ├── broker_chat_configs (1:1)
           ├── prompt_versions
           ├── agent_voice_templates
           ├── knowledge_base
           ├── message_templates
           ├── campaigns ── campaign_steps
           │                  └── campaign_logs ── leads
           ├── conversations ── chat_messages ── leads
           ├── appointments ── leads
           │              └── users (agent)
           ├── availability_slots ── users (agent)
           ├── appointment_blocks ── users (agent)
           ├── voice_calls ── leads
           └── activity_logs ── leads
```

---

## 4. Notas de Implementación

### Multi-tenancy

Todas las tablas con `broker_id` deben incluirlo en:
- Queries: `WHERE broker_id = :broker_id`
- FK constraints hacia `brokers`
- Índices compuestos que incluyan `broker_id` como primera columna
- WebSocket rooms: `broker_id` como namespace

### Encriptación

Los siguientes campos están encriptados at-rest (AES-256-GCM, clave en variable de entorno):

- `BrokerPromptConfig.google_refresh_token`
- `BrokerPromptConfig.outlook_refresh_token`
- `BrokerChatConfig.telegram_token`
- `BrokerChatConfig.whatsapp_token`
- `BrokerChatConfig.instagram_password`
- `BrokerVoiceConfig.vapi_api_key`

Ver `app/core/encryption.py`.

### PII y `lead_metadata`

`lead_metadata` es JSONB y puede contener PII. Se encripta a nivel de columna usando `app/core/encryption.py`. Los campos `phone`, `email`, `name` se almacenan en columnas typed (para indexing), pero también pueden existir en `lead_metadata` en texto plano — la encriptación de la columna cubre ambos escenarios.

### Scoring

El `lead_score` se calcula en `app/services/leads/scoring.py`. Los componentes se almacenan en `lead_score_components`. El score nunca se guarda en caché indefinidamente; se recalcula en cada `LeadService.get_lead()` y tras eventos relevantes.

### Búsqueda Vectorial

La búsqueda semántica en `KnowledgeBase` usa similitud coseno:

```python
result = await session.execute(
    select(KnowledgeBase).where(
        KnowledgeBase.broker_id == broker_id,
        cast(func.cohere_embedding(embedding, query_embedding), Float) < 0.7
    ).order_by(
        func.cohere_embedding(embedding, query_embedding).asc()
    )
)
```

### Índices de вектор (pgvector)

```sql
CREATE INDEX idx_lead_embedding ON leads
USING ivfflat (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
```

---

## Changelog

| Fecha | Versión | Cambios |
|---|---|---|
| 2026-04-18 | 1.1 | Actualizada sección `users` con campos OAuth calendar y voice_profile. Corregida sección `agent_voice_templates` (modelo real difiere del doc). Agregada sección `agent_voice_profiles` completa. |
