---
title: "UC-03: Gestionar Leads"
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# UC-03: Gestionar Leads

## Descripción

Administradores y agentes crean, consultan, actualizan y gestionan leads en el sistema.

## Actor Principal

Admin, Agent

## Precondiciones

- Usuario autenticado con rol ADMIN o AGENT
- Para AGENT: solo ve leads asignados a él

## Flujo Principal - Crear Lead

1. Admin envía `POST /api/v1/leads` con `{phone, name, email, tags, metadata}`
2. El sistema normaliza el número de teléfono a formato E.164
3. El sistema verifica duplicados por teléfono dentro del broker
4. El sistema crea el lead con `status=cold`, `lead_score=0`, `pipeline_stage=entrada`
5. El sistema calcula score inicial
6. El sistema retorna el lead creado

## Flujo Principal - Listar Leads

1. Usuario envía `GET /api/v1/leads?status=warm&search=...&pipeline_stage=...`
2. El sistema filtra por broker (ADMIN) o por asignación (AGENT)
3. El sistema retorna lista paginada con `{data, total, skip, limit}`

## Flujo Principal - Importar CSV

1. Admin sube archivo CSV a `POST /api/v1/leads/bulk-import`
2. El sistema procesa cada fila: normaliza teléfono, detecta duplicados
3. El sistema retorna conteo de `{imported, duplicates, invalid}`

## Flujo Principal - Asignar Lead

1. Admin envía `PUT /api/v1/leads/{id}/assign` con `{agent_id}`
2. El sistema verifica que el agente pertenece al mismo broker
3. El sistema actualiza `assigned_to` y registra actividad

## Flujos Alternativos

| ID | Condición | Acción |
|----|-----------|--------|
| FA-1 | Teléfono duplicado | Retornar lead existente o contabilizar duplicado (CSV) |
| FA-2 | Lead no encontrado | Retornar 404 |
| FA-3 | Sin permisos | Retornar 403 |
| FA-4 | Agent intenta ver lead no asignado | Retornar 403 |

## Postcondiciones

- Lead creado/actualizado en BD
- Score calculado
- Actividad registrada en activity_log
