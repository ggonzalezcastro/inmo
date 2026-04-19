---
title: "UC-08: Configurar Broker"
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# UC-08: Configurar Broker

## Descripción

Un administrador personaliza la configuración de su inmobiliaria: prompt del agente IA, scoring de leads y proveedor de voz.

## Actor Principal

Admin

## Precondiciones

- Usuario con rol ADMIN autenticado
- Broker con configuración inicializada (ocurre automáticamente al registrar)

## Flujo Principal - Configurar Prompt IA

1. Admin consulta configuración actual: `GET /api/broker/config`
2. Admin actualiza prompt: `PUT /api/broker/config/prompt`
   - `agent_name`: Nombre del agente (default: "Sofía")
   - `agent_role`: Rol del agente (default: "asesora inmobiliaria")
   - `identity_prompt`: Personalidad y tono
   - `business_context`: Contexto del negocio, propiedades, ubicaciones
   - `behavior_rules`: Reglas de comportamiento
   - `restrictions`: Restricciones del agente
3. Admin puede previsualizar: `GET /api/broker/config/prompt/preview`

## Flujo Principal - Configurar Scoring

1. Admin actualiza scoring: `PUT /api/broker/config/leads`
   - `field_weights`: Pesos por campo (`{name: 10, phone: 15, budget: 20, ...}`)
   - `cold_max_score`: Score máximo para "cold" (default: 20)
   - `warm_max_score`: Score máximo para "warm" (default: 50)
   - `hot_min_score`: Score mínimo para "hot" (default: 50)
   - `qualified_min_score`: Score mínimo para "qualified" (default: 75)
   - Alertas: `alert_on_hot_lead`, `alert_score_threshold`, `alert_email`

## Parámetros Configurables

| Categoría | Parámetro | Default |
|-----------|-----------|---------|
| Identidad | `agent_name` | "Sofía" |
| Identidad | `agent_role` | "asesora inmobiliaria" |
| Scoring | `field_weights.name` | 10 |
| Scoring | `field_weights.phone` | 15 |
| Scoring | `field_weights.email` | 10 |
| Scoring | `field_weights.location` | 15 |
| Scoring | `field_weights.budget` | 20 |
| Scoring | `cold_max_score` | 20 |
| Scoring | `warm_max_score` | 50 |
| Scoring | `hot_min_score` | 50 |
| Scoring | `qualified_min_score` | 75 |
| Voz | `provider` | "vapi" |
| Citas | `enable_appointment_booking` | true |

## Flujos Alternativos

| ID | Condición | Acción |
|----|-----------|--------|
| FA-1 | Config no existe | BrokerInitService la crea con defaults |
| FA-2 | Superadmin modifica otro broker | Debe pasar `broker_id` como query param |
| FA-3 | Valores de scoring inconsistentes | Validación en servicio |

## Postcondiciones

- Configuración actualizada en BD
- Cache de configuración invalidada en Redis
- Próximas interacciones usan nueva configuración
