---
title: Requerimientos Funcionales
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# Requerimientos Funcionales

## RF-01: Gestión de Leads

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| RF-01.1 | El sistema debe permitir crear leads con teléfono, nombre, email, tags y metadata | Alta |
| RF-01.2 | El sistema debe normalizar números de teléfono al formato E.164 | Alta |
| RF-01.3 | El sistema debe soportar importación masiva de leads desde CSV | Media |
| RF-01.4 | Los leads deben poder asignarse a agentes específicos | Alta |
| RF-01.5 | Los leads deben tener un score calculado automáticamente (0-100) | Alta |
| RF-01.6 | El scoring debe considerar: datos base, comportamiento, engagement y financiero | Alta |
| RF-01.7 | Los leads deben clasificarse automáticamente como cold/warm/hot según score | Alta |

## RF-02: Pipeline de Ventas

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| RF-02.1 | El pipeline debe tener etapas configurables (entrada, perfilamiento, calificación, agendado, seguimiento, ganado, perdido) | Alta |
| RF-02.2 | Los leads deben avanzar automáticamente de etapa cuando se cumplen condiciones | Alta |
| RF-02.3 | El sistema debe calcular métricas por etapa (conteo, conversión) | Media |
| RF-02.4 | Se debe detectar leads inactivos en una etapa por más de N días | Media |

## RF-03: Comunicación Multicanal

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| RF-03.1 | El sistema debe recibir y responder mensajes de Telegram | Alta |
| RF-03.2 | El sistema debe soportar WhatsApp como canal de comunicación | Alta |
| RF-03.3 | Cada mensaje debe analizarse por LLM para extraer datos del lead | Alta |
| RF-03.4 | Las respuestas deben generarse por LLM con el contexto del broker | Alta |
| RF-03.5 | El historial de mensajes debe persistirse por lead y canal | Alta |

## RF-04: Llamadas de Voz con IA

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| RF-04.1 | El sistema debe iniciar llamadas outbound a leads | Alta |
| RF-04.2 | Se debe soportar múltiples proveedores de voz (VAPI, Bland AI) | Alta |
| RF-04.3 | Los webhooks de cada proveedor deben normalizarse a un formato único | Alta |
| RF-04.4 | Las llamadas deben generar transcripciones y resúmenes por IA | Alta |
| RF-04.5 | Cada broker debe poder configurar su proveedor de voz | Media |

## RF-05: Campañas Automatizadas

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| RF-05.1 | Se deben crear campañas con pasos secuenciales (enviar mensaje, llamar, agendar, mover etapa) | Alta |
| RF-05.2 | Las campañas deben activarse por triggers: manual, score, cambio de etapa, inactividad | Alta |
| RF-05.3 | Los pasos deben poder tener delays configurables (horas) | Media |
| RF-05.4 | Se deben registrar logs de ejecución por lead | Alta |
| RF-05.5 | Se deben generar estadísticas de campañas (enviados, fallidos, tasa de éxito) | Media |

## RF-06: Citas y Calendario

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| RF-06.1 | El sistema debe integrar con Google Calendar para crear eventos con Meet | Alta |
| RF-06.2 | Se debe verificar disponibilidad de agentes antes de agendar | Alta |
| RF-06.3 | Los leads deben poder agendar citas a través del chat (function calling) | Alta |
| RF-06.4 | Las citas deben tener estados: scheduled, confirmed, cancelled, completed, no_show | Alta |

## RF-07: Configuración por Broker

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| RF-07.1 | Cada broker debe poder personalizar el prompt del agente IA | Alta |
| RF-07.2 | Los pesos de scoring de leads deben ser configurables por broker | Media |
| RF-07.3 | La configuración de voz (proveedor, voiceId, modelo) debe ser por broker | Alta |
| RF-07.4 | Se debe poder configurar canales de chat habilitados por broker | Media |

## RF-08: Autenticación y Autorización

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| RF-08.1 | Autenticación JWT con tokens de acceso | Alta |
| RF-08.2 | Roles: SUPERADMIN (global), ADMIN (broker), AGENT (leads asignados) | Alta |
| RF-08.3 | Rate limiting por IP y endpoint | Alta |
| RF-08.4 | Registro de brokers con creación automática de configuración | Alta |

## RF-09: Templates de Mensajes

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| RF-09.1 | CRUD de templates con variables ({{name}}, {{budget}}, etc.) | Media |
| RF-09.2 | Templates por canal (Telegram, WhatsApp, Email, Voz) | Media |
| RF-09.3 | Templates por tipo de agente (perfilador, calificador, agendador, seguimiento) | Media |
