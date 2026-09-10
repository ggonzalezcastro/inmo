# Revisión de seguridad local: Ecosistema Meta

**Spec ID:** META-ECOSYSTEM-001
**Fecha:** 2026-09-07
**Alcance:** código local de Meta, rutas compartidas de WhatsApp usadas durante la migración, esquemas públicos y configuración versionada.
**Resultado:** aprobada para el alcance local; **0 hallazgos críticos abiertos y 0 hallazgos altos abiertos**.

Esta revisión es una auditoría estática y de pruebas dirigidas. No reemplaza una prueba de penetración, la validación de secretos reales en Railway ni las pruebas contra activos sandbox de Meta.

## Checklist

| Control | Resultado | Evidencia principal |
|---|---|---|
| Aislamiento por broker | Aprobado | Rutas autenticadas derivan `broker_id` de claims; conexiones, activos, bandeja, Ads, Lead Ads y conversiones aplican alcance por broker. Se reforzaron las uniones de conversión y la deduplicación Lead Ads. |
| Credenciales y respuestas | Aprobado | Tokens cifrados con clave dedicada, esquemas públicos sin campos de credenciales y errores Graph con redacción defensiva. |
| Escaneo de secretos | Aprobado en árbol actual | `scripts/check_security.sh` pasó y el barrido dirigido no encontró claves privadas ni credenciales Meta, AWS, Google u OpenAI inesperadas en fuente/configuración actual. No se imprimieron valores durante la revisión. |
| Logs | Aprobado | Las rutas Meta no registran tokens ni cuerpos de webhook. El fallback WhatsApp dejó de registrar teléfonos, texto de mensajes y cuerpos de error del proveedor. |
| SSRF y multimedia | Aprobado para la arquitectura actual | La paginación Graph acepta URL absoluta solo en `https://graph.facebook.com:443`; Ads y adjuntos salientes rechazan HTTP, credenciales embebidas, hosts locales, nombres internos e IP no global. El CRM no descarga los adjuntos: entrega la URL a Meta. |
| Replay OAuth | Aprobado | Estado JWT con propósito, expiración y nonce; consumo atómico mediante `GETDEL` o Lua y rechazo seguro si el cliente Redis no ofrece una primitiva atómica. |
| Firmas y callbacks | Aprobado | HMAC SHA-256 constante sobre el cuerpo crudo, producción falla cerrada sin secreto y los callbacks de baja/eliminación validan `signed_request`. |
| Webhook durable y privacidad | Aprobado | Firma antes de persistir/encolar, clave idempotente, payload bruto cifrado y expiración programada a siete días. |
| Rate limiting | Aprobado | Límite por activo y remitente con claves que contienen solo hash del remitente; límites del proveedor permanecen como respaldo. |

## Hallazgos corregidos

| ID | Severidad original | Hallazgo | Corrección |
|---|---|---|---|
| SEC-META-001 | Alta | `paging.next` podía dirigir una solicitud autenticada a otro host HTTPS. | Lista permitida exacta para Graph, sin credenciales URL ni puertos alternativos; prueba demuestra que el segundo host nunca recibe una solicitud. |
| SEC-META-002 | Alta | El fallback global de WhatsApp podía elegir arbitrariamente un broker cuando había más de uno habilitado. | El fallback solo opera con un candidato único y rechaza cualquier resolución ambigua; la deduplicación legacy ahora incluye `broker_id`. |
| SEC-META-003 | Alta | El fallback OAuth `GET` seguido de `DELETE` permitía una carrera de replay. | Lua atómico como alternativa a `GETDEL`; si ninguna operación atómica existe, el callback falla cerrado. |
| SEC-META-004 | Alta | Una referencia inconsistente de negocio podía combinar un deal con lead o propiedad de otro broker antes de enviar una conversión. | Las uniones exigen igualdad de `broker_id` para deal, lead y propiedad; la recuperación deduplicada de Lead Ads también valida broker. |
| SEC-META-005 | Media | El camino legacy de WhatsApp registraba teléfono, fragmento del mensaje y cuerpo de error remoto. | Logs reducidos a IDs técnicos, estados, longitudes y tipos de excepción. |
| SEC-META-006 | Media | La validación de adjuntos salientes comprobaba solo el prefijo `https://`. | Validador compartido de URL HTTPS pública aplicado a Ads y bandeja. |

Todos los hallazgos altos identificados durante esta revisión quedaron corregidos antes del cierre.

## Evidencia ejecutada

```text
DEBUG=false backend/.venv/bin/pytest -q \
  backend/tests/services/test_meta_foundation.py \
  backend/tests/services/test_meta_ads.py \
  backend/tests/services/test_meta_normalization.py

49 passed

DEBUG=false backend/.venv/bin/python -m pytest -q \
  backend/tests/features/test_whatsapp_webhook.py --noconftest

5 passed

./scripts/check_security.sh
Verificacion de seguridad completada
```

El barrido estático adicional revisó patrones de claves privadas, AWS, Google, OpenAI y tokens Meta en el árbol actual, excluyendo dependencias, builds, lockfiles y el `.env` local ignorado; `.env.example` se verificó por separado y contiene solo contratos/placeholders.

## Límites y condiciones externas

- Los secretos Meta reales todavía deben aprovisionarse y validarse por ambiente; corresponde a la tarea 0.6 y a la validación de topología 12.4.
- El historial Git contiene archivos candidatos antiguos ajenos al módulo Meta (`.env.bak`, benchmarks y bundles generados). La verificación existente ya exige confirmar rotación y purga si esos valores fueron reales. No hay copias equivalentes en el árbol actual, pero esa confirmación sigue siendo una compuerta general de despliegue.
- Si en el futuro el backend descarga multimedia, el nuevo cliente deberá resolver y fijar una IP pública, limitar redirecciones, tamaño, tiempo, MIME y extensión. La implementación revisada no contiene una descarga de servidor.
- Firmas, OAuth y permisos deben validarse nuevamente con secretos y activos reales durante sandbox/App Review.
