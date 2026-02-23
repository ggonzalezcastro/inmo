# Diseños Inmo - AI Lead Agent Pro

Esta carpeta contiene los diseños de las vistas del frontend creados en **Pencil** para facilitar el diseño y la iteración visual.

## Vistas incluidas

Todas las pantallas principales de la aplicación han sido migradas a Pencil:

| Vista | Descripción |
|-------|-------------|
| **Login** | Formulario de inicio de sesión (AI Lead Agent Pro) |
| **Register** | Formulario de registro con nombre del broker |
| **Dashboard** | Panel con estadísticas (Total Leads, Cold, Warm, Hot, Avg Score) |
| **Leads** | Tabla de leads con filtros y paginación |
| **Pipeline** | Vista Kanban con columnas (Nuevo, Contactado, Calificado) + sidebar de detalle |
| **Campanas** | Lista de campañas con estado (Activa) |
| **Chat** | Interfaz de chat para generación de leads |
| **Templates** | Plantillas de mensajes |
| **Configuracion** | Página de settings con tabs (Agente, Calificación, Alertas) |
| **Usuarios** | Gestión de usuarios del equipo (Admin/Agente) |
| **Brokers** | Gestión de brokers (SuperAdmin) |

## Archivos en esta carpeta

- **`inmo-app-shadcn.pen`** — Diseño completo con Shadcn UI (11 pantallas)
- **`inmo-views.pen`** — Diseños con estilo Swiss Clean Expressive (legacy)
- **`PENCIL_DESIGN_PROMPT.md`** — Prompt completo para recrear desde cero con Shadcn UI
- **`README.md`** — Este archivo

## Cómo usar

### Diseños actuales (inmo-views.pen)
1. **Abrir en Pencil**: Si tienes el archivo `inmo-views.pen`, ábrelo con Pencil en Cursor.
2. **Guardar cambios**: Los diseños están en un canvas ordenado en cuadrícula.
3. **Modificar**: Usa Pencil para iterar en el diseño actual.

### Diseño Shadcn UI (inmo-app-shadcn.pen)
1. Abre el archivo **`inmo-app-shadcn.pen`** en Pencil
2. Contiene 11 pantallas con estilo Shadcn UI
3. Guarda el documento actual como `design/inmo-app-shadcn.pen` si creaste uno nuevo

### Recrear desde cero
1. Lee el archivo **`PENCIL_DESIGN_PROMPT.md`**
2. Sigue las especificaciones para diseñar con componentes de Shadcn UI

## Mapeo Frontend ↔ Pencil

- `frontend/src/components/Login.jsx` → Pantalla **Login**
- `frontend/src/components/Register.jsx` → Pantalla **Register**
- `frontend/src/components/Dashboard.jsx` → Pantalla **Dashboard**
- `frontend/src/pages/Leads.jsx` → Pantalla **Leads**
- `frontend/src/pages/Pipeline.jsx` → Pantalla **Pipeline**
- `frontend/src/pages/Campaigns.jsx` → Pantalla **Campanas**
- `frontend/src/pages/Chat.jsx` → Pantalla **Chat**
- `frontend/src/pages/Templates.jsx` → Pantalla **Templates**
- `frontend/src/pages/SettingsPage.jsx` → Pantalla **Configuracion**
- `frontend/src/pages/UsersPage.jsx` → Pantalla **Usuarios**
- `frontend/src/pages/BrokersPage.jsx` → Pantalla **Brokers**

## Estilo aplicado: Swiss Clean Expressive

Diseño prediseñado con estética **Swiss Expressionism**:

- **Sidebar/Nav oscuro:** `#0A0A0A` — contraste marcado
- **Acento principal:** `#FF3B30` (rojo iOS) — CTAs, estados activos
- **Fondo contenido:** `#FFFFFF`
- **Texto principal:** `#0A0A0A`
- **Texto secundario:** `#666666`
- **Bordes:** `#E0E0E0`
- **Columnas Kanban:** `#1A1A1A`
- **Esquinas:** 0px (sin redondeo) — geometría definida
- **Tipografía:** Space Grotesk (bold), Inter (body)
