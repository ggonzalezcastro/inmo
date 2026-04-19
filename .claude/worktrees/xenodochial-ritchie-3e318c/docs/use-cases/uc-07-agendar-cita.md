---
title: "UC-07: Agendar Cita"
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# UC-07: Agendar Cita

## Descripción

Se agenda una cita entre un lead y un agente, ya sea manualmente por un agente o automáticamente a través del chat con IA (function calling).

## Actor Principal

Agent, Lead (vía chat IA)

## Precondiciones

- Lead existe en el sistema
- Agente tiene disponibilidad configurada
- Google Calendar integrado (opcional)

## Flujo Principal - Agendamiento Manual

1. Agente consulta slots disponibles: `GET /appointments/available/slots?start_date=...&end_date=...&agent_id=...`
2. El sistema verifica `AvailabilitySlots` menos `Appointments` y `AppointmentBlocks` existentes
3. Agente crea cita: `POST /appointments` con `{lead_id, appointment_type, start_time, agent_id}`
4. El sistema calcula `end_time` según `duration_minutes`
5. Si Google Calendar está configurado, crea evento con link de Google Meet
6. Retorna cita con `status=SCHEDULED` y `meet_url`

## Flujo Principal - Agendamiento vía Chat IA

```mermaid
sequenceDiagram
    actor Lead
    participant Chat as ChatOrchestratorService
    participant LLM as LLMServiceFacade
    participant Tools as AgentToolsService
    participant Appt as AppointmentService
    participant GCal as Google Calendar

    Lead->>Chat: "Quiero agendar una visita"
    Chat->>LLM: Analizar mensaje con tools
    LLM-->>Chat: function_call: check_availability
    Chat->>Tools: check_availability(params)
    Tools->>Appt: get_available_slots()
    Appt-->>Tools: Slots disponibles
    Tools-->>Chat: Slots formateados
    Chat->>LLM: Resultado + historial
    LLM-->>Chat: "Tengo estos horarios: ..."
    Chat-->>Lead: Opciones de horario

    Lead->>Chat: "El martes a las 10"
    Chat->>LLM: Analizar selección con tools
    LLM-->>Chat: function_call: book_appointment
    Chat->>Tools: book_appointment(date, time, type)
    Tools->>Appt: Crear cita
    Appt->>GCal: Crear evento con Meet
    GCal-->>Appt: event_id, meet_url
    Appt-->>Tools: Cita confirmada
    Tools-->>Chat: Detalles de cita
    Chat->>LLM: Confirmar al lead
    LLM-->>Chat: "¡Perfecto! Tu cita queda para el martes..."
    Chat-->>Lead: Confirmación con detalles
```

## Tipos de Cita

| Tipo | Descripción |
|------|-------------|
| `PROPERTY_VISIT` | Visita a propiedad |
| `VIRTUAL_MEETING` | Reunión virtual (Meet) |
| `PHONE_CALL` | Llamada telefónica |
| `OFFICE_MEETING` | Reunión en oficina |
| `OTHER` | Otro |

## Flujos Alternativos

| ID | Condición | Acción |
|----|-----------|--------|
| FA-1 | Sin slots disponibles | Sugerir otros horarios/fechas |
| FA-2 | Google Calendar no configurado | Crear cita sin meet_url |
| FA-3 | Conflicto de horario | Retornar 409 |
| FA-4 | Lead cancela | `POST /appointments/{id}/cancel` con razón |

## Postcondiciones

- Appointment creado con `status=SCHEDULED`
- Evento en Google Calendar (si configurado) con link Meet
- Lead movido a etapa "agendado" en pipeline
- Actividad registrada
