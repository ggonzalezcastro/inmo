---
title: Architecture Decision Records
version: 1.1.0
date: 2026-02-22
author: Equipo Inmo
---

# Architecture Decision Records (ADRs)

## ADR-001: Async FastAPI con SQLAlchemy 2.0

**Estado:** Aceptada  
**Fecha:** 2025-01-01  
**Contexto:** Se necesita alta concurrencia para manejar webhooks de múltiples proveedores de chat y voz simultáneamente.  
**Decisión:** Usar FastAPI con SQLAlchemy 2.0 async (asyncpg) para todo el backend.  
**Consecuencias:** Mayor rendimiento en I/O, pero requiere disciplina con session management async.

## ADR-002: Strategy Pattern para Proveedores de LLM

**Estado:** Aceptada  
**Fecha:** 2025-01-15  
**Contexto:** Se necesita flexibilidad para cambiar entre modelos de lenguaje (costo, disponibilidad, capacidades).  
**Decisión:** Implementar `BaseLLMProvider` ABC con factory pattern. Proveedores: Gemini, Claude, OpenAI.  
**Consecuencias:** Se puede cambiar el proveedor por variable de entorno sin cambios de código. La `LLMServiceFacade` mantiene retrocompatibilidad.

## ADR-003: Strategy Pattern para Proveedores de Voz

**Estado:** Aceptada  
**Fecha:** 2026-02-21  
**Contexto:** El sistema estaba acoplado a VAPI. Se necesita soporte para múltiples proveedores de voz.  
**Decisión:** Replicar el patrón de LLM: `BaseVoiceProvider` ABC con factory y registry. Tipos normalizados (`WebhookEvent`, `MakeCallRequest`). Proveedores: VAPI, Bland AI.  
**Consecuencias:** Cada broker puede elegir su proveedor de voz. Webhooks normalizados permiten lógica de negocio agnóstica.

## ADR-004: Multi-Tenancy por Broker

**Estado:** Aceptada  
**Fecha:** 2025-01-01  
**Contexto:** Múltiples inmobiliarias usan el sistema con configuraciones independientes.  
**Decisión:** Multi-tenancy a nivel de registros con `broker_id` en las tablas principales. Roles RBAC: SUPERADMIN, ADMIN, AGENT.  
**Consecuencias:** Simplicidad de despliegue (una instancia), pero requiere filtrado cuidadoso en queries.

## ADR-005: Celery para Tareas en Background

**Estado:** Aceptada  
**Fecha:** 2025-01-10  
**Contexto:** Procesamiento de mensajes de Telegram, ejecución de campañas y generación de transcripciones son operaciones lentas.  
**Decisión:** Celery con Redis como broker para tareas asíncronas.  
**Consecuencias:** Mejor UX (respuesta rápida de webhooks), pero añade complejidad operacional (worker + beat).

## ADR-006: Redis para Cache y Rate Limiting

**Estado:** Aceptada  
**Fecha:** 2025-01-10  
**Contexto:** El contexto de leads y la configuración de brokers se consultan frecuentemente.  
**Decisión:** Redis para cache (TTL-based) y rate limiting (sliding window).  
**Consecuencias:** Reduce carga en PostgreSQL, pero añade Redis como dependencia de infraestructura.

## ADR-007: Zustand para Estado Frontend

**Estado:** Aceptada  
**Fecha:** 2025-01-01  
**Contexto:** Se necesita gestión de estado simple y eficiente para React.  
**Decisión:** Zustand en vez de Redux por su simplicidad y menor boilerplate.  
**Consecuencias:** Stores individuales por dominio, fácil de testear y mantener.

## ADR-008: Reorganización de Services en Subdirectorios

**Estado:** Aceptada
**Fecha:** 2026-02-21
**Contexto:** 23 archivos sueltos en `services/` (15 facades, 3 duplicados, 5 únicos) causaban confusión.
**Decisión:** Organizar por dominio en subdirectorios. Eliminar facades y duplicados. Crear `shared/` para servicios transversales.
**Consecuencias:** 0 archivos sueltos en la raíz. Imports directos a subpaquetes.

## ADR-009: Sistema Multi-Agente con Feature Flag

**Estado:** Aceptada
**Fecha:** 2026-02-22
**Contexto:** El `ChatOrchestratorService` monolítico maneja calificación, agendamiento y seguimiento en un solo agente, causando conflictos de instrucciones en casos edge.
**Decisión:** Implementar agentes especializados (`QualifierAgent`, `SchedulerAgent`, `FollowUpAgent`) coordinados por `AgentSupervisor`. Activar con feature flag `MULTI_AGENT_ENABLED=true` para rollout progresivo.
**Consecuencias:** Agentes más predecibles y testeables de forma aislada. El sistema existente sigue funcionando sin cambios. La regla DICOM se aplica en el agente más temprano posible (Qualifier) en vez de en el prompt monolítico.

## ADR-010: Eval Framework Determinista + LLM-Judge Opcional

**Estado:** Aceptada
**Fecha:** 2026-02-22
**Contexto:** Se necesita verificar la calidad del agente IA (adherencia a reglas de negocio, completitud de tareas) en CI sin incurrir en costos de API.
**Decisión:** Dos niveles: (1) métricas deterministas con regex (`DicomRuleMetric`, `TaskCompletionMetric`) que siempre corren; (2) métricas LLM-judge (`deepeval`) opcionales via `EVAL_LLM_ENABLED=true`.
**Consecuencias:** CI siempre verifica las reglas críticas de negocio sin costos externos. El LLM-judge se usa solo en revisiones manuales o pipelines de staging.

## ADR-011: Dead Letter Queue en Redis para Celery

**Estado:** Aceptada
**Fecha:** 2026-02-22
**Contexto:** Las tareas Celery que fallan repetidamente se pierden silenciosamente (solo logs). No hay mecanismo para reintentar manualmente ni auditar fallos acumulados.
**Decisión:** Implementar `DLQTask` como clase base para todas las tareas. Los fallos finales se persisten en Redis con metadatos completos (traceback, args, retry count). Endpoints admin para gestión.
**Consecuencias:** Visibilidad completa de fallos. Reintento/descarte manual desde la UI admin. Overhead mínimo: solo se activa en `on_failure` tras agotar reintentos.

## ADR-012: pgvector para Knowledge Base RAG

**Estado:** Aceptada
**Fecha:** 2026-02-22
**Contexto:** El agente necesita acceder a información específica del broker (proyectos, precios, políticas) que no cabe en el system prompt.
**Decisión:** Extensión `pgvector` en PostgreSQL existente. Embeddings de 768 dimensiones con Gemini `text-embedding-004`. Búsqueda por similitud coseno con índice `IVFFlat`.
**Consecuencias:** Sin nueva infraestructura (mismo PostgreSQL). Los embeddings son específicos por broker. Latencia de búsqueda semántica ~5-20ms con el índice.
