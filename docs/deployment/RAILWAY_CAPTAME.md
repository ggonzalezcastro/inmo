# Railway + Cloudflare para Captame

Configuración de producción validada para:

- Frontend: `https://app.captame.cl`
- Backend: `https://api.captame.cl`
- Healthcheck backend: `https://api.captame.cl/health`

No guardar tokens, secretos ni inventarios de activos Meta en Git.

## Servicio Frontend

Configurar el servicio Railway con:

- Root Directory: `/frontend`
- Config file: `/frontend/railway.toml`
- Builder: Dockerfile
- Healthcheck: `/health`

Variables disponibles durante el build:

```dotenv
VITE_API_URL=https://api.captame.cl
VITE_API_BASE_URL=https://api.captame.cl
```

La imagen usa un build Node reproducible y sirve `dist` desde Nginx. Las rutas
de React Router regresan a `index.html`, por lo que enlaces como
`/my-channels`, `/meta-inbox` y `/meta-ads` pueden abrirse directamente.

## Servicio Backend

Configurar el servicio con el archivo `/railway.json` y estas variables no
secretas:

```dotenv
ENVIRONMENT=production
DEBUG=false
FRONTEND_URL=https://app.captame.cl
WEBHOOK_BASE_URL=https://api.captame.cl
META_OAUTH_REDIRECT_BASE_URL=https://api.captame.cl/api/v1/meta
ALLOWED_ORIGINS=https://app.captame.cl
ALLOWED_HOSTS=api.captame.cl,*.up.railway.app,*.railway.internal
```

Railway proporciona automáticamente sus dominios público y privado al
contenedor. El backend también los incorpora a `TrustedHostMiddleware` para que
los healthchecks internos no dependan del dominio personalizado.

Mantener Backend, Worker y Beat conectados a las mismas referencias compartidas
de PostgreSQL, Redis y variables `META_*`. Beat debe tener una sola réplica.

## URLs que deben registrarse en Meta

OAuth redirects válidos:

```text
https://api.captame.cl/api/v1/meta/connections/whatsapp/callback
https://api.captame.cl/api/v1/meta/connections/instagram/callback
https://api.captame.cl/api/v1/meta/connections/messenger/callback
https://api.captame.cl/api/v1/meta/connections/business/callback
```

Callbacks generales:

```text
Webhook:          https://api.captame.cl/webhooks/meta
Desautorización:  https://api.captame.cl/webhooks/meta/deauthorize
Eliminación:      https://api.captame.cl/webhooks/meta/data-deletion
```

URLs públicas de cumplimiento:

```text
https://app.captame.cl/privacy
https://app.captame.cl/terms
https://app.captame.cl/support
https://app.captame.cl/data-deletion
```

La base OAuth debe terminar en `/api/v1/meta`; el backend añade automáticamente
`/connections/{channel}/callback`.

## Orden de despliegue

1. Desplegar Backend y confirmar que su pre-deploy ejecuta `./migrate.sh`.
2. Confirmar `GET https://api.captame.cl/health` con DB y Redis en `ok`.
3. Desplegar Worker y comprobar `celery inspect ping`.
4. Desplegar una sola réplica de Beat y revisar sus despachos.
5. Desplegar Frontend y comprobar `/health` y una ruta profunda de la SPA.
6. Ejecutar el challenge del webhook Meta.
7. Mantener los feature flags Meta apagados hasta completar las pruebas sandbox.

## Comprobación pública

```bash
curl --fail --show-error https://api.captame.cl/health
curl --fail --show-error https://app.captame.cl/health
curl --fail --show-error https://app.captame.cl/my-channels
```

Para CORS, una petición `OPTIONS` desde `https://app.captame.cl` debe devolver
`Access-Control-Allow-Origin: https://app.captame.cl`.
