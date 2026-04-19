---
title: "UC-06: Crear y Ejecutar Campaña"
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# UC-06: Crear y Ejecutar Campaña

## Descripción

Un administrador crea una campaña de marketing con pasos automatizados y la aplica a leads del pipeline.

## Actor Principal

Admin

## Precondiciones

- Usuario con rol ADMIN autenticado
- Al menos un lead en el pipeline del broker

## Flujo Principal - Crear Campaña

1. Admin envía `POST /api/v1/campaigns` con nombre, canal, trigger
2. El sistema crea la campaña con `status=DRAFT`
3. Admin agrega pasos con `POST /api/v1/campaigns/{id}/steps`:
   - `step_number`, `action` (send_message/make_call/schedule_meeting/update_stage)
   - `delay_hours`, `message_template_id`, `conditions`
4. Admin activa la campaña (cambiar status a ACTIVE)

## Flujo Principal - Ejecutar Campaña

```mermaid
flowchart TD
    A[Admin: Aplicar campaña a lead] --> B[POST /campaigns/{id}/apply-to-lead/{lead_id}]
    B --> C{Verificar trigger conditions}
    C -->|No cumple| D[Skip - Log reason]
    C -->|Cumple| E[Obtener steps ordenados]
    E --> F{Para cada step}
    F --> G{Acción del step}
    G -->|SEND_MESSAGE| H[Renderizar template → Enviar por canal]
    G -->|MAKE_CALL| I[Iniciar llamada de voz]
    G -->|SCHEDULE_MEETING| J[Crear cita]
    G -->|UPDATE_STAGE| K[Mover lead de etapa]
    H --> L[Log: status=sent]
    I --> L
    J --> L
    K --> L
    L --> M{Más steps?}
    M -->|Sí + delay| N[Esperar delay_hours]
    N --> F
    M -->|No| O[Campaña completada para lead]
```

1. Admin aplica campaña a un lead: `POST /campaigns/{id}/apply-to-lead/{lead_id}`
2. El sistema verifica las condiciones de trigger
3. Celery ejecuta cada step secuencialmente con delays
4. Cada acción se ejecuta y se loguea el resultado

## Triggers Automáticos

| Trigger | Condición |
|---------|-----------|
| `LEAD_SCORE` | Score del lead supera umbral configurado |
| `STAGE_CHANGE` | Lead cambia a una etapa específica |
| `INACTIVITY` | Lead inactivo por N días |
| `MANUAL` | Aplicación manual por admin |

## Flujos Alternativos

| ID | Condición | Acción |
|----|-----------|--------|
| FA-1 | Template no encontrado | Log status=FAILED, continuar siguiente step |
| FA-2 | Llamada falla | Log status=FAILED, continuar |
| FA-3 | Lead ya contactado por misma campaña | Log status=SKIPPED |
| FA-4 | max_contacts alcanzado | No ejecutar más |

## Postcondiciones

- Campaign logs creados para cada step ejecutado
- Acciones ejecutadas (mensajes enviados, llamadas realizadas, etc.)
- Estadísticas actualizadas (sent, failed, skipped)
