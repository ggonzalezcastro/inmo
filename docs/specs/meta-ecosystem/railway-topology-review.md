# Revisión de topología Docker/Railway

**Spec:** META-ECOSYSTEM-001, tarea 12.4
**Fecha:** 2026-09-10
**Estado:** topología local validada; dominios, API, DB, Redis y CORS públicos verificados; Worker, Beat y rollout remoto pendientes.

## Topología objetivo

| Servicio | Proceso | Dependencias | Comprobación |
|---|---|---|---|
| Backend | `uvicorn app.main:app` | PostgreSQL, Redis, volumen `/data` | `GET /health` y conexión WebSocket autenticada |
| Frontend | imagen multi-stage Node/Nginx | Backend público durante build | `GET /health` y fallback SPA |
| Worker | `celery ... worker` | PostgreSQL, Redis DB 0/1/2 | `inspect ping`, tareas registradas y ejecución sin error |
| Beat | `celery ... beat` | Redis DB 1, PostgreSQL para tareas | una sola réplica y despachos programados visibles |
| PostgreSQL | Railway PostgreSQL con pgvector | volumen administrado | conexión desde `/health` y migración `heads` |
| Redis | Railway Redis | almacenamiento administrado | cache DB 0, broker DB 1, resultados DB 2 y Pub/Sub WS |

El repositorio conserva un archivo por proceso porque la configuración Railway
es por servicio, no una definición multi-servicio dentro de un único
`railway.json`:

- Backend: `/railway.json`.
- Worker: `/config/deployment/railway.worker.json`.
- Beat: `/config/deployment/railway.beat.json`.
- Frontend: `/frontend/railway.toml`.

Los dominios productivos son `https://app.captame.cl` para el frontend y
`https://api.captame.cl` para el backend. La matriz exacta de variables y
callbacks está en [RAILWAY_CAPTAME.md](../../deployment/RAILWAY_CAPTAME.md).

Los servicios Worker y Beat deben seleccionar su archivo de configuración
explícitamente en Railway. El Backend usa el archivo raíz y ejecuta
`./migrate.sh` como pre-deploy; las migraciones no se ejecutan desde Worker ni
Beat.

## Variables y almacenamiento

Configurar como referencias compartidas, nunca copiar secretos entre servicios:

- `DATABASE_URL=${{Postgres.DATABASE_URL}}` en Backend, Worker y Beat.
- `REDIS_URL=${{Redis.REDIS_URL}}` en Backend, Worker y Beat.
- `CELERY_BROKER_URL` y `CELERY_RESULT_BACKEND` derivados de Redis con DB 1 y 2.
- `SECRET_KEY` y variables `META_*` como variables compartidas de ambiente.
- `ENVIRONMENT=production`, `DEBUG=false` y orígenes/URLs HTTPS del ambiente.
- Volumen persistente del Backend montado en `/data`, con
  `STORAGE_DRIVER=railway_volume` y `STORAGE_VOLUME_PATH=/data/deals`.

Beat debe tener exactamente una réplica. Backend y Worker pueden escalar; el
WebSocket distribuye eventos entre procesos mediante Redis Pub/Sub.

## Evidencia local ejecutada

- `docker compose config --quiet`: correcto.
- PostgreSQL, Redis y MCP: contenedores healthy.
- `GET /health`: `status=healthy`, DB y Redis `ok`, WebSocket Redis conectado.
- Worker: `inspect ping` correcto y 22 tareas registradas, incluidas las 7 tareas Meta.
- Beat: proceso activo y despachos programados visibles.
- DLQ: índice Redis accesible, con 0 entradas al verificar.
- Migración: contenedor `migrate` terminó con código 0.
- Dominio frontend: `GET https://app.captame.cl/` respondió 200 mediante Cloudflare/Railway.
- Dominio backend: `GET https://api.captame.cl/health` respondió 200 con DB y Redis `ok` y WebSocket conectado a Redis.
- CORS: el preflight desde `https://app.captame.cl` devolvió el origen exacto permitido.
- Imagen frontend nueva: build Docker correcto, `/health` respondió 200, una ruta profunda devolvió la SPA y los assets contienen `https://api.captame.cl` sin la URL Railway heredada.

Durante la prueba, el recálculo de scoring reveló una comparación entre fechas
naive y aware. Se corrigió en `ScoringService` y se agregó una prueba de fecha
UTC consciente de zona horaria.

## Puertas externas pendientes

No se cierra 12.4 hasta ejecutar en el ambiente Railway enlazado:

El 2026-09-09 la CLI local respondió `Unauthorized`. El 2026-09-10 se pudieron
verificar los dominios públicos, pero esta sesión todavía no puede inspeccionar
la configuración interna del proyecto Railway.

1. Confirmar los cinco servicios del cuadro y sus referencias de variables.
2. Confirmar una sola réplica de Beat y volumen `/data` persistente en Backend.
3. Confirmar en el historial del Backend que el pre-deploy ejecutó las migraciones.
4. Comprobar `inspect ping`, tareas registradas y al menos un ciclo de Beat.
5. Abrir un WebSocket autenticado y verificar `connected`, `ping` y un evento real.
6. Consultar la DLQ por el endpoint administrativo y ensayar reintento en staging.
7. Reiniciar Backend, Worker y Redis de forma controlada y confirmar recuperación.

La configuración como código heredada de Railway está deprecada y tiene corte
anunciado para 2026-12-01. El proyecto debe ejecutar `railway config pull` con
una CLI vigente y versionar `.railway/railway.ts` antes de ese límite; esa
migración requiere el proyecto Railway enlazado y no puede inferirse de forma
segura solo desde el repositorio.

## Referencias oficiales

- https://docs.railway.com/config-as-code
- https://docs.railway.com/config-as-code/reference
- https://docs.railway.com/variables
- https://docs.railway.com/deployments/monorepo
