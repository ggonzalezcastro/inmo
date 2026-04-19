# Documentación AI Lead Agent Pro

Sistema CRM de agentes IA para corretaje inmobiliario

> Última actualización: 2026-04-18

## Arquitectura

- [[arquitectura/overview]] — Visión general del sistema
- [[arquitectura/multi-agente]] — Sistema multi-agente (Supervisor + agentes)
- [[arquitectura/handoff-flows]] — Flujos de transferencia entre agentes
- [[arquitectura/pipeline-states]] — Pipeline de leads y estados
- [[arquitectura/llm-layer]] — Capa de LLM (Gemini/Claude/OpenAI)
- [[arquitectura/escalation]] — Sistema de sentiment y escalación
- [[arquitectura/human-handoff]] — Toma de control por agente humano
- [[arquitectura/websockets]] — Comunicación en tiempo real
- [[arquitectura/channels]] — Canales de mensajería (Telegram, WhatsApp, Webchat)
- [[arquitectura/auth]] — Autenticación y autorización
- [[arquitectura/broker-config]] — Configuración por broker
- [[arquitectura/knowledge-base]] — Knowledge Base y RAG
- [[arquitectura/scoring]] — Sistema de puntaje de leads
- [[arquitectura/voice]] — Integración de voz (VAPI)
- [[arquitectura/celery-tasks]] — Tareas asíncronas (Celery)
- [[arquitectura/observability]] — Observabilidad y monitoring

## Base de Datos

- [[arquitectura/database-schema]] — Esquema completo de PostgreSQL

## Agentes

- [[agentes/qualifier-agent]] — Agente de calificación
- [[agentes/scheduler-agent]] — Agente de agendamiento
- [[agentes/follow-up-agent]] — Agente de seguimiento

## API

- [[api/endpoints]] — Referencia completa de endpoints REST

## Frontend

- [[frontend/structure]] — Estructura del frontend (React, Zustand, Router)

## Guías

- [[guides/getting-started]] — Guía de inicio rápido para nuevos desarrolladores
- [[guides/development]] — Workflow de desarrollo
- [[guides/ENV_VARIABLES]] — Variables de entorno completas
- [[guides/USAGE_GUIDE]] — Guía de uso del sistema
- [[guides/GOOGLE_CALENDAR_SETUP]] — Configuración de Google Calendar
- [[guides/VAPI_QUICKSTART]] — Quickstart de VAPI

## Decisiones Arquitectónicas

- [[decisiones/ADR-001-postgresql-pgvector]] — PostgreSQL + pgvector
- [[decisiones/ADR-002-gemini-primary]] — Gemini como LLM primario
- [[decisiones/ADR-003-multi-agente-supervisor]] — Patrón Supervisor
- [[decisiones/ADR-004-lead-metadata-jsonb]] — lead_metadata JSONB
- [[decisiones/ADR-005-celery-redis]] — Celery + Redis
- [[decisiones/ADR-006-zustand]] — Zustand para state management
- [[decisiones/ADR-007-tool-based-handoffs]] — Handoffs basados en tools
- [[decisiones/ADR-008-gemini-context-cache]] — Context Caching
- [[decisiones/ADR-009-sync-sentiment-gate]] — Sentiment gate síncrono
- [[decisiones/ADR-010-advisory-locks]] — Advisory locks

## Issues

- [[bugs-conocidos]] — Bugs y TODOs conocidos

## Changelog

### 2026-04-18

- Agregada sección de Guías con getting-started, development, ENV_VARIABLES
- Agregada referencia a arquitectura/observability
- Actualización de índice con todas las guías disponibles

### 2026-04-17

- Creación del archivo README principal del vault de documentación
- Organización de la documentación en categorías: Arquitectura, Agentes, API, Frontend, Decisiones Arquitectónicas e Issues
- Inclusión de referencias a documentos de arquitectura del sistema multi-agente
- Inclusión de referencias a ADRs (Architecture Decision Records)
