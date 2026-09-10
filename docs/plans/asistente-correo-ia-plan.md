# Plan completo: asistente de correo con IA para leads

**Guardado:** 2026-08-26
**Complejidad estimada:** Alta
**Duración estimada del piloto:** 5 a 8 semanas

## Resumen

La primera versión permitirá que cada ejecutivo conecte Gmail y/o Outlook, reciba un resumen diario, genere borradores y apruebe tareas sugeridas por la IA.

Decisiones acordadas:

- Piloto interno para los ejecutivos de la empresa.
- Google limitado a un único Google Workspace.
- Outlook limitado a una única organización Microsoft.
- Importación inicial de los últimos 30 días.
- Sincronización cada 15 minutos.
- Resumen diario a las 08:30 de Chile y actualización manual.
- Solo se analizarán correos que coincidan con el email de un lead asignado.
- Las tareas siempre requerirán aprobación.
- Los correos redactados por IA siempre requerirán revisión antes de enviarse.
- Jefatura verá métricas, pero no asuntos, cuerpos ni resúmenes privados.
- No se procesarán archivos adjuntos en la primera versión.
- Gmail y Outlook tendrán conexiones separadas de las conexiones actuales de calendario.

## 1. Configuración que debes realizar

### A. Preparar Google Workspace

Necesitarás acceso como administrador de Google Workspace y permiso para crear proyectos dentro de la organización de Google Cloud.

Si al configurar la audiencia no aparece la opción “Interna”, significa que el proyecto no fue creado dentro de la organización asociada al Workspace.

### B. Crear los proyectos en Google Cloud

Crear dos proyectos independientes de los utilizados actualmente por Google Calendar:

1. `inmo-correo-desarrollo`
2. `inmo-correo-produccion`

Separar correo y calendario evita que los permisos restringidos de Gmail afecten la conexión actual del calendario. Google también recomienda separar los proyectos de desarrollo y producción.

Para cada proyecto:

1. Entrar a Google Cloud Console.
2. Seleccionar la organización de Google Workspace.
3. Ir a “IAM y administración”.
4. Seleccionar “Crear un proyecto”.
5. Asignar el nombre correspondiente.
6. Registrar un correo administrativo como contacto del proyecto.
7. Mantener un número reducido de propietarios y editores.

### C. Activar Gmail API

En cada proyecto:

1. Abrir “APIs y servicios”.
2. Entrar a “Biblioteca”.
3. Buscar “Gmail API”.
4. Seleccionarla.
5. Presionar “Habilitar”.

No será necesario habilitar Cloud Pub/Sub en esta versión, porque la sincronización se realizará cada 15 minutos mediante Celery.

### D. Configurar Google Auth Platform

En cada proyecto:

1. Abrir “Google Auth Platform”.
2. Presionar “Get started” o “Comenzar”.
3. En “Branding”, configurar:

   - Nombre oficial del CRM.
   - Correo de soporte.
   - Logo oficial, si está disponible.
   - Correo de contacto técnico.

4. En “Audience”, seleccionar “Internal”.
5. No publicar la aplicación como externa durante el piloto.
6. En “Data Access”, agregar únicamente:

   - `openid`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`

`gmail.readonly` permite analizar mensajes y `gmail.send` permite enviar solamente después de la confirmación del ejecutivo. No se solicitarán `gmail.modify`, `gmail.compose` ni acceso completo a la cuenta. Google clasifica la lectura de Gmail como acceso restringido y el envío como sensible. Consulta los [scopes oficiales de Gmail](https://developers.google.com/workspace/gmail/api/auth/scopes).

### E. Crear los clientes OAuth de Google

En “Google Auth Platform → Clients”:

1. Presionar “Create client”.
2. Seleccionar “Web application”.
3. Usar el nombre `Inmo CRM Correo`.
4. No agregar orígenes JavaScript: el intercambio de tokens ocurrirá en el backend.
5. En desarrollo agregar esta URI exacta:

   `http://localhost:8000/api/v1/mail/google/callback`

6. En producción agregar:

   `https://<DOMINIO_BACKEND_RAILWAY>/api/v1/mail/google/callback`

7. No agregar ni eliminar barras finales distintas de las utilizadas por el backend.
8. Crear el cliente.
9. Copiar inmediatamente el Client ID y Client Secret.
10. Guardarlos en un administrador de contraseñas y en Railway.

Google actualmente muestra el secreto completo al crearlo y puede no permitir recuperarlo posteriormente. Consulta la [gestión oficial de clientes OAuth](https://support.google.com/cloud/answer/15549257).

### F. Autorizar la aplicación en Google Workspace

Desde `admin.google.com`:

1. Entrar con una cuenta administradora.
2. Ir a “Seguridad”.
3. Abrir “Control de acceso y datos”.
4. Entrar a “Controles de API”.
5. Seleccionar “Administrar acceso de aplicaciones”.
6. Presionar “Configurar nueva aplicación”.
7. Buscar la aplicación utilizando el Client ID OAuth.
8. Seleccionar la unidad organizativa de los ejecutivos.
9. Elegir “Datos específicos de Google”.
10. Autorizar únicamente Gmail de solo lectura, envío y datos básicos de identidad.
11. Finalizar y guardar.
12. Repetir el proceso con los Client ID de desarrollo y producción.

Es preferible “Datos específicos de Google” sobre “Trusted”, porque evita entregar acceso futuro a servicios no solicitados. Consulta la [configuración oficial de acceso en Workspace](https://support.google.com/a/answer/7281227).

Al ser un piloto interno para un solo Workspace, no será obligatorio completar la verificación pública de Google. Consulta las [exenciones para aplicaciones internas](https://support.google.com/cloud/answer/13464323).

### G. Variables que se configurarán en Railway

Agregar en backend, Celery Worker y Celery Beat:

- `MAIL_FEATURE_ENABLED`
- `MAIL_SYNC_INTERVAL_MINUTES`, con valor 15.
- `MAIL_INITIAL_LOOKBACK_DAYS`, con valor 30.
- `MAIL_DATA_RETENTION_DAYS`, con valor 30.
- `MAIL_DAILY_DIGEST_LOCAL_TIME`, con valor 08:30.
- `MAIL_ENCRYPTION_KEY`, diferente de la clave JWT.
- `GOOGLE_MAIL_CLIENT_ID`
- `GOOGLE_MAIL_CLIENT_SECRET`
- `GOOGLE_MAIL_REDIRECT_URI`
- `MICROSOFT_MAIL_CLIENT_ID`
- `MICROSOFT_MAIL_CLIENT_SECRET`
- `MICROSOFT_MAIL_TENANT_ID`
- `MICROSOFT_MAIL_REDIRECT_URI`

Los secretos nunca se agregarán al frontend ni al repositorio.

### H. Configurar Microsoft Outlook

Aunque no pertenece a Google Cloud, es obligatorio para el alcance acordado.

1. Entrar al centro de administración de Microsoft Entra.
2. Ir a “Entra ID → App registrations”.
3. Crear `Inmo CRM Correo`.
4. Seleccionar “Accounts in this organizational directory only”.
5. Copiar:

   - Application Client ID.
   - Directory Tenant ID.

6. En “Authentication”, agregar plataforma “Web”.
7. Registrar:

   - `http://localhost:8000/api/v1/mail/outlook/callback`
   - `https://<DOMINIO_BACKEND_RAILWAY>/api/v1/mail/outlook/callback`

8. En “API permissions → Microsoft Graph → Delegated permissions”, agregar:

   - `User.Read`
   - `Mail.Read`
   - `Mail.Send`
   - `openid`
   - `profile`
   - `email`
   - `offline_access`

9. Presionar “Grant admin consent” para la organización.
10. Crear un Client Secret para el piloto.
11. Guardar su fecha de expiración y programar su rotación.
12. Desactivar flujos de cliente público.

La aplicación usará permisos delegados: solamente podrá actuar sobre la cuenta conectada por el ejecutivo. Consulta el [registro de aplicaciones](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app) y los [permisos de Microsoft Graph](https://learn.microsoft.com/en-us/graph/permissions-reference).

## 2. Implementación por etapas

### Etapa 1: seguridad, datos y conexiones OAuth

Objetivo: conectar y desconectar Gmail y Outlook sin afectar los calendarios actuales.

- Crear el módulo de correo en backend, tareas programadas y frontend.
- Crear tablas multi-tenant:

  - `mail_connections`
  - `mail_message_refs`
  - `mail_action_suggestions`
  - `mail_drafts`
  - `mail_daily_digests`

- Cada registro incluirá `broker_id` y `user_id`.
- Permitir como máximo una cuenta Gmail y una Outlook por ejecutivo.
- Guardar tokens de Google cifrados.
- Para Outlook, guardar un caché MSAL serializado y cifrado por usuario, no manipular directamente refresh tokens. Microsoft recomienda persistir un caché independiente por usuario. Consulta la [persistencia oficial de MSAL](https://learn.microsoft.com/en-us/entra/msal/python/advanced/msal-python-token-cache-serialization).
- Implementar estado OAuth de un solo uso, almacenado temporalmente en Redis.
- Incorporar PKCE y validar que el callback corresponda al ejecutivo, broker y proveedor correctos.
- Validar los permisos realmente concedidos.
- Si el ejecutivo permite lectura pero no envío, el resumen seguirá funcionando y “Enviar” aparecerá desactivado.
- Agregar en Configuración una sección “Correo” separada de “Calendario”.
- Antes de OAuth, mostrar una autorización interna que explique qué se leerá, cómo participa la IA, la retención y cómo eliminar los datos.

Validación:

- Un ejecutivo conecta y desconecta cada proveedor.
- Otro usuario no puede consultar ni utilizar esa conexión.
- Los tokens nunca aparecen en respuestas, logs ni frontend.
- Las conexiones actuales de Calendar continúan funcionando.

### Etapa 2: sincronización y relación con leads

Objetivo: detectar correos comerciales sin convertir el CRM en una copia completa de la bandeja.

- Importar inicialmente Inbox y Enviados de los últimos 30 días.
- Después utilizar sincronización incremental:

  - Gmail mediante `historyId`.
  - Outlook mediante `deltaLink` por carpeta.

Gmail recomienda sincronización inicial seguida de consultas parciales con `history.list`; Outlook ofrece delta query para el mismo propósito. Consulta la [sincronización de Gmail](https://developers.google.com/workspace/gmail/api/guides/sync) y la [sincronización incremental de Outlook](https://learn.microsoft.com/en-us/graph/delta-query-messages).

- Celery Beat iniciará el proceso cada 15 minutos.
- Cada conexión se procesará en una tarea independiente del Worker.
- Utilizar bloqueos e identificadores únicos para impedir duplicados.
- Aplicar reintentos con espera progresiva y respetar `Retry-After`.
- Consultar primero remitentes, destinatarios y fechas.
- Descargar el cuerpo solamente cuando exista coincidencia exacta con el email de un lead asignado al ejecutivo.
- Si el email aparece en varios leads del mismo ejecutivo, marcarlo como ambiguo y no analizarlo.
- Ignorar leads desasignados o asignados a otra persona.
- Excluir spam, papelera, borradores, newsletters y adjuntos.
- Convertir HTML a texto seguro y eliminar cadenas citadas repetidas.
- No guardar el cuerpo original del correo.
- Guardar únicamente:

  - Identificador del proveedor y conversación.
  - Lead relacionado.
  - Dirección entrante o saliente.
  - Fecha.
  - Asunto cifrado.
  - Resumen cifrado.
  - Indicador de respuesta pendiente.
  - Estado de procesamiento.

Validación:

- Un correo nuevo aparece en el CRM en un máximo de 15 minutos.
- Correos ajenos a leads no generan resúmenes ni registros.
- Repetir la misma sincronización no duplica correos ni sugerencias.
- Un fallo de Gmail, Outlook o IA no detiene las otras conexiones.

### Etapa 3: inteligencia artificial y automatización controlada

Objetivo: transformar correos en información útil sin permitir acciones autónomas.

- Crear un análisis estructurado que obtenga:

  - Resumen breve.
  - Urgencia.
  - Necesidad de respuesta.
  - Objeciones.
  - Documentos prometidos o solicitados.
  - Compromisos.
  - Fechas mencionadas.
  - Acciones sugeridas.

- Tratar todo el contenido del correo como información no confiable.
- No permitir que instrucciones escritas dentro de un correo ejecuten herramientas, cambien permisos o envíen mensajes.
- Desactivar cachés semánticos y logs de contenido para este flujo.
- No utilizar correos para entrenar o mejorar modelos generales.
- Mantener las reglas comerciales existentes, incluyendo no prometer aprobación financiera, disponibilidad o precios no confirmados.

Google reconoce expresamente los CRM y los resúmenes generativos como usos permitidos de Gmail, pero prohíbe utilizar estos datos para entrenar modelos generales. Consulta la [política de datos de Google Workspace](https://developers.google.com/workspace/workspace-api-user-data-developer-policy).

#### Resumen diario

- Un proceso revisará cada 15 minutos qué usuarios llegaron a las 08:30 en `America/Santiago`.
- Una restricción única por usuario y fecha impedirá generar dos resúmenes automáticos.
- El resumen incluirá:

  - Respuestas recibidas.
  - Leads esperando respuesta.
  - Solicitudes urgentes.
  - Documentos y compromisos.
  - Objeciones detectadas.
  - Reuniones relacionadas.
  - Tareas sugeridas.
  - Seguimientos atrasados.

- La actualización manual reemplazará el resumen del día utilizando los datos más recientes.

#### Tareas sugeridas

- La IA creará una sugerencia, nunca una tarea definitiva.
- El ejecutivo podrá editar título, vencimiento y recordatorio antes de aprobar.
- Fechas explícitas se interpretarán en horario de Chile.
- Si existe una acción clara pero no una hora, se propondrá las 10:00 del día indicado.
- Si no existe fecha, se propondrá el siguiente día hábil a las 10:00 y se marcará como “fecha inferida”.
- Al aprobar se utilizará el servicio actual de tareas y su recordatorio predeterminado de una hora.
- Cada sugerencia solo podrá aprobarse una vez.
- Las tareas aprobadas conservarán una referencia de auditoría, pero no el cuerpo del correo.

#### Borradores y envío

- El ejecutivo solicitará el borrador desde un correo vinculado.
- La IA utilizará el correo, el estado del lead, proyecto, notas y tareas relevantes.
- El ejecutivo podrá modificar asunto y contenido.
- El destinatario estará bloqueado al email del lead.
- No habrá CC, BCC, adjuntos ni envíos masivos.
- Se mostrará una confirmación final antes de enviar.
- Gmail enviará con `gmail.send` y Outlook con `Mail.Send`.
- Se conservará el hilo de respuesta del proveedor.
- Un fallo de envío mantendrá el borrador y permitirá reintentar.

### Etapa 4: interfaz y métricas

Objetivo: proporcionar una experiencia diaria clara para ejecutivos y jefatura.

Crear `/mail-assistant` con el acceso “Bandeja IA” y estas secciones:

- Resumen de hoy.
- Correos por responder.
- Acciones sugeridas.
- Borradores.
- Historial reciente.
- Estado de conexión.

Cada tarjeta permitirá:

- Abrir el lead.
- Consultar el correo bajo demanda.
- Generar o editar una respuesta.
- Aprobar o descartar una tarea.
- Marcar una sugerencia como revisada.

El cuerpo solicitado bajo demanda se devolverá con política `no-store` y no se persistirá.

En el seguimiento del lead se agregará una sección de correos vinculados, visible solamente para el dueño de la cuenta de correo.

Jefatura verá exclusivamente:

- Ejecutivos con correo conectado.
- Correos vinculados a leads.
- Leads esperando respuesta.
- Tiempo medio de respuesta.
- Sugerencias pendientes.
- Tareas aprobadas desde correos.
- Errores de sincronización.

No verá asuntos, cuerpos, borradores ni resúmenes individuales.

Agregar eventos WebSocket:

- `mail_sync_completed`
- `mail_action_suggested`
- `mail_draft_sent`
- `mail_connection_attention`

## 3. APIs e interfaces

Crear bajo `/api/v1/mail`:

- `GET /connections`
- `GET /connections/{provider}/auth-url`
- `GET /google/callback`
- `GET /outlook/callback`
- `DELETE /connections/{provider}`
- `DELETE /connections/{provider}/data`
- `POST /connections/{provider}/sync`
- `GET /messages`
- `GET /messages/{message_id}/content`
- `POST /messages/{message_id}/draft`
- `PATCH /drafts/{draft_id}`
- `POST /drafts/{draft_id}/send`
- `DELETE /drafts/{draft_id}`
- `GET /suggestions`
- `POST /suggestions/{suggestion_id}/accept`
- `POST /suggestions/{suggestion_id}/dismiss`
- `GET /digest/today`
- `POST /digest/refresh`
- `GET /metrics/summary`

Agregar tipos TypeScript:

- `MailProvider`
- `MailConnection`
- `MailConnectionStatus`
- `LeadMailMessage`
- `MailActionSuggestion`
- `MailDraft`
- `DailyMailDigest`
- `MailMetrics`
- Filtros y eventos WebSocket correspondientes.

Permisos:

- Ejecutivo: solamente su correo y leads asignados.
- Administrador: métricas agregadas del broker.
- Superadmin: métricas mediante impersonación.
- Ningún administrador podrá usar la conexión de otro ejecutivo para enviar mensajes.

Registrar en auditoría:

- Conexión y desconexión.
- Eliminación de datos.
- Fallos y recuperación de sincronización.
- Generación, edición y envío de borradores.
- Aprobación y descarte de tareas sugeridas.

## 4. Seguridad, privacidad y retención

- Usar una clave exclusiva `MAIL_ENCRYPTION_KEY`.
- Si la clave no está configurada, el módulo de correo no debe iniciar.
- Cifrar tokens, cachés MSAL, asuntos, resúmenes, borradores y digest.
- No guardar cuerpos ni adjuntos.
- No incluir contenido de correo en logs, Sentry, métricas o historial de llamadas LLM.
- Eliminar referencias, resúmenes, borradores y sugerencias después de 30 días.
- Las tareas aprobadas permanecerán porque pasan a ser datos operativos creados por el usuario.
- Al eliminar datos de una conexión, borrar inmediatamente todo contenido derivado, conservando solo auditoría sin contenido.
- Al desconectar Gmail, revocar el token cuando Google lo permita y eliminarlo localmente.
- Al desconectar Outlook, eliminar el caché MSAL local y mostrar instrucciones para revocar la aplicación desde Microsoft si fuese necesario.
- Mantener un botón visible “Eliminar mis datos de correo”.
- Documentar expresamente que los datos no se usan para publicidad, evaluación crediticia ni entrenamiento general de IA.
- Verificar contractualmente que el proveedor LLM configurado no utilice las solicitudes API para entrenamiento.

## 5. Pruebas, despliegue y paso futuro a clientes externos

### Pruebas obligatorias

- Aislamiento entre brokers y ejecutivos.
- Administrador limitado a métricas.
- OAuth válido, expirado, repetido, cancelado y con permisos parciales.
- Tokens cifrados y ausencia de contenido en logs.
- Importación inicial de 30 días.
- Sincronización incremental de Gmail y Outlook.
- Recuperación cuando el cursor de Gmail expire.
- Paginación y `deltaLink` de Outlook.
- Manejo de límites, errores 429 y `Retry-After`.
- Coincidencia exacta, duplicada y ausente de emails de leads.
- No procesamiento de correos personales.
- Idempotencia de mensajes y sugerencias.
- Protección contra instrucciones maliciosas dentro del correo.
- Resumen único a las 08:30, considerando horario de verano chileno.
- Actualización manual del resumen.
- Generación, edición, envío y reintento de borradores.
- Restricción del destinatario al lead.
- Aprobación única de tareas y conversión a la bandeja existente.
- Desconexión, revocación y eliminación de datos.
- Estados de carga, vacío, error y reconexión.
- Pruebas backend, frontend, type-check, Vitest y build.
- Flujo completo en Docker con backend, Worker, Beat, Redis y PostgreSQL.
- Prueba real con una cuenta Gmail y una Outlook internas.

### Orden de despliegue

1. Crear los proyectos y clientes OAuth de desarrollo.
2. Implementar y validar localmente.
3. Crear clientes OAuth de producción con la URL real de Railway.
4. Configurar Google Workspace y Microsoft Entra.
5. Desplegar migración aditiva con la función desactivada.
6. Desplegar backend, Worker y Beat.
7. Desplegar frontend.
8. Conectar dos ejecutivos piloto.
9. Activar la sincronización.
10. Observar durante tres a cinco días:

    - Errores OAuth.
    - Duración de sincronización.
    - Duplicados.
    - Costos LLM.
    - Tareas sugeridas y descartadas.
    - Envíos fallidos.

11. Corregir problemas y habilitar al resto de los ejecutivos internos.

### Paso futuro para clientes externos

Antes de permitir cuentas Gmail de otros dominios:

1. Adquirir un dominio propio.
2. Publicar página principal, privacidad, términos y eliminación de datos.
3. Conectar frontend y backend a subdominios propios con HTTPS.
4. Verificar el dominio mediante Google Search Console.
5. Cambiar la audiencia de Google a “External”.
6. Registrar el dominio en Branding.
7. Actualizar las URI OAuth.
8. Preparar un video mostrando consentimiento, conexión, resumen, borrador, tarea y eliminación.
9. Justificar por qué se necesitan `gmail.readonly` y `gmail.send`.
10. Enviar la aplicación a verificación.
11. Completar la evaluación de seguridad que Google solicite por el uso de scopes restringidos y procesamiento en servidores.

Google exige página pública, política de privacidad, dominio verificado, demostración de la funcionalidad y evaluación de seguridad para aplicaciones externas que almacenan o transmiten datos obtenidos mediante scopes restringidos. Consulta los [requisitos oficiales de verificación](https://support.google.com/cloud/answer/13464321).

Hasta completar esa etapa, el módulo permanecerá restringido al Google Workspace y tenant Microsoft internos.
