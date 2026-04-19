---
title: Requerimientos No Funcionales
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# Requerimientos No Funcionales

## RNF-01: Rendimiento

| ID | Requerimiento | Métrica |
|----|---------------|---------|
| RNF-01.1 | Tiempo de respuesta de API < 500ms para endpoints CRUD | p95 < 500ms |
| RNF-01.2 | Procesamiento de webhooks < 2s | p95 < 2s |
| RNF-01.3 | Cache hit rate > 80% para contexto de leads | > 80% |
| RNF-01.4 | Connection pooling de BD con pool_size=20, max_overflow=40 | Configurado |

## RNF-02: Seguridad

| ID | Requerimiento | Implementación |
|----|---------------|----------------|
| RNF-02.1 | Autenticación JWT con SECRET_KEY >= 32 caracteres | Validado en producción |
| RNF-02.2 | Contraseñas hasheadas con bcrypt | passlib + bcrypt |
| RNF-02.3 | Rate limiting: 60 req/min general, 5/min login, 3/hora registro | Redis sliding window |
| RNF-02.4 | CORS configurado con orígenes permitidos | Configurable por env var |
| RNF-02.5 | HTTPS redirect en producción | TrustedHostMiddleware |
| RNF-02.6 | Validación de webhooks por token secreto (Telegram) | Header verification |
| RNF-02.7 | Input sanitization (HTML en mensajes de chat) | Bleach/strip |
| RNF-02.8 | Password validation: min 8 chars, uppercase, lowercase, digit | Pydantic validator |

## RNF-03: Escalabilidad

| ID | Requerimiento | Estrategia |
|----|---------------|-----------|
| RNF-03.1 | Soporte para múltiples brokers concurrentes | Multi-tenancy por broker_id |
| RNF-03.2 | Tareas pesadas ejecutadas en background | Celery workers (escalable horizontalmente) |
| RNF-03.3 | Base de datos preparada para índices de performance | Índices compuestos en leads, campaigns, voice_calls |
| RNF-03.4 | Cache distribuido para contexto y configuración | Redis con TTL |

## RNF-04: Disponibilidad

| ID | Requerimiento | Estrategia |
|----|---------------|-----------|
| RNF-04.1 | Health check endpoint `/health` con verificación de BD y Redis | Implementado |
| RNF-04.2 | Webhooks retornan 200 incluso en errores internos | Evita retries infinitos de proveedores |
| RNF-04.3 | Graceful degradation si Redis no está disponible | Cache bypass, operación sin cache |
| RNF-04.4 | Error handling global que oculta detalles internos en producción | Exception handler en main.py |

## RNF-05: Mantenibilidad

| ID | Requerimiento | Implementación |
|----|---------------|----------------|
| RNF-05.1 | Código organizado por dominio (services/, routes/, models/) | Subdirectorios por dominio |
| RNF-05.2 | Proveedores intercambiables sin cambios en lógica de negocio | Strategy + Factory pattern |
| RNF-05.3 | Migraciones de base de datos versionadas | Alembic |
| RNF-05.4 | Configuración externalizada en variables de entorno | Pydantic Settings |

## RNF-06: Observabilidad

| ID | Requerimiento | Implementación |
|----|---------------|----------------|
| RNF-06.1 | Logging estructurado con niveles (DEBUG, INFO, WARNING, ERROR) | Python logging |
| RNF-06.2 | Audit log de acciones de usuario | Tabla audit_logs |
| RNF-06.3 | Activity log por lead | Tabla activity_log |
| RNF-06.4 | [TODO: Integración con servicio de monitoreo (Sentry, DataDog)] | Pendiente |
