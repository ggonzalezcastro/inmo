---
title: AI Lead Agent Pro - Documentación
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-React-61DAFB)
![Database](https://img.shields.io/badge/database-PostgreSQL-336791)
![License](https://img.shields.io/badge/license-proprietary-red)

# AI Lead Agent Pro

CRM inmobiliario multi-tenant con inteligencia artificial para calificación de leads, comunicación multicanal (Telegram, WhatsApp, voz), pipeline de ventas automatizado y campañas de marketing.

## Tabla de Contenidos

| Sección | Descripción |
|---------|-------------|
| [Arquitectura](architecture/overview.md) | Descripción de la arquitectura general del sistema |
| [Diagramas](architecture/diagrams.md) | Diagramas de arquitectura, ERD, flujo de datos y componentes |
| [Decisiones](architecture/decisions.md) | Architecture Decision Records (ADRs) |
| [Requerimientos Funcionales](requirements/functional.md) | Funcionalidades del sistema |
| [Requerimientos No Funcionales](requirements/non-functional.md) | Rendimiento, seguridad, escalabilidad |
| [Casos de Uso](use-cases/overview.md) | Listado y detalle de casos de uso |
| [API - Overview](api/overview.md) | Descripción general de la API REST |
| [API - Endpoints](api/endpoints.md) | Documentación detallada de endpoints |
| [Guía de Inicio](guides/getting-started.md) | Instalación y configuración |
| [Guía de Desarrollo](guides/development.md) | Guía para desarrolladores |
| [Guía de Despliegue](guides/deployment.md) | Despliegue en producción |
| [Estrategia de Testing](testing/strategy.md) | Plan y cobertura de pruebas |
| [Changelog](changelog/CHANGELOG.md) | Historial de versiones |

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI (Python 3.11+), async/await |
| Frontend | React + Vite, Zustand |
| Base de Datos | PostgreSQL 15 + SQLAlchemy 2.0 (async) |
| Cache | Redis |
| Colas | Celery + Redis |
| LLM | Gemini, Claude, OpenAI (Strategy Pattern) |
| Voz | VAPI, Bland AI (Strategy Pattern) |
| Chat | Telegram, WhatsApp (Strategy Pattern) |
| Calendario | Google Calendar API |
| Auth | JWT + bcrypt |
| Infraestructura | Docker Compose |

## Arquitectura en Resumen

El sistema es una aplicación multi-tenant donde cada **Broker** (inmobiliaria) tiene su propia configuración de IA, pipeline de ventas y canales de comunicación. Los **Leads** se califican automáticamente mediante LLM y se mueven a través de un pipeline de ventas con campañas automatizadas.

```mermaid
flowchart LR
    subgraph channels [Canales]
        TG[Telegram]
        WA[WhatsApp]
        VOZ[Voz AI]
    end
    subgraph core [Core]
        API[FastAPI API]
        LLM[LLM Engine]
        PIPE[Pipeline]
    end
    subgraph data [Data]
        PG[(PostgreSQL)]
        RD[(Redis)]
    end
    channels --> API
    API --> LLM
    API --> PIPE
    API --> PG
    API --> RD
```
