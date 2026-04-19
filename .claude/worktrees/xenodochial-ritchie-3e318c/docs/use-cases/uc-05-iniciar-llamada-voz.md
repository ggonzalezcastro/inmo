---
title: "UC-05: Iniciar Llamada de Voz"
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# UC-05: Iniciar Llamada de Voz

## Descripción

Un agente o el sistema inicia una llamada telefónica a un lead usando IA de voz. El proveedor de voz se selecciona según la configuración del broker.

## Actor Principal

Agent, Admin, Sistema (campaña)

## Precondiciones

- Lead existe con número de teléfono válido
- Proveedor de voz configurado para el broker (VAPI o Bland AI)
- API key del proveedor válida
- Phone number ID configurado (VAPI)

## Flujo Principal

```mermaid
sequenceDiagram
    actor Agent
    participant API
    participant CallSvc as VoiceCallService
    participant Factory as VoiceProviderFactory
    participant Provider as VapiProvider/BlandProvider
    participant ExtAPI as API Externa (VAPI/Bland)
    participant Celery

    Agent->>API: POST /api/v1/calls/initiate {lead_id}
    API->>CallSvc: Iniciar llamada
    CallSvc->>CallSvc: Crear registro VoiceCall
    CallSvc->>Factory: get_voice_provider(broker_id)
    Factory-->>CallSvc: Provider según config
    CallSvc->>Provider: make_call(MakeCallRequest)
    Provider->>ExtAPI: POST /call (API del proveedor)
    ExtAPI-->>Provider: {call_id}
    Provider-->>CallSvc: external_call_id
    CallSvc->>CallSvc: Actualizar VoiceCall con external_call_id

    Note over ExtAPI: Llamada en progreso...

    ExtAPI->>API: POST /webhooks/voice/{provider} (status update)
    API->>Provider: handle_webhook(payload)
    Provider-->>API: WebhookEvent normalizado
    API->>CallSvc: handle_normalized_event(event)
    CallSvc->>CallSvc: Actualizar estado

    ExtAPI->>API: POST /webhooks/voice/{provider} (call ended)
    API->>CallSvc: handle_normalized_event(event)
    CallSvc->>Celery: Encolar generación de transcript
    Celery->>Celery: CallAgentService.generate_summary()
    Celery->>Celery: Actualizar lead score y metadata
```

1. Agente envía `POST /api/v1/calls/initiate` con `lead_id`
2. Se crea registro `VoiceCall` con `status=INITIATED`
3. La factory resuelve el proveedor según config del broker
4. El proveedor realiza la llamada vía su API
5. Se guarda `external_call_id` en el registro
6. Webhooks llegan con actualizaciones de estado
7. Se normalizan a `WebhookEvent` genérico
8. Al completar la llamada, se encola tarea de transcript/summary

## Flujos Alternativos

| ID | Condición | Acción |
|----|-----------|--------|
| FA-1 | Proveedor no disponible | Retornar 503 |
| FA-2 | Teléfono inválido | Retornar 400 |
| FA-3 | Llamada no contestada | Webhook con status NO_ANSWER |
| FA-4 | Llamada fallida | Webhook con status FAILED, log error |

## Postcondiciones

- VoiceCall record creado y actualizado
- Transcripción generada (si la llamada fue contestada)
- Resumen de IA generado
- Score del lead actualizado
- Actividad registrada
