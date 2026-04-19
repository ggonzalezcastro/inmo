---
title: "UC-02: Login"
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# UC-02: Login

## Descripción

Un usuario autenticado accede al sistema con sus credenciales.

## Actor Principal

Superadmin, Admin o Agent

## Precondiciones

- El usuario tiene una cuenta registrada
- La cuenta está activa (`is_active=True`)

## Flujo Principal

1. El usuario envía email y contraseña a `POST /auth/login`
2. El sistema busca el usuario por email
3. El sistema verifica la contraseña con bcrypt
4. El sistema genera un JWT con `user_id`, `role`, `broker_id`
5. El sistema retorna `{access_token, token_type}`

## Flujos Alternativos

| ID | Condición | Acción |
|----|-----------|--------|
| FA-1 | Email no encontrado | Retornar 401 "Invalid credentials" |
| FA-2 | Contraseña incorrecta | Retornar 401 "Invalid credentials" |
| FA-3 | Cuenta inactiva | Retornar 403 "Account disabled" |
| FA-4 | Rate limit alcanzado (5/min) | Retornar 429 "Too many requests" |

## Postcondiciones

- JWT emitido con expiración configurable (default 30 min)
- Usuario puede acceder a endpoints protegidos según su rol
