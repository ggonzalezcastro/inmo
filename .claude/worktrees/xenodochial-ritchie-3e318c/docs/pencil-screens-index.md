# Índice de pantallas — Proyecto Pencil (Inmo)

Este documento mapea las pantallas del frontend React con el proyecto Pencil **Frost.pen**. Usa la skill **pencil-design** y el MCP de Pencil Dev para refinar los diseños.

## Estado del MCP Pencil

El MCP de Pencil se arranca con la **extensión Pencil Dev** en Cursor. Si el servidor fallaba era porque la extensión no estaba instalada (el binario no existía).

**Para tener el MCP activo:**

1. En Cursor: **Extensions** (Cmd+Shift+X) → buscar **"Pencil"** → **Install**.
2. Tras instalar, el MCP suele registrarse solo. Si no: **Settings → Tools & MCP** y añade el servidor Pencil (la extensión indica la ruta del binario).
3. Abre un `.pen` (p. ej. `Frost.pen`) y comprueba en MCP que **pencil** aparece sin error.

Cuando esté activo podrás usar `pencil_get_editor_state`, `pencil_batch_get`, `pencil_batch_design`, `pencil_get_screenshot`, etc.

## Archivo Pencil

| Archivo   | Descripción                          |
|----------|--------------------------------------|
| `Frost.pen` | Proyecto principal con todas las pantallas |

## Mapeo rutas ↔ frames en Frost.pen

Cada pantalla tiene **contenido distinto** según la vista real del frontend (no clon del dashboard).

| Ruta frontend | Frame en Pencil | ID frame | Contenido en Frost.pen |
|---------------|-----------------|----------|------------------------|
| `/login`      | Login           | `Lgn01`  | Formulario centrado (email, contraseña, Entrar) |
| `/register`   | Register        | `Reg02`  | Formulario de registro |
| `/403`        | 403 Forbidden   | `F403`   | Mensaje 403 + "Volver al inicio" |
| `/dashboard`  | K — FROST INMOBILIARIA | `AgwAe` | **Dashboard** (sidebar + KPIs + tabla + actividad) |
| `/leads`      | Leads           | `Lds04`  | Header + **tabla de leads** (sin KPIs ni panel derecho) |
| `/pipeline`   | Pipeline        | `Pip05`  | Header + **Kanban** (columnas: Entrada, Perfilamiento, Cal. Financiera, Agendado, Seguimiento, Ganado/Perdido) |
| `/campaigns`  | Campaigns       | `Cpg06`  | Header + **lista de cards** de campañas (nombre, estado, stats) |
| `/appointments` | Appointments  | `Apt07`  | Header + **tabla de citas** |
| `/templates`  | Templates       | `Tpl08`  | Header + **tabla de plantillas** |
| `/chat`       | Chat IA         | `Cht09`  | Header + **área de chat** (mensajes + input) |
| `/costs`      | Costs LLM       | `Cst10`  | Header + **cards resumen** + **gráficos** (tendencia, por proveedor, por broker) + **tabla de costos** |
| `/settings`   | Settings        | `Stg11`  | Header + **secciones de configuración** (Datos broker, Notificaciones, Integraciones) |
| `/users`      | Users           | `Usr12`  | Header + **tabla de usuarios** |
| `/brokers`    | Brokers         | `Brk13`  | Header + **tabla de brokers** |

## Workflow con Pencil MCP (skill pencil-design)

Cuando el MCP esté disponible:

1. **Abrir documento**: `pencil_open_document` con `path` a `Frost.pen`.
2. **Estado y sistema de diseño**: `pencil_get_editor_state`, luego `pencil_batch_get` con `patterns: [{ reusable: true }]` para reutilizar componentes (sidebar, botones, cards).
3. **Variables**: `pencil_get_variables` y usar tokens (colores, radius, tipografía) en lugar de valores fijos.
4. **Por cada pantalla placeholder**: usar `pencil_batch_design` para reemplazar el contenido del frame por el diseño real (reutilizando componentes del frame `AgwAe` donde aplique).
5. **Verificación**: `pencil_get_screenshot` por sección y `pencil_snapshot_layout` con `problemsOnly: true`.

El frame **AgwAe** (K — FROST INMOBILIARIA) sirve como referencia de layout con sidebar, header, KPIs y tabla; se puede copiar estructura a otras pantallas con `pencil_batch_design` (operación `C()` para copiar nodos).

## Design-to-code (skill pencil-to-code)

Para exportar un frame a React/Tailwind:

1. `pencil_batch_get` del frame (p. ej. `Lgn01`) con `resolveInstances: true`, `resolveVariables: true`.
2. Mapear variables del .pen a `@theme` de Tailwind v4.
3. Generar componente React con clases semánticas (`bg-primary`, `rounded-md`, etc.) según las referencias de la skill.

## Referencias

- Skill **pencil-design**: diseño en Pencil, reutilización de componentes, variables, verificación visual.
- Skill **pencil-to-code**: exportar .pen → React + Tailwind.
- Skill **frontend-design**: cargar siempre junto a pencil-design para dirección estética y calidad.
