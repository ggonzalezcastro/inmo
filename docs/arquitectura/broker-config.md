# Arquitectura de Configuración de Broker

**Fecha:** 17 de abril de 2026
**Versión:** 1.0

---

## Overview

Cada **Broker** (corredora de propiedades) posee una configuración aislada que controla el comportamiento del agente IA "Sofía". Esta configuración se divide en tres modelos principales:

| Modelo | Responsabilidad |
|---|---|
| `BrokerPromptConfig` | Personalización del prompt de sistema del agente |
| `BrokerLeadConfig` | Reglas de scoring y calificación de leads |
| `BrokerChatConfig` | Configuración de canales de chat (Telegram, WhatsApp, etc.) |

---

## BrokerPromptConfig

Controla el prompt de sistema que recibe el modelo de lenguaje. Admite dos modos:

1. **Full override**: `full_custom_prompt` ignora todas las demás secciones
2. **Construcción por secciones**: cada campo inyecta una parte del prompt final

### Campos de Identidad

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `agent_name` | `str` | `"Sofía"` | Nombre del agente |
| `agent_role` | `str` | `"asesora inmobiliaria"` | Rol del agente |
| `identity_prompt` | `str \| None` | `None` | Override completo de la sección identidad |

### Campos de Contexto y Objetivo

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `business_context` | `str \| None` | `None` | Contexto del negocio inmobiliario |
| `agent_objective` | `str \| None` | `None` | Objetivo principal del agente |
| `data_collection_prompt` | `str \| None` | `None` | Instrucciones para recolectar datos del lead |

### Campos de Comportamiento

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `behavior_rules` | `str \| None` | `None` | Reglas de comportamiento del agente |
| `restrictions` | `str \| None` | `None` | Restricciones y límites del agente |
| `situation_handlers` | `JSON \| None` | `None` | Manejo de situaciones especiales |

**Estructura de `situation_handlers` (JSON):**

```json
{
  "no_interesado": "Respuesta cuando el lead no está interesado...",
  "ya_tiene_propiedad": "Respuesta cuando ya es dueño...",
  "fuera_de_presupuesto": "Respuesta cuando excede el presupuesto..."
}
```

### Campos de Output

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `output_format` | `str \| None` | `None` | Formato de salida esperado |

### Override Completo

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `full_custom_prompt` | `str \| None` | `None` | Prompt completo que ignora todas las secciones anteriores si está definido |

### Campos de Herramientas

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `enable_appointment_booking` | `bool` | `True` | Habilita la réservation de citas |
| `tools_instructions` | `str \| None` | `None` | Instrucciones adicionales para herramientas |

### Campos de Beneficios y Subsidios

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `benefits_info` | `JSON \| None` | `None` | Información de beneficios y subsidios disponibles |

**Estructura de `benefits_info` (JSON):**

```json
{
  "bono_pie_0": {
    "name": "Bono Pie 0",
    "active": true,
    "conditions": "..."
  },
  "subsidio_ds19": {
    "name": "Subsidio DS19",
    "active": false,
    "conditions": "..."
  }
}
```

### Campos de Calificación

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `qualification_requirements` | `JSON \| None` | `None` | Requisitos de calificación |

**Estructura de `qualification_requirements` (JSON):**

```json
{
  "dicom": {
    "required": "clean",
    "min_months_clean": 12
  },
  "income": {
    "min_income": 400000
  }
}
```

### Campos de Seguimiento

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `follow_up_messages` | `JSON \| None` | `None` | Mensajes de seguimiento automatizado |

**Estructura de `follow_up_messages` (JSON):**

```json
{
  "no_response_24h": "Hola {nombre}, ¿tienes alguna duda sobre la propiedad?",
  "no_response_48h": "Hola {nombre}, queremos saber cómo te fue en la visita...",
  "post_appointment": "Gracias por la visita, ¿tienes algún comentario?"
}
```

### Campos Adicionales

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `additional_fields` | `JSON \| None` | `None` | Campos extras requeridos en el formulario |

**Estructura de `additional_fields` (JSON):**

```json
{
  "age": {"required": true},
  "employment_status": {"required": false}
}
```

### Campos de Reunión

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `meeting_config` | `JSON \| None` | `None` | Configuración de reuniones |

**Estructura de `meeting_config` (JSON):**

```json
{
  "platform": "google_meet",
  "duration_minutes": 60,
  "auto_send_invite": true
}
```

### Campos de Templates de Mensaje

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `message_templates` | `JSON \| None` | `None` | Plantillas de mensajes predefinidos |

**Estructura de `message_templates` (JSON):**

```json
{
  "greeting": "¡Hola {nombre}! Soy Sofía, ¿en qué puedo ayudarte?",
  "appointment_scheduled": "✅ ¡Cita agendada para el {fecha}!",
  "qualification_complete": "🎉 ¡Estás calificado!"
}
```

### Campos de Calendario (OAuth2)

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `google_refresh_token` | `str \| None` | `None` | Token OAuth2 de Google |
| `google_calendar_id` | `str` | `"primary"` | ID del calendario de Google |
| `google_calendar_email` | `str \| None` | `None` | Email asociado al calendario |
| `outlook_refresh_token` | `str \| None` | `None` | Token OAuth2 de Outlook |
| `outlook_calendar_id` | `str \| None` | `None` | ID del calendario de Outlook |
| `outlook_calendar_email` | `str \| None` | `None` | Email de Outlook |
| `calendar_provider` | `str` | `"google"` | Proveedor: `"google"` \| `"outlook"` \| `"none"` |

---

## BrokerLeadConfig

Controla el scoring y calificación de leads para un broker.

### Campos de Ponderación de Campos

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `field_weights` | `dict` | Ver abajo | Ponderación de cada campo en el scoring |

**Default de `field_weights`:**

```python
{
    "name": 10,
    "phone": 15,
    "email": 10,
    "location": 15,
    "budget": 20
}
```

### Campos de Scoring

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `cold_max_score` | `int` | `20` | Score máximo para lead frío |
| `warm_max_score` | `int` | `50` | Score máximo para lead tibio |
| `hot_min_score` | `int` | `50` | Score mínimo para lead hot |
| `qualified_min_score` | `int` | `75` | Score mínimo para lead calificado |

### Campos de Prioridad

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `field_priority` | `list[str]` | Ver abajo | Orden de prioridad de campos |

**Default de `field_priority`:**

```python
["name", "phone", "email", "location", "budget"]
```

### Campos de Criterios de Calificación

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `qualification_criteria` | `JSON \| None` | `None` | Criterios adicionales de calificación |
| `max_acceptable_debt` | `int` | `0` | Deuda máxima aceptable |
| `scoring_config` | `JSON \| None` | `None` | Configuración avanzada de scoring |

**Estructura de `scoring_config` (JSON):**

```json
{
  "income_tiers": [
    {"min": 400000, "max": 800000, "weight": 10},
    {"min": 800000, "max": 1500000, "weight": 20}
  ],
  "dicom_weights": {
    "clean": 30,
    "light_debt": 10,
    "heavy_debt": -20
  }
}
```

### Campos de Alertas

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `alert_on_hot_lead` | `bool` | `True` | Alerta cuando el lead se vuelve hot |
| `alert_score_threshold` | `int` | `70` | Threshold de score para alerta |
| `alert_on_qualified` | `bool` | `True` | Alerta cuando el lead está calificado |
| `alert_email` | `str \| None` | `None` | Email para recibir alertas |

---

## Construcción del System Prompt

El prompt de sistema se construye en `BrokerInitService.build_system_prompt()` siguiendo este algoritmo:

```
build_system_prompt(db, broker_id, lead_context=None) → str
```

### Algoritmo

```
1. Obtener BrokerPromptConfig del broker

2. IF full_custom_prompt está definido:
       RETURN full_custom_prompt

3. ELSE construir por secciones:
       sections = []

       # Sección Identidad
       IF identity_prompt:
           sections.append(identity_prompt)
       ELSE:
           sections.append(f"Eres {agent_name}, {agent_role}.")

       # Sección Contexto
       IF business_context:
           sections.append(f"Contexto del negocio: {business_context}")

       # Sección Objetivo
       IF agent_objective:
           sections.append(f"Objetivo: {agent_objective}")

       # Sección Recolección de Datos
       IF data_collection_prompt:
           sections.append(f"Recolección de datos: {data_collection_prompt}")

       # Sección Reglas
       IF behavior_rules:
           sections.append(f"Reglas de comportamiento: {behavior_rules}")

       # Sección Restricciones
       IF restrictions:
           sections.append(f"Restricciones: {restrictions}")

       # Sección Manejo de Situaciones
       IF situation_handlers:
           sections.append("Manejo de situaciones especiales:")
           FOR key, value IN situation_handlers:
               sections.append(f"- {key}: {value}")

       # Sección Formato de Output
       IF output_format:
           sections.append(f"Formato de salida: {output_format}")

4. IF enable_appointment_booking AND tools_instructions:
       sections.append(f"Instrucciones de herramientas: {tools_instructions}")

5. RETURN "\n\n".join(sections)
```

### Inyección de Contexto del Lead

Cuando se proporciona `lead_context`, el sistema puede usarlo para:
- Personalizar el saludo con el nombre del lead
- Referenciar información de la propiedad en conversación
- Adaptar el nivel de formalidad

---

## Versionamiento de Prompts

### Modelo PromptVersion

Cada versión del prompt se almacena en la tabla `PromptVersion` con los campos:

| Campo | Descripción |
|---|---|
| `id` | UUID único |
| `broker_id` | FK al broker |
| `version` | Número de versión incremental |
| `prompt_content` | Contenido completo del prompt |
| `created_at` | Timestamp de creación |
| `is_active` | Si es la versión actualmente en uso |

### Trazabilidad

- `ChatMessage.prompt_version_id` referencia qué versión del prompt se usó en cada mensaje
- Permite auditar qué prompt estaba activo en cualquier conversación pasada
- Facilita rollback si un cambio de prompt degrada la calidad

### Flujo de Versionamiento

```
1. BrokerActualizaConfig → nueva PromptVersion creada
2. ChatMessage.prompt_version_id → apunta a nueva versión
3. Sistema usa is_active=True para próximas conversaciones
```

---

## BrokerInitService

Servicio que inicializa un nuevo broker con configuración por defecto.

### Flujo de Inicialización

```
broker_registration(broker_data) → Broker
│
├── 1. Create Broker record
│       └── Broker(id, name, email, ...)
│
├── 2. Create BrokerPromptConfig with defaults
│       ├── agent_name = 'Sofía'
│       ├── agent_role = 'asesora inmobiliaria'
│       ├── enable_appointment_booking = True
│       ├── google_calendar_id = 'primary'
│       ├── calendar_provider = 'google'
│       └── ... (all other fields = None)
│
├── 3. Create BrokerLeadConfig with defaults
│       ├── field_weights = {name:10, phone:15, email:10, location:15, budget:20}
│       ├── cold_max_score = 20
│       ├── warm_max_score = 50
│       ├── hot_min_score = 50
│       ├── qualified_min_score = 75
│       ├── field_priority = [name, phone, email, location, budget]
│       ├── max_acceptable_debt = 0
│       ├── alert_on_hot_lead = True
│       ├── alert_score_threshold = 70
│       ├── alert_on_qualified = True
│       └── ... (all other fields = None)
│
├── 4. Create BrokerChatConfig with defaults
│       └── Configuración de canales (Telegram, WhatsApp, etc.)
│
└── 5. Create AgentVoiceTemplate (default)
        └── Plantilla de voz por defecto para llamadas VAPI
```

### Validaciones

- Todos los campos JSON se validan como JSON válido antes de guardar
- Tokens OAuth2 se encriptan antes de almacenar
- Emails de alerta se validan en formato

---

## Changelog

### 17 de abril de 2026 — v1.0

- Creación del documento de arquitectura de broker config
- Documentación completa de `BrokerPromptConfig`
- Documentación completa de `BrokerLeadConfig`
- Algoritmo de construcción de system prompt
- Sistema de versionamiento de prompts
- Flujo de inicialización de `BrokerInitService`
