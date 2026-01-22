# Frontend: Configuración de Brokers

## 📋 Objetivo

Crear un sistema con dos tipos de usuarios por broker:
1. **Admin**: Configura el agente IA, gestiona usuarios
2. **Agente Inmobiliario**: Trabaja con leads, pipeline, campañas

---

## 👥 Sistema de Roles

### Vistas por Rol

```
┌─────────────────────────────────────────────────────────────────┐
│                         NAVEGACIÓN                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  👔 ADMIN ve:                      🏠 AGENT ve:                 │
│  ├── Dashboard (métricas)          ├── Leads (asignados)       │
│  ├── Leads (todos)                 ├── Pipeline                │
│  ├── Pipeline                      ├── Campañas (solo ver)     │
│  ├── Campañas                      ├── Chat                    │
│  ├── ⚙️ Configuración              └── Citas                   │
│  │   ├── Agente IA                                             │
│  │   ├── Calificación                                          │
│  │   └── Alertas                                               │
│  └── 👤 Usuarios                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Lógica de Navegación

```jsx
// NavBar.jsx - Mostrar opciones según rol
const navigation = [
  { name: 'Dashboard', href: '/dashboard', roles: ['admin'] },
  { name: 'Leads', href: '/leads', roles: ['admin', 'agent'] },
  { name: 'Pipeline', href: '/pipeline', roles: ['admin', 'agent'] },
  { name: 'Campañas', href: '/campaigns', roles: ['admin', 'agent'] },
  { name: 'Chat', href: '/chat', roles: ['admin', 'agent'] },
  { name: 'Configuración', href: '/settings', roles: ['admin'] },  // Solo admin
  { name: 'Usuarios', href: '/users', roles: ['admin'] },          // Solo admin
];

// Filtrar según rol del usuario
const userNavigation = navigation.filter(item => 
  item.roles.includes(currentUser.role)
);
```

---

## 📄 Páginas por Rol

### Solo ADMIN

| Página | Ruta | Descripción |
|--------|------|-------------|
| Dashboard | `/dashboard` | Métricas generales del broker |
| Configuración | `/settings` | Config de agente IA y calificación |
| Usuarios | `/users` | Gestión de usuarios del broker |

### ADMIN + AGENT

| Página | Ruta | Descripción |
|--------|------|-------------|
| Leads | `/leads` | Admin: todos, Agent: asignados |
| Pipeline | `/pipeline` | Board de pipeline |
| Campañas | `/campaigns` | Admin: editar, Agent: solo ver |
| Chat | `/chat` | Conversaciones con leads |

---

## 📋 Lista de Leads (según rol)

### Vista Admin (ve todos los leads del broker)

```
┌─────────────────────────────────────────────────────────────────┐
│  Leads                                    [Filtros] [+ Nuevo]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Juan Pérez (+56 9 1234 5678)                 🔥 Hot      │   │
│  │ Interesado en: Depto 2D, Las Condes                     │   │
│  │ 👤 Asignado a: María González           [Reasignar ▼]   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Ana Silva (+56 9 8765 4321)               🌡️ Warm       │   │
│  │ Interesado en: Casa, Providencia                        │   │
│  │ 👤 Sin asignar                          [Asignar ▼]     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Vista Agente (solo leads asignados)

```
┌─────────────────────────────────────────────────────────────────┐
│  Mis Leads                                         [Filtros]    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Juan Pérez (+56 9 1234 5678)                 🔥 Hot      │   │
│  │ Interesado en: Depto 2D, Las Condes                     │   │
│  │ Última interacción: hace 2 horas                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Componente de Asignación (Solo Admin)

```jsx
// Dropdown para asignar lead a agente
function AssignmentDropdown({ lead, agents, onAssign }) {
  const [isOpen, setIsOpen] = useState(false);
  
  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-sm text-blue-500"
      >
        {lead.assigned_to 
          ? `Asignado a: ${lead.assigned_agent?.name}` 
          : 'Sin asignar'
        }
        <span className="ml-1">▼</span>
      </button>
      
      {isOpen && (
        <div className="absolute bg-white shadow-lg rounded mt-1 z-10">
          {agents.map(agent => (
            <button
              key={agent.id}
              onClick={() => {
                onAssign(lead.id, agent.id);
                setIsOpen(false);
              }}
              className="block w-full px-4 py-2 hover:bg-gray-100 text-left"
            >
              {agent.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## 🎨 Páginas de Admin

### Configuración (ya definida arriba)

La pantalla de configuración con 3 tabs:
1. **Agente** - Prompts del agente IA
2. **Calificación** - Pesos y umbrales
3. **Alertas** - Notificaciones

---

## 🎨 Diseño de UI

### Pantalla Principal: `/settings` o `/configuracion`

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚙️ Configuración                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Tab: Agente] [Tab: Calificación] [Tab: Alertas]              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📑 Tab 1: Configuración del Agente

```
┌─────────────────────────────────────────────────────────────────┐
│  🤖 Configuración del Agente                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  IDENTIDAD                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Nombre del agente:  [____Sofía____]                     │   │
│  │ Rol:               [____asesora inmobiliaria____]       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  CONTEXTO DEL NEGOCIO                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [                                                       ] │   │
│  │ [ Describe qué ofrece tu inmobiliaria, en qué zonas    ] │   │
│  │ [ trabajan, qué tipo de propiedades manejan...         ] │   │
│  │ [                                                       ] │   │
│  └─────────────────────────────────────────────────────────┘   │
│  💡 Ej: "Somos especialistas en propiedades de lujo en Las Condes"│
│                                                                 │
│  REGLAS DE COMUNICACIÓN                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [ - Responde de forma formal                           ] │   │
│  │ [ - Usa "usted" en lugar de "tú"                       ] │   │
│  │ [ - Máximo 2 oraciones por mensaje                     ] │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  RESTRICCIONES                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [ - NUNCA menciones competidores                       ] │   │
│  │ [ - NO des precios exactos sin autorización            ] │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ☑️ Permitir agendar citas automáticamente                     │
│                                                                 │
│  [Vista Previa del Prompt]              [Guardar Cambios]      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📑 Tab 2: Calificación de Leads

```
┌─────────────────────────────────────────────────────────────────┐
│  📊 Calificación de Leads                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  IMPORTANCIA DE DATOS                                          │
│  Ajusta el peso de cada dato en el score del lead              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 💰 Ingresos Mensuales [███████████████████████] 25 pts   │   │
│  │ 📊 Estado DICOM       [████████████████████  ] 20 pts   │   │
│  │ 📞 Teléfono          [███████████████       ] 15 pts   │   │
│  │ 📍 Ubicación         [███████████████       ] 15 pts   │   │
│  │ 💵 Presupuesto       [██████████            ] 10 pts   │   │
│  │ 👤 Nombre            [██████████            ] 10 pts   │   │
│  │ ✉️ Email             [██████████            ] 10 pts   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                      Total: 100 pts             │
│                                                                 │
│  UMBRALES DE SCORE (Temperatura del Lead)                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  🔵 COLD ───|─── 🟡 WARM ───|─── 🟠 HOT ───|─── 🟢      │   │
│  │      0     20              50              75      100  │   │
│  │             ▲               ▲               ▲           │   │
│  │         [slider]       [slider]        [slider]         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ⭐ RANGOS DE INGRESOS (Configurable)                          │
│  Define los rangos de ingreso mensual para tu mercado          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 🔴 Insuficiente:  $0 - $[___500,000___]                │   │
│  │ 🟡 Bajo:         $[___500,000___] - $[___1,000,000___] │   │
│  │ 🟢 Medio:        $[___1,000,000___] - $[___2,000,000___]│   │
│  │ 🟢 Bueno:        $[___2,000,000___] - $[___4,000,000___]│   │
│  │ ⭐ Excelente:    $[___4,000,000___] +                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ⭐ CRITERIOS DE CALIFICACIÓN FINANCIERA                       │
│  Define qué hace que un lead sea CALIFICADO, POTENCIAL o NO    │
│                                                                 │
│  ✅ CALIFICADO (Listo para agendar)                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Ingreso mínimo: $[___1,000,000___] / mes               │   │
│  │ Estado DICOM:   ☑️ Limpio  ☐ Con deuda manejable        │   │
│  │ Deuda máxima:   $[___0___]                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ⚠️ POTENCIAL (Seguimiento futuro)                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Ingreso mínimo: $[___500,000___] / mes                 │   │
│  │ Estado DICOM:   ☑️ Limpio  ☑️ Con deuda manejable        │   │
│  │ Deuda máxima:   $[___500,000___]                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ❌ NO CALIFICADO (Condiciones de rechazo automático)          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ☑️ Ingreso menor a: $[___500,000___] / mes             │   │
│  │ ☑️ Deuda mayor a:   $[___500,000___]                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  PRIORIDAD DE PREGUNTAS                                        │
│  Arrastra para ordenar qué datos pedir primero                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ≡ 1. Nombre                                            │   │
│  │ ≡ 2. Teléfono                                          │   │
│  │ ≡ 3. Email                                             │   │
│  │ ≡ 4. Ubicación                                         │   │
│  │ ≡ 5. Ingresos Mensuales                                │   │
│  │ ≡ 6. Estado DICOM                                      │   │
│  │ ≡ 7. Presupuesto                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│                                        [Guardar Cambios]       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📑 Tab 3: Alertas

```
┌─────────────────────────────────────────────────────────────────┐
│  🔔 Alertas y Notificaciones                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ☑️ Notificarme cuando un lead llegue a HOT                    │
│     Umbral de score: [___70___] pts                            │
│                                                                 │
│  ☑️ Notificarme cuando un lead complete su perfil              │
│                                                                 │
│  📧 Email para notificaciones:                                 │
│  [_______ventas@miinmobiliaria.cl_______]                      │
│                                                                 │
│                                        [Guardar Cambios]       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔌 Integración con API

### Endpoints a consumir

```javascript
// Obtener configuración actual
GET /api/broker/config

// Response:
{
  "broker": {
    "id": 1,
    "name": "InmoChile",
    "contact_phone": "+56912345678"
  },
  "prompt_config": {
    "agent_name": "Sofía",
    "agent_role": "asesora inmobiliaria",
    "business_context": "Ofrecemos propiedades...",
    "behavior_rules": "- Responde en español...",
    "restrictions": "- NUNCA inventes...",
    "enable_appointment_booking": true
  },
  "lead_config": {
    "field_weights": {"name": 10, "phone": 15, ...},
    "thresholds": {"cold_max": 20, "warm_max": 50, ...},
    "field_priority": ["name", "phone", ...],
    "alerts": {
      "on_hot_lead": true,
      "score_threshold": 70,
      "email": "ventas@..."
    }
  }
}
```

```javascript
// Actualizar configuración de prompts
PUT /api/broker/config/prompt
{
  "agent_name": "Carolina",
  "business_context": "Somos la inmobiliaria líder...",
  "behavior_rules": "- Sé formal\n- Usa usted"
}
```

```javascript
// Actualizar calificación de leads
PUT /api/broker/config/leads
{
  "field_weights": {"name": 10, "phone": 25, ...},
  "hot_min_score": 60,
  "field_priority": ["phone", "name", "budget"]
}
```

```javascript
// Preview del prompt
GET /api/broker/config/prompt/preview

// Response:
{
  "prompt": "## ROL\nEres Carolina, asesora de InmoChile...\n\n## CONTEXTO\n..."
}
```

```javascript
// Valores por defecto (para referencia)
GET /api/broker/config/defaults
```

---

## 🧩 Componentes React

### 1. SettingsPage.jsx
```jsx
import { useState, useEffect } from 'react';
import { Tabs, Tab } from './ui/Tabs';
import AgentConfigTab from './AgentConfigTab';
import LeadConfigTab from './LeadConfigTab';
import AlertsConfigTab from './AlertsConfigTab';
import api from '../services/api';

export default function SettingsPage() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('agent');
  
  useEffect(() => {
    loadConfig();
  }, []);
  
  const loadConfig = async () => {
    try {
      const response = await api.get('/broker/config');
      setConfig(response.data);
    } catch (error) {
      console.error('Error loading config:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) return <div>Cargando...</div>;
  
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">⚙️ Configuración</h1>
      
      <Tabs value={activeTab} onChange={setActiveTab}>
        <Tab value="agent" label="🤖 Agente" />
        <Tab value="leads" label="📊 Calificación" />
        <Tab value="alerts" label="🔔 Alertas" />
      </Tabs>
      
      <div className="mt-6">
        {activeTab === 'agent' && (
          <AgentConfigTab 
            config={config?.prompt_config} 
            onSave={loadConfig}
          />
        )}
        {activeTab === 'leads' && (
          <LeadConfigTab 
            config={config?.lead_config}
            onSave={loadConfig}
          />
        )}
        {activeTab === 'alerts' && (
          <AlertsConfigTab 
            config={config?.lead_config?.alerts}
            onSave={loadConfig}
          />
        )}
      </div>
    </div>
  );
}
```

### 2. AgentConfigTab.jsx
```jsx
import { useState } from 'react';
import api from '../services/api';

export default function AgentConfigTab({ config, onSave }) {
  const [formData, setFormData] = useState({
    agent_name: config?.agent_name || 'Sofía',
    agent_role: config?.agent_role || 'asesora inmobiliaria',
    business_context: config?.business_context || '',
    behavior_rules: config?.behavior_rules || '',
    restrictions: config?.restrictions || '',
    enable_appointment_booking: config?.enable_appointment_booking ?? true
  });
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [preview, setPreview] = useState('');
  
  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/broker/config/prompt', formData);
      onSave();
      alert('Configuración guardada');
    } catch (error) {
      alert('Error al guardar');
    } finally {
      setSaving(false);
    }
  };
  
  const handlePreview = async () => {
    try {
      const response = await api.get('/broker/config/prompt/preview');
      setPreview(response.data.prompt);
      setShowPreview(true);
    } catch (error) {
      console.error('Error getting preview:', error);
    }
  };
  
  return (
    <div className="space-y-6">
      {/* Identidad */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Identidad del Agente</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm mb-1">Nombre</label>
            <input
              type="text"
              value={formData.agent_name}
              onChange={e => setFormData({...formData, agent_name: e.target.value})}
              className="w-full border rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm mb-1">Rol</label>
            <input
              type="text"
              value={formData.agent_role}
              onChange={e => setFormData({...formData, agent_role: e.target.value})}
              className="w-full border rounded px-3 py-2"
            />
          </div>
        </div>
      </section>
      
      {/* Contexto */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Contexto del Negocio</h2>
        <textarea
          value={formData.business_context}
          onChange={e => setFormData({...formData, business_context: e.target.value})}
          placeholder="Describe qué ofrece tu inmobiliaria..."
          className="w-full border rounded px-3 py-2 h-24"
        />
        <p className="text-sm text-gray-500 mt-1">
          💡 Ej: "Somos especialistas en propiedades de lujo en Las Condes y Vitacura"
        </p>
      </section>
      
      {/* Reglas */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Reglas de Comunicación</h2>
        <textarea
          value={formData.behavior_rules}
          onChange={e => setFormData({...formData, behavior_rules: e.target.value})}
          placeholder="- Responde de forma formal&#10;- Usa 'usted'&#10;- Máximo 2 oraciones"
          className="w-full border rounded px-3 py-2 h-24 font-mono text-sm"
        />
      </section>
      
      {/* Restricciones */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Restricciones</h2>
        <textarea
          value={formData.restrictions}
          onChange={e => setFormData({...formData, restrictions: e.target.value})}
          placeholder="- NUNCA menciones competidores&#10;- NO des precios sin autorización"
          className="w-full border rounded px-3 py-2 h-24 font-mono text-sm"
        />
      </section>
      
      {/* Herramientas */}
      <section>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={formData.enable_appointment_booking}
            onChange={e => setFormData({...formData, enable_appointment_booking: e.target.checked})}
          />
          <span>Permitir agendar citas automáticamente</span>
        </label>
      </section>
      
      {/* Acciones */}
      <div className="flex gap-4">
        <button
          onClick={handlePreview}
          className="px-4 py-2 border rounded hover:bg-gray-50"
        >
          Vista Previa del Prompt
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {saving ? 'Guardando...' : 'Guardar Cambios'}
        </button>
      </div>
      
      {/* Modal de Preview */}
      {showPreview && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-auto p-6">
            <h3 className="text-lg font-bold mb-4">Preview del System Prompt</h3>
            <pre className="bg-gray-100 p-4 rounded text-sm whitespace-pre-wrap">
              {preview}
            </pre>
            <button
              onClick={() => setShowPreview(false)}
              className="mt-4 px-4 py-2 bg-gray-200 rounded"
            >
              Cerrar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

### 3. LeadConfigTab.jsx
```jsx
import { useState } from 'react';
import api from '../services/api';

const FIELD_LABELS = {
  name: '👤 Nombre',
  phone: '📞 Teléfono',
  email: '✉️ Email',
  location: '📍 Ubicación',
  monthly_income: '💰 Ingresos Mensuales',
  dicom_status: '📊 Estado DICOM',
  budget: '💵 Presupuesto',
  property_type: '🏠 Tipo',
  bedrooms: '🛏️ Dormitorios',
};

export default function LeadConfigTab({ config, onSave }) {
  const [weights, setWeights] = useState(config?.field_weights || {
    name: 10, phone: 15, email: 10, location: 15, 
    monthly_income: 25, dicom_status: 20, budget: 10
  });
  
  const [thresholds, setThresholds] = useState(config?.thresholds || {
    cold_max: 20, warm_max: 50, hot_min: 50, qualified_min: 75
  });
  
  // ⭐ NUEVO: Rangos de ingresos configurables
  const [incomeRanges, setIncomeRanges] = useState(config?.income_ranges || {
    insufficient: { min: 0, max: 500000, label: 'Insuficiente' },
    low: { min: 500000, max: 1000000, label: 'Bajo' },
    medium: { min: 1000000, max: 2000000, label: 'Medio' },
    good: { min: 2000000, max: 4000000, label: 'Bueno' },
    excellent: { min: 4000000, max: null, label: 'Excelente' },
  });
  
  // ⭐ NUEVO: Criterios de calificación configurables
  const [qualificationCriteria, setQualificationCriteria] = useState(
    config?.qualification_criteria || {
      calificado: {
        min_monthly_income: 1000000,
        dicom_status: ['clean'],
        max_debt_amount: 0
      },
      potencial: {
        min_monthly_income: 500000,
        dicom_status: ['clean', 'has_debt'],
        max_debt_amount: 500000
      },
      no_calificado: {
        conditions: [
          { monthly_income_below: 500000 },
          { debt_amount_above: 500000 }
        ]
      }
    }
  );
  
  const [priority, setPriority] = useState(config?.field_priority || [
    'name', 'phone', 'email', 'location', 'monthly_income', 'dicom_status', 'budget'
  ]);
  
  const [saving, setSaving] = useState(false);
  
  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/broker/config/leads', {
        field_weights: weights,
        cold_max_score: thresholds.cold_max,
        warm_max_score: thresholds.warm_max,
        hot_min_score: thresholds.hot_min,
        qualified_min_score: thresholds.qualified_min,
        field_priority: priority,
        income_ranges: incomeRanges,  // ⭐ NUEVO
        qualification_criteria: qualificationCriteria,  // ⭐ NUEVO
      });
      onSave();
      alert('Configuración guardada');
    } catch (error) {
      alert('Error al guardar');
    } finally {
      setSaving(false);
    }
  };
  
  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
  
  return (
    <div className="space-y-8">
      {/* Pesos de campos */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Importancia de Datos</h2>
        <p className="text-sm text-gray-500 mb-4">
          Ajusta el peso de cada dato en el score del lead
        </p>
        <div className="space-y-3">
          {Object.entries(weights).map(([field, value]) => (
            <div key={field} className="flex items-center gap-4">
              <span className="w-40">{FIELD_LABELS[field] || field}</span>
              <input
                type="range"
                min="0"
                max="50"
                value={value}
                onChange={e => setWeights({...weights, [field]: parseInt(e.target.value)})}
                className="flex-1"
              />
              <span className="w-16 text-right">{value} pts</span>
            </div>
          ))}
        </div>
        <p className="text-sm text-gray-500 mt-2">
          Total: {totalWeight} pts
        </p>
      </section>
      
      {/* Umbrales de Score */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Umbrales de Score (Temperatura)</h2>
        <div className="bg-gray-100 p-4 rounded">
          <div className="flex items-center justify-between mb-4">
            <span className="text-blue-500">🔵 COLD</span>
            <span className="text-yellow-500">🟡 WARM</span>
            <span className="text-orange-500">🟠 HOT</span>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm mb-1">COLD hasta:</label>
              <input
                type="number"
                value={thresholds.cold_max}
                onChange={e => setThresholds({...thresholds, cold_max: parseInt(e.target.value)})}
                className="w-full border rounded px-2 py-1"
              />
            </div>
            <div>
              <label className="block text-sm mb-1">WARM hasta:</label>
              <input
                type="number"
                value={thresholds.warm_max}
                onChange={e => setThresholds({...thresholds, warm_max: parseInt(e.target.value)})}
                className="w-full border rounded px-2 py-1"
              />
            </div>
            <div>
              <label className="block text-sm mb-1">HOT desde:</label>
              <input
                type="number"
                value={thresholds.hot_min}
                onChange={e => setThresholds({...thresholds, hot_min: parseInt(e.target.value)})}
                className="w-full border rounded px-2 py-1"
              />
            </div>
          </div>
        </div>
      </section>
      
      {/* ⭐ NUEVO: Rangos de Ingresos */}
      <section>
        <h2 className="text-lg font-semibold mb-3">⭐ Rangos de Ingresos</h2>
        <p className="text-sm text-gray-500 mb-4">
          Define los rangos de ingreso mensual para tu mercado
        </p>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4 items-center bg-red-50 p-3 rounded">
            <span className="font-medium">🔴 Insuficiente:</span>
            <div className="flex items-center gap-2">
              <span>$0 - $</span>
              <input
                type="number"
                value={incomeRanges.insufficient.max}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  insufficient: {...incomeRanges.insufficient, max: parseInt(e.target.value)}
                })}
                className="w-32 border rounded px-2 py-1"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4 items-center bg-yellow-50 p-3 rounded">
            <span className="font-medium">🟡 Bajo:</span>
            <div className="flex items-center gap-2">
              <span>$</span>
              <input
                type="number"
                value={incomeRanges.low.min}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  low: {...incomeRanges.low, min: parseInt(e.target.value)}
                })}
                className="w-32 border rounded px-2 py-1"
              />
              <span>- $</span>
              <input
                type="number"
                value={incomeRanges.low.max}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  low: {...incomeRanges.low, max: parseInt(e.target.value)}
                })}
                className="w-32 border rounded px-2 py-1"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4 items-center bg-green-50 p-3 rounded">
            <span className="font-medium">🟢 Medio:</span>
            <div className="flex items-center gap-2">
              <span>$</span>
              <input
                type="number"
                value={incomeRanges.medium.min}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  medium: {...incomeRanges.medium, min: parseInt(e.target.value)}
                })}
                className="w-32 border rounded px-2 py-1"
              />
              <span>- $</span>
              <input
                type="number"
                value={incomeRanges.medium.max}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  medium: {...incomeRanges.medium, max: parseInt(e.target.value)}
                })}
                className="w-32 border rounded px-2 py-1"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4 items-center bg-green-100 p-3 rounded">
            <span className="font-medium">🟢 Bueno:</span>
            <div className="flex items-center gap-2">
              <span>$</span>
              <input
                type="number"
                value={incomeRanges.good.min}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  good: {...incomeRanges.good, min: parseInt(e.target.value)}
                })}
                className="w-32 border rounded px-2 py-1"
              />
              <span>- $</span>
              <input
                type="number"
                value={incomeRanges.good.max}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  good: {...incomeRanges.good, max: parseInt(e.target.value)}
                })}
                className="w-32 border rounded px-2 py-1"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4 items-center bg-blue-50 p-3 rounded">
            <span className="font-medium">⭐ Excelente:</span>
            <div className="flex items-center gap-2">
              <span>$</span>
              <input
                type="number"
                value={incomeRanges.excellent.min}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  excellent: {...incomeRanges.excellent, min: parseInt(e.target.value)}
                })}
                className="w-32 border rounded px-2 py-1"
              />
              <span>+</span>
            </div>
          </div>
        </div>
      </section>
      
      {/* ⭐ NUEVO: Criterios de Calificación */}
      <section>
        <h2 className="text-lg font-semibold mb-3">⭐ Criterios de Calificación Financiera</h2>
        
        {/* CALIFICADO */}
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded">
          <h3 className="font-semibold text-green-700 mb-3">✅ CALIFICADO (Listo para agendar)</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-4">
              <label className="w-48">Ingreso mínimo:</label>
              <span>$</span>
              <input
                type="number"
                value={qualificationCriteria.calificado.min_monthly_income}
                onChange={e => setQualificationCriteria({
                  ...qualificationCriteria,
                  calificado: {
                    ...qualificationCriteria.calificado,
                    min_monthly_income: parseInt(e.target.value)
                  }
                })}
                className="w-40 border rounded px-2 py-1"
              />
              <span>/ mes</span>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="w-48">Estado DICOM:</label>
              <label>
                <input
                  type="checkbox"
                  checked={qualificationCriteria.calificado.dicom_status.includes('clean')}
                  onChange={e => {
                    const newStatuses = e.target.checked 
                      ? [...qualificationCriteria.calificado.dicom_status, 'clean']
                      : qualificationCriteria.calificado.dicom_status.filter(s => s !== 'clean');
                    setQualificationCriteria({
                      ...qualificationCriteria,
                      calificado: {...qualificationCriteria.calificado, dicom_status: newStatuses}
                    });
                  }}
                />
                Limpio
              </label>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="w-48">Deuda máxima:</label>
              <span>$</span>
              <input
                type="number"
                value={qualificationCriteria.calificado.max_debt_amount}
                onChange={e => setQualificationCriteria({
                  ...qualificationCriteria,
                  calificado: {
                    ...qualificationCriteria.calificado,
                    max_debt_amount: parseInt(e.target.value)
                  }
                })}
                className="w-40 border rounded px-2 py-1"
              />
            </div>
          </div>
        </div>
        
        {/* POTENCIAL */}
        <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded">
          <h3 className="font-semibold text-yellow-700 mb-3">⚠️ POTENCIAL (Seguimiento futuro)</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-4">
              <label className="w-48">Ingreso mínimo:</label>
              <span>$</span>
              <input
                type="number"
                value={qualificationCriteria.potencial.min_monthly_income}
                onChange={e => setQualificationCriteria({
                  ...qualificationCriteria,
                  potencial: {
                    ...qualificationCriteria.potencial,
                    min_monthly_income: parseInt(e.target.value)
                  }
                })}
                className="w-40 border rounded px-2 py-1"
              />
              <span>/ mes</span>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="w-48">Estado DICOM:</label>
              <label className="mr-4">
                <input
                  type="checkbox"
                  checked={qualificationCriteria.potencial.dicom_status.includes('clean')}
                  readOnly
                />
                Limpio
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={qualificationCriteria.potencial.dicom_status.includes('has_debt')}
                  readOnly
                />
                Con deuda manejable
              </label>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="w-48">Deuda máxima:</label>
              <span>$</span>
              <input
                type="number"
                value={qualificationCriteria.potencial.max_debt_amount}
                onChange={e => setQualificationCriteria({
                  ...qualificationCriteria,
                  potencial: {
                    ...qualificationCriteria.potencial,
                    max_debt_amount: parseInt(e.target.value)
                  }
                })}
                className="w-40 border rounded px-2 py-1"
              />
            </div>
          </div>
        </div>
        
        {/* NO CALIFICADO */}
        <div className="p-4 bg-red-50 border border-red-200 rounded">
          <h3 className="font-semibold text-red-700 mb-3">❌ NO CALIFICADO (Rechazo automático)</h3>
          <div className="space-y-2">
            <label className="flex items-center gap-4">
              <input type="checkbox" checked readOnly />
              <span>Ingreso menor a: $</span>
              <input
                type="number"
                value={qualificationCriteria.no_calificado.conditions[0]?.monthly_income_below || 500000}
                onChange={e => {
                  const newConditions = [...qualificationCriteria.no_calificado.conditions];
                  newConditions[0] = { monthly_income_below: parseInt(e.target.value) };
                  setQualificationCriteria({
                    ...qualificationCriteria,
                    no_calificado: { conditions: newConditions }
                  });
                }}
                className="w-40 border rounded px-2 py-1"
              />
              <span>/ mes</span>
            </label>
            
            <label className="flex items-center gap-4">
              <input type="checkbox" checked readOnly />
              <span>Deuda mayor a: $</span>
              <input
                type="number"
                value={qualificationCriteria.no_calificado.conditions[1]?.debt_amount_above || 500000}
                onChange={e => {
                  const newConditions = [...qualificationCriteria.no_calificado.conditions];
                  newConditions[1] = { debt_amount_above: parseInt(e.target.value) };
                  setQualificationCriteria({
                    ...qualificationCriteria,
                    no_calificado: { conditions: newConditions }
                  });
                }}
                className="w-40 border rounded px-2 py-1"
              />
            </label>
          </div>
        </div>
      </section>
      
      {/* Prioridad de preguntas */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Prioridad de Preguntas</h2>
        <p className="text-sm text-gray-500 mb-4">
          Orden en que el agente preguntará los datos
        </p>
        <div className="space-y-2">
          {priority.map((field, index) => (
            <div 
              key={field}
              className="flex items-center gap-3 bg-gray-50 p-2 rounded"
            >
              <span className="text-gray-400">≡</span>
              <span>{index + 1}.</span>
              <span>{FIELD_LABELS[field] || field}</span>
              <div className="ml-auto flex gap-1">
                <button
                  onClick={() => {
                    if (index > 0) {
                      const newPriority = [...priority];
                      [newPriority[index], newPriority[index - 1]] = 
                        [newPriority[index - 1], newPriority[index]];
                      setPriority(newPriority);
                    }
                  }}
                  disabled={index === 0}
                  className="px-2 py-1 text-sm border rounded disabled:opacity-30"
                >
                  ↑
                </button>
                <button
                  onClick={() => {
                    if (index < priority.length - 1) {
                      const newPriority = [...priority];
                      [newPriority[index], newPriority[index + 1]] = 
                        [newPriority[index + 1], newPriority[index]];
                      setPriority(newPriority);
                    }
                  }}
                  disabled={index === priority.length - 1}
                  className="px-2 py-1 text-sm border rounded disabled:opacity-30"
                >
                  ↓
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
      
      {/* Guardar */}
      <button
        onClick={handleSave}
        disabled={saving}
        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
      >
        {saving ? 'Guardando...' : 'Guardar Cambios'}
      </button>
    </div>
  );
}
```

---

## 📁 Estructura de Archivos

```
frontend/src/
├── pages/
│   └── SettingsPage.jsx          # Página principal
├── components/
│   ├── AgentConfigTab.jsx        # Tab de configuración de agente
│   ├── LeadConfigTab.jsx         # Tab de calificación
│   ├── AlertsConfigTab.jsx       # Tab de alertas
│   └── ui/
│       └── Tabs.jsx              # Componente de tabs
└── services/
    └── api.js                    # Ya existe, agregar endpoints
```

---

---

## 👤 Página de Gestión de Usuarios (Solo Admin)

### UI: `/users`

```
┌─────────────────────────────────────────────────────────────────┐
│  👤 Usuarios del Equipo                        [+ Nuevo Usuario]│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 📧 juan@inmochile.cl                                     │   │
│  │ Juan Pérez                                               │   │
│  │ 🏷️ Admin                              [Editar] [Desactivar]│   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 📧 maria@inmochile.cl                                    │   │
│  │ María González                                           │   │
│  │ 🏷️ Agente                             [Editar] [Desactivar]│   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 📧 pedro@inmochile.cl                                    │   │
│  │ Pedro Soto                                               │   │
│  │ 🏷️ Agente                             [Editar] [Desactivar]│   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Modal: Crear/Editar Usuario

```
┌─────────────────────────────────────────────────────────────────┐
│  ➕ Nuevo Usuario                                          [X]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Nombre completo:                                              │
│  [_________________________________]                           │
│                                                                 │
│  Email:                                                        │
│  [_________________________________]                           │
│                                                                 │
│  Contraseña:                                                   │
│  [_________________________________]                           │
│                                                                 │
│  Rol:                                                          │
│  ○ Admin - Puede configurar el agente IA y gestionar usuarios  │
│  ● Agente - Trabaja con leads, pipeline y campañas             │
│                                                                 │
│                              [Cancelar]  [Crear Usuario]       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Componente UsersPage.jsx

```jsx
// frontend/src/pages/UsersPage.jsx

import { useState, useEffect } from 'react';
import api from '../services/api';

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  
  useEffect(() => {
    loadUsers();
  }, []);
  
  const loadUsers = async () => {
    const response = await api.get('/broker/users');
    setUsers(response.data);
  };
  
  const handleCreate = async (userData) => {
    await api.post('/broker/users', userData);
    loadUsers();
    setShowModal(false);
  };
  
  const handleUpdate = async (userId, updates) => {
    await api.put(`/broker/users/${userId}`, updates);
    loadUsers();
    setEditingUser(null);
  };
  
  const handleDeactivate = async (userId) => {
    if (confirm('¿Desactivar este usuario?')) {
      await api.delete(`/broker/users/${userId}`);
      loadUsers();
    }
  };
  
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">👤 Usuarios del Equipo</h1>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-blue-500 text-white rounded"
        >
          + Nuevo Usuario
        </button>
      </div>
      
      <div className="space-y-4">
        {users.map(user => (
          <div key={user.id} className="border rounded-lg p-4">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-gray-500">📧 {user.email}</p>
                <p className="font-semibold">{user.name}</p>
                <span className={`inline-block px-2 py-1 text-xs rounded ${
                  user.role === 'admin' 
                    ? 'bg-purple-100 text-purple-700' 
                    : 'bg-green-100 text-green-700'
                }`}>
                  {user.role === 'admin' ? '👔 Admin' : '🏠 Agente'}
                </span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setEditingUser(user)}
                  className="px-3 py-1 border rounded text-sm"
                >
                  Editar
                </button>
                <button
                  onClick={() => handleDeactivate(user.id)}
                  className="px-3 py-1 border rounded text-sm text-red-500"
                >
                  Desactivar
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* Modal para crear/editar */}
      {(showModal || editingUser) && (
        <UserModal
          user={editingUser}
          onSave={editingUser ? handleUpdate : handleCreate}
          onClose={() => {
            setShowModal(false);
            setEditingUser(null);
          }}
        />
      )}
    </div>
  );
}

function UserModal({ user, onSave, onClose }) {
  const [formData, setFormData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    password: '',
    role: user?.role || 'agent'
  });
  
  const handleSubmit = () => {
    if (user) {
      onSave(user.id, formData);
    } else {
      onSave(formData);
    }
  };
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-lg font-bold mb-4">
          {user ? 'Editar Usuario' : '➕ Nuevo Usuario'}
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm mb-1">Nombre completo</label>
            <input
              type="text"
              value={formData.name}
              onChange={e => setFormData({...formData, name: e.target.value})}
              className="w-full border rounded px-3 py-2"
            />
          </div>
          
          <div>
            <label className="block text-sm mb-1">Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={e => setFormData({...formData, email: e.target.value})}
              className="w-full border rounded px-3 py-2"
              disabled={!!user}
            />
          </div>
          
          {!user && (
            <div>
              <label className="block text-sm mb-1">Contraseña</label>
              <input
                type="password"
                value={formData.password}
                onChange={e => setFormData({...formData, password: e.target.value})}
                className="w-full border rounded px-3 py-2"
              />
            </div>
          )}
          
          <div>
            <label className="block text-sm mb-2">Rol</label>
            <div className="space-y-2">
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  value="admin"
                  checked={formData.role === 'admin'}
                  onChange={e => setFormData({...formData, role: e.target.value})}
                  className="mt-1"
                />
                <div>
                  <span className="font-medium">Admin</span>
                  <p className="text-sm text-gray-500">
                    Puede configurar el agente IA y gestionar usuarios
                  </p>
                </div>
              </label>
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  value="agent"
                  checked={formData.role === 'agent'}
                  onChange={e => setFormData({...formData, role: e.target.value})}
                  className="mt-1"
                />
                <div>
                  <span className="font-medium">Agente</span>
                  <p className="text-sm text-gray-500">
                    Trabaja con leads, pipeline y campañas
                  </p>
                </div>
              </label>
            </div>
          </div>
        </div>
        
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 border rounded"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            className="px-4 py-2 bg-blue-500 text-white rounded"
          >
            {user ? 'Guardar Cambios' : 'Crear Usuario'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## 🔐 Protección de Rutas

```jsx
// frontend/src/components/ProtectedRoute.jsx

import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function ProtectedRoute({ children, allowedRoles = [] }) {
  const { user, isLoading } = useAuth();
  
  if (isLoading) {
    return <div>Cargando...</div>;
  }
  
  if (!user) {
    return <Navigate to="/login" />;
  }
  
  // Si hay roles permitidos y el usuario no tiene uno de ellos
  if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    return <Navigate to="/leads" />;  // Redirigir a página que sí puede ver
  }
  
  return children;
}

// Uso en App.jsx
<Route 
  path="/settings" 
  element={
    <ProtectedRoute allowedRoles={['admin']}>
      <SettingsPage />
    </ProtectedRoute>
  } 
/>

<Route 
  path="/users" 
  element={
    <ProtectedRoute allowedRoles={['admin']}>
      <UsersPage />
    </ProtectedRoute>
  } 
/>
```

---

## ✅ Checklist

### Roles y Permisos
- [ ] Guardar `role` en estado de autenticación
- [ ] Crear `ProtectedRoute` para rutas protegidas
- [ ] Filtrar navegación según rol

### Páginas Admin
- [ ] Crear `SettingsPage.jsx` con tabs
- [ ] Crear `AgentConfigTab.jsx`
- [ ] Crear `LeadConfigTab.jsx`
- [ ] Crear `AlertsConfigTab.jsx`
- [ ] Crear `UsersPage.jsx`
- [ ] Crear `UserModal.jsx`

### Integración API
- [ ] Endpoint GET `/broker/config`
- [ ] Endpoint PUT `/broker/config/prompt`
- [ ] Endpoint PUT `/broker/config/leads`
- [ ] Endpoint GET `/broker/users`
- [ ] Endpoint POST `/broker/users`
- [ ] Endpoint PUT `/broker/users/:id`
- [ ] Endpoint DELETE `/broker/users/:id`

### Navegación
- [ ] Actualizar `NavBar.jsx` para filtrar por rol
- [ ] Agregar rutas en `App.jsx`

### UX
- [ ] Preview del prompt antes de guardar
- [ ] Sliders para pesos de campos
- [ ] Drag & drop para prioridad de campos
- [ ] Feedback visual al guardar
- [ ] Confirmación antes de desactivar usuario
- [ ] Dropdown de asignación de leads (solo admin)
- [ ] Título "Mis Leads" vs "Leads" según rol

---

## 🎨 Consideraciones de UX

1. **Valores por defecto**: Mostrar placeholders con valores por defecto
2. **Feedback visual**: Indicar cuando se guarda correctamente
3. **Preview**: Permitir ver cómo queda el prompt antes de guardar
4. **Validación**: Validar que los umbrales estén en orden (cold < warm < hot)
5. **Drag & Drop**: Para la prioridad de campos, idealmente con drag & drop
6. **Responsive**: Asegurar que funcione en móvil
7. **Roles claros**: Indicar visualmente qué puede hacer cada rol

