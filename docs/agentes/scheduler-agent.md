# SchedulerAgent

**Fecha de última actualización:** 17 de abril de 2026
**Propietario del stage:** `calificacion_financiera`
**Agente destino para handoff:** `FollowUpAgent`

---

## 1. Propósito y Responsabilidad

El `SchedulerAgent` gestiona el agendamiento de visitas a propiedades mediante integración con Google Calendar. Su responsabilidad principal es convertir un lead calificado (en stage `calificacion_financiera`) en una cita confirmada, recopilando los datos mínimos necesarios y coordinando la disponibilidad entre el agente y el lead.

El agente opera exclusivamente sobre leads que han sido cualificados financieramente y han expresado interés en agendar una visita presencial o virtual.

---

## 2. Condiciones de `should_handle()`

El `SchedulerAgent` asume el procesamiento de un mensaje cuando se cumplen **todas** las siguientes condiciones:

1. `current_stage == "calificacion_financiera"`
2. `current_agent == "scheduler"` (sticky session)
3. El lead posee los datos mínimos requeridos (nombre, teléfono, email)
4. La intención del mensaje indica voluntad de agendar (`appointment_intent` o palabras clave de agendamiento)

Si alguna condición no se cumple, el `AgentSupervisor` evalúa reasignación a otro agente según la tabla `_STAGE_TO_AGENT`.

---

## 3. Flujo de `process()`

```
process(message, AgentContext, db) → Tuple[str, Optional[HandoffSignal]]
│
├── 1. Validar campos obligatorios del lead
│       ├─ name: presente y no placeholder
│       ├─ phone: presente, no "web_chat_pending", no empieza con "+569999"
│       └─ email: presente y válido
│
├── 2. Si faltan campos → devolver errorBlocking
│       │   "El lead no está calificado. Faltan datos obligatorios: {missing_fields}"
│
├── 3. Extraer parámetros de la solicitud
│       ├─ fecha_solicitada: parseada del mensaje o inferida
│       ├─ duracion_minutos: default 60
│       ├─ agent_id: del contexto oinferido del broker
│       └─ modalidad: "PRESENCIAL" | "VIRTUAL_MEETING"
│
├── 4. Obtener horarios disponibles
│       └─ tool: get_available_appointment_slots
│           date: fecha_solicitada
│           duration_minutes: duracion_minutos
│           agent_id: agent_id
│
├── 5. Si no hay horarios → devolver errorBlocking
│       │   "No hay horarios disponibles para esa fecha"
│
├── 6. Presentar opciones al lead (1-3 slots)
│       └─ Generar mensaje con horarios disponibles
│
├── 7. Esperar confirmación del lead (puede tomar varios mensajes)
│
├── 8. Validar agente tiene email configurado (Google Calendar)
│       └─ Si no tiene email → devolver errorBlocking
│
├── 9. Crear la cita
│       └─ tool: create_appointment
│           start_time: slot seleccionado
│           duration_minutes: duracion_minutos
│           agent_id: agent_id
│           location: dirección o "Reunión virtual"
│           notes: datos del lead
│
├── 10. Si creación falla → devolver errorBlocking
│        └─ "No se pudo crear la cita. Intenta nuevamente."
│
├── 11. Confirmar al lead con detalles de la cita
│
├── 12. Avanzar stage del lead a "agendado"
│       └─ auto_advance_stage(lead, "agendado", db)
│
└── 13. Emitir HandoffSignal hacia FollowUpAgent
            target_agent: "follow_up"
            reason: "appointment_confirmed"
            context_updates: {appointment_id, scheduled_time}
```

---

## 4. Herramientas (Function Calling)

### 4.1. `get_available_appointment_slots`

```json
{
  "name": "get_available_appointment_slots",
  "description": "Obtiene horarios disponibles para agendar una visita",
  "parameters": {
    "type": "object",
    "properties": {
      "date": {
        "type": "string",
        "description": "Fecha en formato YYYY-MM-DD"
      },
      "duration_minutes": {
        "type": "integer",
        "description": "Duración en minutos"
      },
      "agent_id": {
        "type": "integer",
        "description": "ID del agente"
      }
    },
    "required": ["date"]
  }
}
```

**Comportamiento del tool executor:**

1. Consultar tabla `AvailabilitySlot` para el `agent_id` especificado
   - Filtrar por `day_of_week` correspondiente a la fecha
   - Filtrar por rango `valid_from <= date <= valid_until`
2. Obtener `AppointmentBlock` del agente para ese día (horas bloqueadas)
3. Obtener `Appointment` existentes del agente para ese día
4. Generar ventanas disponibles restando bloques y citas existentes
5. Retornar lista de slots ordenados cronológicamente

**Retorno:** Lista de diccionarios con `{"start": "HH:MM", "end": "HH:MM", "available": bool}`

---

### 4.2. `create_appointment`

```json
{
  "name": "create_appointment",
  "description": "Crea una cita en Google Calendar",
  "parameters": {
    "type": "object",
    "properties": {
      "start_time": {
        "type": "string",
        "description": "Fecha y hora ISO"
      },
      "duration_minutes": {
        "type": "integer"
      },
      "agent_id": {
        "type": "integer"
      },
      "location": {
        "type": "string",
        "description": "Dirección o 'Reunión virtual'"
      },
      "notes": {
        "type": "string"
      }
    },
    "required": ["start_time", "duration_minutes", "agent_id", "location"]
  }
}
```

**Comportamiento del tool executor:**

1. Validar que el lead tenga datos mínimos (`name`, `phone`, `email`)
2. Validar que el agente tenga email válido (requerido por Google Calendar API)
3. Crear registro `Appointment` en base de datos
4. Si `location == "Reunión virtual"`:
   - Generar Google Meet URL via Google Calendar API
   - Asignar `conferenceData` al evento
5. Crear evento en Google Calendar con:
   - `summary`: "Visita de propiedad - {lead_name}"
   - `attendees`: `[{email: lead_email}]`
   - `location`: dirección o link de Meet
   - `reminders`: `[{"method": "email", "minutes": 1440}, {"method": "popup", "minutes": 60}]` (24h y 1h)
6. Registrar `Activity` del tipo `appointment_created`
7. Retornar detalles de la cita creada

**En caso de error:** No crear registro en base de datos. Devolver mensaje de error Blocking.

---

## 5. Modelo de Datos

### `AvailabilitySlot`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer | PK |
| `agent_id` | Integer (FK, nullable) | null = disponible para todo el broker |
| `day_of_week` | Integer (0-6) | 0 = Lunes |
| `start_time` | Time | Hora de inicio del slot |
| `end_time` | Time | Hora de fin del slot |
| `valid_from` | Date | Inicio de validez |
| `valid_until` | Date | Fin de validez |
| `slot_duration_minutes` | Integer | Default: 60 |
| `max_appointments_per_slot` | Integer | Default: 1 |

### `Appointment`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer | PK |
| `lead_id` | Integer (FK) | Lead asociado |
| `agent_id` | Integer (FK) | Agente asignado |
| `broker_id` | Integer (FK) | Broker (multi-tenant) |
| `start_time` | DateTime | Inicio de la cita |
| `duration_minutes` | Integer | Duración |
| `location` | String | Dirección o "Reunión virtual" |
| `google_event_id` | String | ID del evento en Google Calendar |
| `meet_url` | String (nullable) | Link de Google Meet |
| `status` | Enum | `scheduled`, `confirmed`, `cancelled`, `completed` |
| `notes` | Text (nullable) | Notas adicionales |

---

## 6. Integración con Google Calendar

### Configuración

- **OAuth2**: Refresh token almacenado en `BrokerPromptConfig`
- **Calendar ID**: Obtenido de configuración del broker (default: `"primary"`)

### Flujo de autenticación

```
BrokerPromptConfig.google_refresh_token
        │
        ▼
Google Auth (oauth2 Credentials.refresh())
        │
        ▼
Service Build (googleapiclient.discovery.build('calendar', 'v3'))
        │
        ▼
API Calls (events().insert())
```

### Creación de evento

```python
event = {
    "summary": f"Visita de propiedad - {lead.name}",
    "location": location,  # dirección o Meet link
    "description": notes,
    "start": {
        "dateTime": start_time.isoformat(),
        "timeZone": "America/Santiago",
    },
    "end": {
        "dateTime": (start_time + timedelta(minutes=duration)).isoformat(),
        "timeZone": "America/Santiago",
    },
    "attendees": [
        {"email": lead.email}
    ],
    "conferenceData": {
        "createRequest": {"requestId": uuid.uuid4().hex}
    } if virtual_meeting else None,
    "reminders": {
        "useDefault": False,
        "overrides": [
            {"method": "email", "minutes": 24 * 60},  # 24 horas
            {"method": "popup", "minutes": 60},        # 1 hora
        ]
    }
}
```

---

## 7. Gate de Cualificación

El `SchedulerAgent` requiere que el lead tenga los siguientes datos antes de proceder:

| Campo | Validación | Fallback |
|-------|------------|----------|
| `name` | No vacío, no null | Error blocking |
| `phone` | No vacío, no `"web_chat_pending"`, no empieza con `"+569999"` | Error blocking |
| `email` | No vacío, formato válido | Error blocking |

**Respuesta de error:**

```
"El lead no está calificado. Faltan datos obligatorios: {missing_fields}"
```

Donde `{missing_fields}` es una lista separada por comas de los campos faltantes.

---

## 8. Handoffs

### Hacia `FollowUpAgent`

**Trigger:** Cita creada exitosamente

**Direction:** `HandoffSignal(target_agent="follow_up", reason="appointment_confirmed")`

**Contexto incluido:**

```python
{
    "appointment_id": int,
    "scheduled_time": datetime,
    "lead_id": int,
    "location": str,
    "agent_id": int
}
```

**Rationale:** El `FollowUpAgent` se encarga de confirmar la cita con el lead, enviar recordatorios y hacer seguimiento en caso de cancelación o re-agendamiento.

---

## 9. Casos Borde

| Escenario | Comportamiento |
|-----------|----------------|
| No hay slots disponibles para la fecha solicitada | Devolver `"No hay horarios disponibles para esa fecha"` |
| Agente sin email configurado | Devolver error blocking (Google Calendar requiere email) |
| Falla al crear evento en Google Calendar | Devolver error, no crear registro en DB |
| Lead con teléfono placeholder (`web_chat_pending`) | Devolver error de cualificación |
| Teléfono comienza con `+569999` (formato inválido) | Devolver error de cualificación |
| Fecha en el pasado | Ignorar y pedir fecha futura |
| Conflicto de horarios (race condition) | Verificar nuevamente antes de crear; si ya existe, devolver error |
| Duración no especificada | Usar default de 60 minutos |
| Agent no existe o está inactivo | Devolver error blocking |

---

## 10. Estados y Transiciones

```
┌─────────────────────────┐      ┌─────────────┐
│ calificacion_financiera │──────►│  agendado   │
│   (SchedulerAgent)      │ crear │ (auto_advance│
│                         │ cita  │  _stage)     │
└─────────────────────────┘      └─────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ FollowUpAgent   │
                              │ (confirmación y │
                              │  seguimiento)    │
                              └─────────────────┘
```

---

## 11. Métricas de Evaluaciones

En el framework de evaluaciones (`tests/evals/`), las métricas relevantes para el `SchedulerAgent` son:

- **TaskCompletionMetric**: Verifica creación exitosa de cita con todos los campos requeridos
- **DicomRuleMetric**: No aplica directamente (regla manejada en `QualifierAgent`)

---

## 12. Configuración de Handoff Tools

```python
_HANDOFF_TOOLS = [
    {
        "name": "schedule_appointment",
        "description": "Confirma el agendamiento de una visita con el lead",
        "parameters": {
            "type": "object",
            "properties": {
                "slot": {"type": "string"},
                "confirm": {"type": "boolean"}
            }
        }
    }
]
```

---

## Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 2026-04-17 | Creación del documento. Documenta flujo completo del SchedulerAgent incluyendo tools, Google Calendar, handoffs y casos borde. |