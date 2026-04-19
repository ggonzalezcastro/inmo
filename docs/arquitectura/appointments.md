# Appointments — Sistema de Agenda y Citas

**Versión:** 1.0
**Fecha:** 2026-04-18
**Proyecto:** AI Lead Agent Pro — Inmo CRM
**Servicios:** `app/services/appointments/`

---

## 1. Arquitectura General

El sistema de citas tiene **3 componentes principales**:

```
RoundRobinService          ← Asignación de agentes
AppointmentSaga           ← Transacción compensable (creación atómica)
AppointmentService        ← CRUD + sync calendario
  ├─ availability.py      ← Check de disponibilidad
  ├─ google_calendar.py  ← Google Calendar API
  ├─ outlook_calendar.py  ← Microsoft Graph API
  └─ round_robin.py       ← Asignación round-robin / priority
```

---

## 2. Creación de Citas — AppointmentSaga

**Patrón:** Transacción compensable (Saga pattern) para consistencia eventual.

### Pasos

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  1. Reserve │───▶│ 2. Create DB row  │───▶│ 3. Sync Calendar    │
│     slot    │    │   (Appointment)  │    │   (Google/Outlook)  │
└─────────────┘    └──────────────────┘    └─────────────────────┘
                          │                         │
                          │   Si falla paso 2 or 3   │
                          ▼                         ▼
                   ┌──────────────┐          ┌─────────────┐
                   │ Compensate:  │          │Compensate:  │
                   │ Cancel DB row│          │Cancel DB +  │
                   │ Release slot │          │Release slot │
                   └──────────────┘          └─────────────┘
```

### Flujo detallado

```python
saga = AppointmentSaga(db)
appointment_id = await saga.execute(
    lead_id=42,
    broker_id=1,
    start_time=datetime(...),
    duration_minutes=60,
    agent_id=None,  # Asignado por RoundRobinService
)
```

**Step 1: Reserve slot** — `saga._reserve_slot()`
- Llama `check_availability()` para verificar que no hay conflictos
- No persite una fila de slot (reserva blanda)
- Retorna `None` si no se crea fila física

**Step 2: Create DB record** — `saga._create_appointment_record()`
- Llama `AppointmentService.create_appointment()`
- Adquiere `pg_advisory_xact_lock` para prevenir double-booking
- Re-verifica disponibilidad dentro del lock

**Step 3: Sync calendar** — `saga._confirm_calendar_event()`
- Llama `AppointmentService.sync_to_calendar()`
- Si falla → compensación completa

### Compensación

Si cualquier paso falla después de uno anterior exitoso:

| Fallo en | Compensación |
|---|---|
| Step 3 (calendar) | Cancela appointment record + libera slot |
| Step 2 (DB) | Libera slot |
| Step 1 | Ninguna (no hay estado previo) |

---

## 3. Asignación de Agentes — RoundRobinService

### 3.1 Modos de asignación

| Modo | Trigger | Selección |
|---|---|---|
| **Priority** | `broker.priority_assignment_enabled = True` | Agente con menor `assignment_priority` (1 = más prioritario) |
| **Round-robin** | Default | Agente con menos citas en últimos 30 días |

### 3.2 Priority Assignment

```python
# Dos pasadas: primero calendar-connected, luego fallback a todos
for calendar_only in (True, False):
    agents = SELECT ... WHERE
        broker_id = :broker_id
        is_active = True
        role = AGENT
        assignment_priority IS NOT NULL
        [AND google_calendar_connected = True]  # si calendar_only
    ORDER BY assignment_priority ASC
    LIMIT 1
```

- `NULL` en `assignment_priority` = fuera de la cola
- Si ningún agente tiene priority seteado → fallback a round-robin

### 3.3 Round-Robin (least-loaded)

```
1. Agentes con google_calendar_connected = True
      └─ Si no hay: todos los agentes activos
2. Ordenados por appointment count (últimos 30 días) ASC
3. Tie-break: Redis circular index (rotación justa)
```

**Redis-backed rotation:**

```python
# Redis key: f"round_robin:{broker_id}"
# Valor: ID del último agente asignado
#
# Al elegir siguiente:
#  1. Encontrar índice del último agente en la lista de mínimo load
#  2. Seleccionar el siguiente en orden circular
#  3. Si no hay Redis: fallback al primero de la lista
```

**Workload dashboard:**

```
GET /agents/workload → [
  {
    "id": 1,
    "name": "Juan Pérez",
    "email": "juan@broker.cl",
    "appointments_30d": 12,
    "leads_assigned": 34,
    "calendar_connected": true,
    "calendar_id": "juan@gmail.com"
  },
  ...
]
```

---

## 4. Disponibilidad — availability.py

### `check_availability()`

```python
is_available = await check_availability(
    db,
    start_time=datetime,
    end_time=datetime,
    agent_id=int | None,
    exclude_appointment_id=int | None,  # para updates
) -> bool
```

**Retorna `False` si existe conflicto con:**

- `Appointment` con status `SCHEDULED` o `CONFIRMED` que se solape
- `AppointmentBlock` que se solape (vacaciones, meetings, etc.)

**Null agents:** Si `agent_id = NULL` en appointment/block, el slot es compartido y cualquier agente puede tomarlo.

### `get_available_slots()`

Retorna slots disponibles en un rango de fechas para un agente, considerando:
- `AvailabilitySlot` recurring del agente
- `AppointmentBlock` existentes
- `Appointment` confirmadas

---

## 5. Sync con Calendarios — google_calendar.py / outlook_calendar.py

### Google Calendar

```python
GoogleCalendarService(refresh_token?, calendar_id?)
```

**Credenciales (en orden de prioridad):**

1. **Service Account** (`GOOGLE_CREDENTIALS_PATH`) — producción recomendada
2. **OAuth2 refresh token** por broker (`google_refresh_token` en `BrokerPromptConfig`)
3. **Global OAuth2** (`GOOGLE_REFRESH_TOKEN` en settings)

**Métodos:**

| Método | Descripción |
|---|---|
| `create_event(appointment)` | Crea evento en Google Calendar con Meet URL |
| `update_event(event_id, appointment)` | Actualiza fecha/hora del evento |
| `delete_event(event_id)` | Cancela evento |
| `is_ready` | `True` si el cliente API está inicializado |

### Outlook Calendar

`OutlookCalendarService` usa Microsoft Graph API con refresh token por broker (`outlook_refresh_token` en `User`).

---

## 6. Modelo de Datos

### `appointments`

| Columna | Tipo | Notas |
|---|---|---|
| `lead_id` | FK → leads | — |
| `agent_id` | FK → users | Puede ser NULL (asignado después) |
| `appointment_type` | Enum | `PROPERTY_VISIT`, `VIRTUAL_MEETING`, `PHONE_CALL`, `OFFICE_MEETING` |
| `status` | Enum | `SCHEDULED`, `CONFIRMED`, `CANCELLED`, `COMPLETED`, `NO_SHOW` |
| `start_time` | DateTime | Timezone aware (Chile) |
| `end_time` | DateTime | Calculado como `start_time + duration_minutes` |
| `duration_minutes` | Integer | Default 60 |
| `location` | String(500) |Dirección o link |
| `property_address` | String(500) | — |
| `meet_url` | String(500) | Google Meet generado automáticamente |
| `google_event_id` | String(255) | ID del evento en Google Calendar |
| `notes` | Text | Notas internas del agente |
| `lead_notes` | Text | Notas para el lead |
| `reminder_sent_24h` | Boolean | — |
| `reminder_sent_1h` | Boolean | — |
| `cancelled_at` | DateTime | — |
| `cancellation_reason` | Text | — |

### `availability_slots`

Slots recurring de disponibilidad por agente.

| Columna | Tipo | Notas |
|---|---|---|
| `agent_id` | FK → users | NULL = aplica a todos los agentes del broker |
| `day_of_week` | Integer | 0=Lunes … 6=Domingo |
| `start_time`, `end_time` | Time | — |
| `valid_from`, `valid_until` | Date | — |
| `slot_duration_minutes` | Integer | Default 60 |
| `max_appointments_per_slot` | Integer | Default 1 |
| `is_active` | Boolean | — |

### `appointment_blocks`

Bloques de tiempo no disponible (vacaciones, eventos, etc.).

| Columna | Tipo | Notas |
|---|---|---|
| `agent_id` | FK → users | NULL = aplica a todos los agentes |
| `start_time`, `end_time` | DateTime | — |
| `is_recurring` | Boolean | — |
| `recurrence_pattern` | String(100) | ej. `"WEEKLY"` |
| `recurrence_end_date` | Date | — |
| `reason` | String(200) | ej. `"Vacaciones"`, `"Team meeting"` |

---

## 7. Double-Booking Prevention

```python
# Advisory lock PostgreSQL (transaction-scoped)
lock_key1 = agent_id if agent_id else 0
lock_key2 = int(start_time.timestamp()) % 2147483647

SELECT pg_advisory_xact_lock(:k1, :k2)

# Re-check availability INSIDE the lock (atomic with insert)
is_available = await check_availability(db, start_time, end_time, agent_id)
if not is_available:
    raise ValueError("Time slot is not available")
```

**Fallback:** Si la base no es PostgreSQL (ej. SQLite en tests), el lock se omite con warning.

---

## 8. Changelog

| Fecha | Versión | Cambios |
|---|---|---|
| 2026-04-18 | 1.0 | Documento creado. Servicios leídos: `service.py` (496l), `saga.py` (209l), `round_robin.py` (273l), `availability.py` (152l), `google_calendar.py` (358l). |
