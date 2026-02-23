---
title: API - Overview
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# API Overview

## Base URL

| Entorno | URL |
|---------|-----|
| Local | `http://localhost:8000` |
| Producción | [TODO: URL de producción] |

## Autenticación

Todas las rutas protegidas requieren un JWT en el header `Authorization`:

```
Authorization: Bearer <access_token>
```

El token se obtiene via `POST /auth/login` o `POST /auth/register`.

**Payload del JWT:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sub` | string | User ID |
| `role` | string | Rol: `superadmin`, `admin`, `agent` |
| `broker_id` | int | ID del broker |
| `email` | string | Email del usuario |
| `exp` | int | Timestamp de expiración |

## Roles y Permisos

| Rol | Alcance | Descripción |
|-----|---------|-------------|
| `SUPERADMIN` | Global | Acceso total. Gestiona todos los brokers |
| `ADMIN` | Broker | Administra su broker. Configura IA, campañas, usuarios |
| `AGENT` | Leads asignados | Solo ve y gestiona leads asignados a él |

## Formato de Respuesta

### Éxito

```json
{
  "data": [...],
  "total": 100,
  "skip": 0,
  "limit": 50
}
```

### Error

```json
{
  "detail": "Descripción del error"
}
```

## Paginación

| Parámetro | Tipo | Default | Max | Descripción |
|-----------|------|---------|-----|-------------|
| `skip` | int | 0 | - | Registros a saltar |
| `limit` | int | 50 | 200 | Máximo de registros |

## Rate Limiting (Producción)

| Endpoint | Límite |
|----------|--------|
| General | 60 req/min |
| `POST /auth/login` | 5 req/min |
| `POST /auth/register` | 3 req/hora |

Headers de respuesta:
- `X-RateLimit-Limit`: Límite total
- `X-RateLimit-Remaining`: Peticiones restantes
- `X-RateLimit-Reset`: Timestamp de reset

## Grupos de Endpoints

| Grupo | Prefijo | Descripción |
|-------|---------|-------------|
| Auth | `/auth` | Registro y login |
| Leads | `/api/v1/leads` | CRUD de leads |
| Chat | `/api/v1/chat` | Mensajería y chat |
| Voice | `/api/v1/calls` | Llamadas de voz |
| Appointments | `/api/v1/appointments` | Citas y calendario |
| Campaigns | `/api/v1/campaigns` | Campañas automatizadas |
| Pipeline | `/api/v1/pipeline` | Pipeline de ventas |
| Templates | `/api/v1/templates` | Templates de mensajes |
| Broker Config | `/api/broker/config` | Configuración del broker |
| Broker Users | `/api/broker/users` | Gestión de usuarios |
| Brokers | `/api/brokers` | Gestión de brokers |
| Webhooks | `/webhooks` | Webhooks de proveedores |
| Telegram | `/api/v1/telegram` | Config de Telegram |

## Documentación Interactiva

FastAPI genera documentación automática:
- **Swagger UI**: `GET /docs`
- **ReDoc**: `GET /redoc`
- **OpenAPI JSON**: `GET /openapi.json`
