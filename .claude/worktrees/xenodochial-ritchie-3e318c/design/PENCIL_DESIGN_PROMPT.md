# AI Lead Agent Pro - Prompt Completo para Diseño en Pencil

## 🎯 Objetivo

Diseñar desde cero en Pencil la aplicación completa **AI Lead Agent Pro**, un CRM inmobiliario con IA para gestión de leads, utilizando **Shadcn UI** como sistema de diseño base.

---

## 📋 Descripción del Proyecto

**AI Lead Agent Pro** es una plataforma CRM para inmobiliarias que:
- Gestiona leads inmobiliarios con IA
- Automatiza conversaciones por Telegram y llamadas
- Califica leads automáticamente (scoring 0-100)
- Permite seguimiento en pipeline Kanban
- Gestiona campañas y plantillas de mensajes
- Multi-tenant (brokers/inmobiliarias con usuarios)
- Roles: SuperAdmin, Admin, Agente

---

## 🎨 Sistema de Diseño Base

### Shadcn UI
**IMPORTANTE:** Usar componentes de **Shadcn UI** como base:
- Button (primary, secondary, outline, ghost, destructive)
- Card (con CardHeader, CardContent, CardFooter)
- Input, Textarea, Select
- Table (DataTable)
- Badge
- Avatar
- Tabs
- Dialog/Modal
- Dropdown Menu
- Command palette
- Progress bar
- Skeleton (loading states)
- Toast/Alert
- Separator

### Paleta de Colores Shadcn
```css
/* Variables CSS de Shadcn UI */
--background: 0 0% 100%;           /* #FFFFFF */
--foreground: 222.2 84% 4.9%;      /* #020817 */
--card: 0 0% 100%;                  /* #FFFFFF */
--card-foreground: 222.2 84% 4.9%;
--popover: 0 0% 100%;
--popover-foreground: 222.2 84% 4.9%;
--primary: 221.2 83.2% 53.3%;      /* #3B82F6 (blue) */
--primary-foreground: 210 40% 98%;
--secondary: 210 40% 96.1%;
--secondary-foreground: 222.2 47.4% 11.2%;
--muted: 210 40% 96.1%;            /* #F1F5F9 */
--muted-foreground: 215.4 16.3% 46.9%;
--accent: 210 40% 96.1%;
--accent-foreground: 222.2 47.4% 11.2%;
--destructive: 0 84.2% 60.2%;      /* #EF4444 (red) */
--destructive-foreground: 210 40% 98%;
--border: 214.3 31.8% 91.4%;       /* #E2E8F0 */
--input: 214.3 31.8% 91.4%;
--ring: 221.2 83.2% 53.3%;
--radius: 0.5rem;                   /* 8px */
```

### Tipografía Shadcn
- **Font principal:** Inter o Geist Sans
- **Font secundaria:** Inter o system-ui
- **Font monospace:** Geist Mono o Fira Code (para código/datos)

**Escalas:**
- Heading 1: 36px (2.25rem), font-weight 700
- Heading 2: 30px (1.875rem), font-weight 600
- Heading 3: 24px (1.5rem), font-weight 600
- Body Large: 16px (1rem), font-weight 400
- Body: 14px (0.875rem), font-weight 400
- Caption: 12px (0.75rem), font-weight 400
- Small: 11px (0.6875rem), font-weight 400

### Espaciado
```
2px, 4px, 8px, 12px, 16px, 20px, 24px, 32px, 40px, 48px, 64px
```

---

## 🏗️ Arquitectura de la Aplicación

### Rutas Principales

1. **Autenticación (Públicas)**
   - `/login` - Login
   - `/register` - Registro (broker + admin inicial)

2. **App (Privadas)**
   - `/dashboard` - Dashboard con estadísticas (Admin)
   - `/leads` - Tabla de leads (Admin/Agente)
   - `/pipeline` - Kanban de pipeline (Admin/Agente)
   - `/campaigns` - Gestión de campañas (Admin)
   - `/templates` - Plantillas de mensajes (Admin)
   - `/chat` - Chat de prueba (Admin/Agente)
   - `/settings` - Configuración (Admin)
   - `/users` - Gestión de usuarios (Admin)
   - `/brokers` - Gestión de brokers (SuperAdmin)

---

## 📱 Pantallas Detalladas

### 1. LOGIN (`/login`)

**Layout:** Centrado vertical y horizontal

**Componentes Shadcn:**
- Card (400px ancho)
- Input (email, password)
- Button (primary, full-width)
- Link (navegación a register)

**Estructura:**
```
┌────────────────────────────────────────┐
│                                        │
│         AI Lead Agent Pro              │ ← Heading 1
│         Login a tu cuenta              │ ← Muted text
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ Email                            │ │ ← Input con label
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ Password                         │ │ ← Input con label
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │         Login                    │ │ ← Button primary
│  └──────────────────────────────────┘ │
│                                        │
│  ¿No tienes cuenta? Regístrate        │ ← Link
│                                        │
└────────────────────────────────────────┘
```

**Estados:**
- Default
- Loading (button con spinner)
- Error (alert destructive)

---

### 2. REGISTER (`/register`)

**Layout:** Similar a Login, card centrada

**Componentes Shadcn:**
- Card (400px)
- Input (nombre broker, email, password)
- Button (primary)
- Link (a login)

**Campos:**
1. Nombre del Broker (text)
2. Email (email)
3. Password (password)
4. Botón "Registrarse"

---

### 3. DASHBOARD (`/dashboard`)

**Layout:** NavBar + Content (max-w-7xl, padding)

**Componentes Shadcn:**
- Card × 5 (stats)
- Table (DataTable)
- Input (search)
- Select (filters)
- Badge (status)
- Button (actions)

**Estructura:**
```
┌─────────────────────────────────────────────────┐
│ NavBar                                   Logout │ ← Sticky top
├─────────────────────────────────────────────────┤
│                                                 │
│  Dashboard                                      │ ← Heading 1
│                                                 │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───┐│
│  │Total  │ │ Cold  │ │ Warm  │ │  Hot  │ │Avg││ ← Stats Cards
│  │  150  │ │  60   │ │  50   │ │  40   │ │75 ││
│  └───────┘ └───────┘ └───────┘ └───────┘ └───┘│
│                                                 │
│  Filtros                                        │
│  ┌─────────┐ ┌────────┐ ┌────┐ ┌────┐  [Aplicar]
│  │Búsqueda │ │ Estado │ │Min │ │Max │          │
│  └─────────┘ └────────┘ └────┘ └────┘          │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │ Tabla de Leads                           │ │ ← DataTable
│  │ Nombre  │ Teléfono │ Estado │ Score │... │ │
│  │─────────┼──────────┼────────┼───────┼────│ │
│  │ Juan    │ +34 612  │ cold   │ █████ 75  │ │
│  │ María   │ +34 623  │ warm   │ ████  65  │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  [← Anterior]  Página 1 de 10  [Siguiente →]   │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Cards de Estadísticas:**
- **Total Leads:** Número grande, icono 📊
- **Cold:** Azul (#3B82F6)
- **Warm:** Amarillo (#EAB308)
- **Hot:** Rojo (#EF4444)
- **Avg Score:** Gris

**Tabla:**
- Columnas: Nombre, Teléfono, Estado (Badge), Score (Progress), Creado, Asignado a (Select para admin)
- Sortable
- Pagination

---

### 4. LEADS (`/leads`)

**Layout:** Idéntico a Dashboard pero sin redirección (accesible para agentes)

**Diferencias:**
- Agentes ven solo sus leads asignados
- Admins ven todos y pueden asignar

---

### 5. PIPELINE (`/pipeline`)

**Layout:** NavBar + Split View (Kanban + Sidebar)

**Componentes Shadcn:**
- Card (lead cards)
- Badge (status)
- Progress (score)
- ScrollArea
- Dialog o Sheet (ticket detail)

**Estructura:**
```
┌──────────────────────────────────────────────────────────────┐
│ NavBar                                              Logout   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Filters: [Buscar] [Asignado] [Campaña] [Desde] [Hasta]     │
│                                                              │
├────────┬────────┬────────┬────────┬────────┬────────┬───────┤
│ Nuevo  │Contact │Califid │Interés │Present │Negocio │Cerrado│
│ (12)   │ (8)    │ (15)   │ (6)    │ (4)    │ (3)    │ (2)  │
├────────┼────────┼────────┼────────┼────────┼────────┼───────┤
│┌──────┐│┌──────┐│┌──────┐│        │        │        │       │
││María ││││Juan  ││││Ana   │││      │        │        │       │
││+34 6 ││││+34 6 ││││+34 6 │││      │        │        │       │
││█75%  ││││█65%  ││││█90%  │││      │        │        │       │
│└──────┘││└──────┘││└──────┘││      │        │        │       │
│        │└──────┘││        ││      │        │        │       │
│        │        │└──────┘││      │        │        │       │
└────────┴────────┴────────┴────────┴────────┴────────┴───────┘
```

**8 Columnas (PIPELINE_STAGES):**
1. `new` - Nuevo
2. `contacted` - Contactado
3. `qualified` - Calificado
4. `interested` - Interesado
5. `presentation` - Presentación
6. `negotiation` - Negociación
7. `closed_won` - Cerrado Ganado
8. `closed_lost` - Cerrado Perdido

**Lead Card (Shadcn Card):**
```
┌─────────────────────────────┐
│ Juan Pérez          [•••]   │ ← Drag handle
│ +34 612 345 678             │
│                             │
│ [Atendido por IA] ← Badge   │
│                             │
│ Score: 75%                  │
│ ████████░░░ 75              │ ← Progress
│                             │
│ "Hola, estoy interesa..."   │ ← Last message
│                             │
│ [piso] [Madrid]             │ ← Tags
└─────────────────────────────┘
```

**Ticket Detail Sidebar (Sheet/Dialog):**
- Cuando se hace clic en una card, se abre un panel lateral (50% ancho)
- Muestra:
  - Info del lead (nombre, teléfono, email, score)
  - Chat completo (mensajes con timestamps)
  - Input para responder
  - Botones: Cambiar etapa, Asignar, Ver perfil completo

---

### 6. CAMPAIGNS (`/campaigns`)

**Layout:** NavBar + Content

**Componentes Shadcn:**
- Card (campaign cards)
- Badge (status)
- Button (crear, editar)
- Tabs (lista / builder / analytics)
- Dialog (formulario crear/editar)

**Vistas:**

#### 6.1 Lista de Campañas
```
┌────────────────────────────────────────────┐
│ Campañas                    [+ Nueva]      │
├────────────────────────────────────────────┤
│                                            │
│ ┌────────────────────────────────────────┐│
│ │ Campaña Web Q1          [Activa]      ││ ← Card
│ │ Leads: 45  │  Resp: 32  │  Conv: 12   ││
│ │ [Ver] [Editar] [Analytics]            ││
│ └────────────────────────────────────────┘│
│                                            │
│ ┌────────────────────────────────────────┐│
│ │ Llamadas Febrero        [Pausada]     ││
│ │ Leads: 120 │  Resp: 85  │  Conv: 28   ││
│ │ [Ver] [Editar] [Analytics]            ││
│ └────────────────────────────────────────┘│
│                                            │
└────────────────────────────────────────────┘
```

#### 6.2 Campaign Builder
- Formulario con campos:
  - Nombre
  - Tipo (Telegram, Llamada, Email)
  - Segmento (filtros de leads)
  - Plantilla de mensaje
  - Programación (fecha, hora)
- Botones: Guardar, Probar, Cancelar

#### 6.3 Analytics
- Cards con métricas:
  - Enviados, Respondidos, Conversiones, Tasa de conversión
- Gráfico de barras/líneas (Chart.js o Recharts)

---

### 7. TEMPLATES (`/templates`)

**Layout:** NavBar + Content

**Componentes Shadcn:**
- Card (template cards)
- Textarea (editor)
- Badge (categoría)
- Button (crear, editar, eliminar)
- Dialog (editor de plantilla)

**Estructura:**
```
┌──────────────────────────────────────────┐
│ Plantillas de Mensajes      [+ Nueva]   │
├──────────────────────────────────────────┤
│                                          │
│ ┌──────────────────────────────────────┐│
│ │ Bienvenida           [Telegram]      ││
│ │ "Hola {nombre}, bienvenido a..."     ││
│ │ [Editar] [Eliminar]                  ││
│ └──────────────────────────────────────┘│
│                                          │
│ ┌──────────────────────────────────────┐│
│ │ Seguimiento 24h      [Llamada]       ││
│ │ "Buenos días {nombre}, llamo..."     ││
│ │ [Editar] [Eliminar]                  ││
│ └──────────────────────────────────────┘│
│                                          │
└──────────────────────────────────────────┘
```

**Variables disponibles:**
- `{nombre}`, `{telefono}`, `{email}`, `{propiedad}`, `{agente}`

---

### 8. CHAT (`/chat`)

**Layout:** NavBar + Chat Interface

**Componentes Shadcn:**
- Card (chat container)
- ScrollArea (mensajes)
- Input + Button (enviar)
- Avatar (usuarios)
- Badge (timestamp)

**Estructura:**
```
┌──────────────────────────────────────────┐
│ Chat de Prueba - Generador de Leads     │
├──────────────────────────────────────────┤
│                                          │
│ ┌──────────────────────────────────────┐│
│ │ 🤖 Hola, ¿en qué puedo ayudarte?    ││ ← Bot
│ │    10:30                             ││
│ │                                      ││
│ │              Busco un piso en       👤│ ← Usuario
│ │              Madrid                 ││
│ │                              10:31  ││
│ │                                      ││
│ │ 🤖 ¡Perfecto! ¿Qué zona prefieres?  ││
│ │    10:31                             ││
│ │                                      ││
│ │              Centro, cerca del      👤│
│ │              metro                  ││
│ │                              10:32  ││
│ └──────────────────────────────────────┘│
│                                          │
│ ┌──────────────────────────────────────┐│
│ │ Escribe un mensaje...      [Enviar] ││
│ └──────────────────────────────────────┘│
│                                          │
└──────────────────────────────────────────┘
```

---

### 9. SETTINGS (`/settings`)

**Layout:** NavBar + Tabs

**Componentes Shadcn:**
- Tabs (Agente, Calificación, Alertas)
- Card
- Textarea (prompts)
- Input (configuración)
- Switch (toggles)
- Slider (umbrales)
- Button (guardar)

**Tabs:**

#### 9.1 Agente
```
┌────────────────────────────────────────┐
│ ┌───────┐ ┌───────────┐ ┌────────┐   │
│ │Agente │ │Calificación│ │Alertas │   │
│ └───────┘ └───────────┘ └────────┘   │
├────────────────────────────────────────┤
│                                        │
│ System Prompt                          │
│ ┌────────────────────────────────────┐│
│ │Eres un agente inmobiliario experto││
│ │que ayuda a clientes a encontrar...││
│ │                                    ││
│ └────────────────────────────────────┘│
│                                        │
│ Tono: [Formal ▼]                       │
│ Idioma: [Español ▼]                    │
│                                        │
│                        [Guardar]       │
└────────────────────────────────────────┘
```

#### 9.2 Calificación
- Umbrales de scoring (sliders)
- Pesos de criterios (inputs)
- Reglas personalizadas

#### 9.3 Alertas
- Configurar notificaciones
- Umbrales de alertas (leads hot, sin responder, etc.)
- Canales (email, telegram)

---

### 10. USERS (`/users`)

**Layout:** NavBar + Content

**Componentes Shadcn:**
- Table (DataTable)
- Badge (rol)
- Dialog (crear/editar usuario)
- Avatar
- Button (acciones)

**Estructura:**
```
┌──────────────────────────────────────────┐
│ Usuarios del Equipo         [+ Nuevo]   │
├──────────────────────────────────────────┤
│                                          │
│ ┌──────────────────────────────────────┐│
│ │ 👤 admin@broker.com                  ││
│ │    Admin Principal                   ││
│ │    [Admin] [Editar] [Desactivar]     ││
│ └──────────────────────────────────────┘│
│                                          │
│ ┌──────────────────────────────────────┐│
│ │ 👤 agente1@broker.com                ││
│ │    Juan García                       ││
│ │    [Agente] [Editar] [Desactivar]    ││
│ └──────────────────────────────────────┘│
│                                          │
└──────────────────────────────────────────┘
```

**Campos en Dialog:**
- Email
- Nombre
- Rol (Select: Admin, Agente)
- Password (solo en creación)

---

### 11. BROKERS (`/brokers`)

**Layout:** Similar a Users (solo SuperAdmin)

**Componentes Shadcn:**
- Table
- Badge (activo/inactivo)
- Dialog (crear/editar)

**Estructura:**
```
┌──────────────────────────────────────────┐
│ Gestión de Brokers          [+ Nuevo]   │
├──────────────────────────────────────────┤
│                                          │
│ ┌──────────────────────────────────────┐│
│ │ Inmobiliaria Ejemplo                 ││
│ │ contacto@inmo.com  │  +34 912 345    ││
│ │ [Activo] [Editar] [Desactivar]       ││
│ └──────────────────────────────────────┘│
│                                          │
└──────────────────────────────────────────┘
```

---

## 🧩 Componentes Reutilizables

### NavBar (Shadcn)
```
┌─────────────────────────────────────────────────────┐
│ Dashboard ▼  Leads  Pipeline  Campañas...   Logout │
└─────────────────────────────────────────────────────┘
```

**Elementos:**
- Logo/Título (izquierda)
- Navegación horizontal (centro)
  - Links activos (primary color)
  - Hover states
- User dropdown o Logout button (derecha)

**Variante móvil:**
- Hamburger menu (Sheet)

---

### LeadCard (Shadcn Card)
Usado en Pipeline. Ya descrito arriba.

---

### StatCard (Shadcn Card)
```
┌──────────────┐
│ Total Leads  │ ← Label (muted)
│              │
│     150      │ ← Value (large, bold)
│              │
└──────────────┘
```

---

### DataTable (Shadcn Table)
Con:
- Sorting (columnas clickeables)
- Pagination
- Row actions (dropdown menu)
- Loading state (skeleton)

---

### FilterBar (Shadcn Input + Select)
```
[Search Input] [Select: Status] [Date From] [Date To] [Apply Button]
```

---

## 📊 Modelos de Datos (para contexto)

### Lead
```typescript
{
  id: number
  name: string
  phone: string
  email?: string
  lead_score: number (0-100)
  status: 'cold' | 'warm' | 'hot'
  pipeline_stage: 'new' | 'contacted' | ...
  assigned_to?: number (user_id)
  treatment_type?: 'automated_telegram' | 'automated_call' | 'manual'
  last_contacted?: Date
  created_at: Date
  tags?: string[]
  metadata?: object
  telegram_messages?: Message[]
}
```

### Campaign
```typescript
{
  id: number
  name: string
  type: 'telegram' | 'call' | 'email'
  status: 'active' | 'paused' | 'completed'
  template_id?: number
  segment_filters: object
  scheduled_at?: Date
  stats: {
    sent: number
    responded: number
    converted: number
  }
}
```

### Template
```typescript
{
  id: number
  name: string
  category: 'telegram' | 'call' | 'email'
  content: string
  variables: string[]
}
```

### User
```typescript
{
  id: number
  email: string
  name: string
  role: 'admin' | 'agent'
  broker_id: number
  is_active: boolean
}
```

---

## 🎨 Guía de Estilo Visual

### Colores Semánticos
- **Success:** Verde (#22C55E)
- **Warning:** Amarillo (#EAB308)
- **Error/Destructive:** Rojo (#EF4444)
- **Info:** Azul (#3B82F6)

### Badges
- **Cold:** Badge azul
- **Warm:** Badge amarillo
- **Hot:** Badge rojo
- **Atendido:** Badge verde
- **No atendido:** Badge gris
- **Activo/Inactivo:** Badge verde/gris

### Progress Bars (Score)
- 0-39: Rojo
- 40-69: Amarillo
- 70-100: Verde

### Iconos
Usar **Lucide Icons** (incluido en Shadcn):
- Home, User, Users, Settings, LogOut
- Mail, Phone, MessageCircle
- Calendar, Clock, Filter
- Plus, Edit, Trash, X
- ChevronDown, ChevronLeft, ChevronRight
- MoreHorizontal (•••)

---

## 🔄 Estados e Interacciones

### Loading States
- Skeleton loaders (Shadcn Skeleton)
- Spinner en botones
- Shimmer effect en cards

### Empty States
```
┌──────────────────────────┐
│    📭                    │
│    No hay leads          │
│    Crea el primero       │
│    [+ Crear Lead]        │
└──────────────────────────┘
```

### Error States
- Alert destructive
- Toast notifications
- Inline validation errors

### Drag & Drop (Pipeline)
- Hover state en columnas (border highlight)
- Dragging opacity
- Drop zones con feedback visual

---

## 📱 Responsive

### Breakpoints (Tailwind)
- `sm`: 640px
- `md`: 768px
- `lg`: 1024px
- `xl`: 1280px
- `2xl`: 1536px

### Mobile Adaptaciones
- NavBar → Hamburger menu (Sheet)
- Stats Cards → Stack vertical
- Pipeline → Scroll horizontal
- DataTable → Cards en mobile
- Sidebar de ticket → Full screen dialog

---

## ✅ Checklist de Diseño en Pencil

### Fase 1: Setup
- [ ] Crear archivo `inmo-app-shadcn.pen`
- [ ] Importar/referenciar componentes de Shadcn UI
- [ ] Configurar paleta de colores (variables)
- [ ] Configurar tipografía (Inter)
- [ ] Crear sistema de espaciado

### Fase 2: Componentes Base
- [ ] Button (variantes)
- [ ] Input, Select, Textarea
- [ ] Card (variantes)
- [ ] Badge (colores semánticos)
- [ ] Avatar
- [ ] Progress
- [ ] Table
- [ ] Dialog/Sheet
- [ ] Tabs

### Fase 3: Componentes Compuestos
- [ ] NavBar
- [ ] StatCard
- [ ] LeadCard
- [ ] FilterBar
- [ ] DataTable con pagination

### Fase 4: Pantallas (Desktop 1440px)
- [ ] Login
- [ ] Register
- [ ] Dashboard
- [ ] Leads
- [ ] Pipeline (+ Ticket Detail)
- [ ] Campaigns (3 vistas)
- [ ] Templates
- [ ] Chat
- [ ] Settings (3 tabs)
- [ ] Users
- [ ] Brokers

### Fase 5: Estados
- [ ] Loading states
- [ ] Empty states
- [ ] Error states
- [ ] Hover/Active states
- [ ] Drag states (Pipeline)

### Fase 6: Responsive
- [ ] Mobile adaptaciones (375px)
- [ ] Tablet (768px)
- [ ] Desktop (1440px)

### Fase 7: Extras
- [ ] Dark mode (opcional)
- [ ] Animaciones (transiciones)
- [ ] Microinteracciones

---

## 🎯 Consideraciones Especiales

### Pipeline Kanban
- Usar `@dnd-kit` para drag & drop en implementación
- Columnas con scroll vertical independiente
- Drop zones con feedback visual
- Card en dragging con opacity reducida

### DataTable
- Sorting por columnas
- Pagination en footer
- Row actions (dropdown con •••)
- Select rows (checkbox)
- Responsive: en mobile convertir a cards

### Chat Interface
- Auto-scroll al último mensaje
- Mensajes del bot (izquierda) vs usuario (derecha)
- Timestamps
- Input con auto-resize
- Typing indicator (opcional)

### Real-time Updates
- Indicar en diseño áreas que se actualizarán en tiempo real:
  - Pipeline (nuevos leads)
  - Dashboard (estadísticas)
  - Chat (nuevos mensajes)

---

## 📄 Entregables

Al completar el diseño en Pencil, deberías tener:

1. **Archivo `.pen`** con todas las pantallas
2. **Sistema de diseño** (componentes reutilizables de Shadcn)
3. **Paleta de colores** configurada
4. **Tipografía** definida
5. **Espaciado** consistente
6. **Estados** (hover, active, loading, error, empty)
7. **Responsive** (mobile, tablet, desktop)
8. **Documentación** de componentes (nombres, variantes)

---

## 🚀 Próximos Pasos

Una vez completado el diseño en Pencil:
1. Exportar componentes a React (código)
2. Implementar con Shadcn UI real
3. Integrar con backend (APIs)
4. Testing de UI/UX
5. Desplegar a producción

---

**Fecha:** 2026-01-31  
**Versión:** 1.0  
**Autor:** AI Assistant  
**Proyecto:** AI Lead Agent Pro
