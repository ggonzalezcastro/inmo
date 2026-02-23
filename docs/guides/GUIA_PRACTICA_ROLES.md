# 🚀 Guía Práctica: Crear Broker, Admin y Agente

## 📋 Índice
1. [Setup Inicial (Superadmin)](#1-setup-inicial-superadmin)
2. [Crear Broker](#2-crear-broker)
3. [Crear Admin del Broker](#3-crear-admin-del-broker)
4. [Login como Admin](#4-login-como-admin)
5. [Configurar el Broker (Admin)](#5-configurar-el-broker-admin)
6. [Crear Agentes (Admin)](#6-crear-agentes-admin)
7. [Login como Agente](#7-login-como-agente)
8. [Probar el Sistema](#8-probar-el-sistema)

---

## 1️⃣ Setup Inicial (Superadmin)

### Crear tu usuario Superadmin

**Opción A: Directamente en la BD (Primera vez)**
```sql
-- En PostgreSQL
INSERT INTO users (email, hashed_password, name, role, is_active, created_at, updated_at)
VALUES (
    'superadmin@tuempresa.com',
    '$2b$12$...hash_de_tu_password...',  -- Genera con bcrypt
    'Super Admin',
    'superadmin',
    true,
    NOW(),
    NOW()
);
```

**Opción B: Usando script Python**
```python
# backend/scripts/create_superadmin.py
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.user import User, UserRole
from app.config import settings
import bcrypt

async def create_superadmin():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Hash password
        password = "tu_password_seguro"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create superadmin
        superadmin = User(
            email="superadmin@tuempresa.com",
            hashed_password=hashed,
            name="Super Admin",
            role=UserRole.SUPERADMIN.value,
            is_active=True
        )
        
        db.add(superadmin)
        await db.commit()
        
        print(f"✅ Superadmin created: {superadmin.email}")

if __name__ == "__main__":
    asyncio.run(create_superadmin())
```

**Ejecutar:**
```bash
cd backend
python scripts/create_superadmin.py
```

---

## 2️⃣ Crear Broker

### Login como Superadmin

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "superadmin@tuempresa.com",
    "password": "tu_password_seguro"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "superadmin@tuempresa.com",
    "name": "Super Admin",
    "role": "superadmin",
    "broker_id": null
  }
}
```

**Guarda el token:**
```bash
export TOKEN="eyJhbGciOiJIUzI1NiIs..."
```

---

### Crear el Broker

**Request:**
```bash
curl -X POST http://localhost:8000/api/brokers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "InmoChile",
    "slug": "inmochile",
    "phone": "+56912345678",
    "email": "contacto@inmochile.cl",
    "website": "https://inmochile.cl",
    "address": "Av. Providencia 1234, Santiago",
    "timezone": "America/Santiago",
    "currency": "CLP",
    "country": "Chile",
    "language": "es"
  }'
```

**Response:**
```json
{
  "id": 1,
  "name": "InmoChile",
  "slug": "inmochile",
  "phone": "+56912345678",
  "email": "contacto@inmochile.cl",
  "is_active": true,
  "created_at": "2024-12-04T10:00:00Z"
}
```

**Guarda el broker_id:**
```bash
export BROKER_ID=1
```

---

## 3️⃣ Crear Admin del Broker

### Crear usuario Admin

**Request:**
```bash
curl -X POST http://localhost:8000/api/broker/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "email": "juan@inmochile.cl",
    "password": "admin123",
    "name": "Juan Pérez",
    "role": "admin",
    "broker_id": 1
  }'
```

**Response:**
```json
{
  "id": 2,
  "email": "juan@inmochile.cl",
  "name": "Juan Pérez",
  "role": "admin",
  "broker_id": 1,
  "is_active": true,
  "created_at": "2024-12-04T10:05:00Z"
}
```

---

## 4️⃣ Login como Admin

### Cerrar sesión de Superadmin y entrar como Admin

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "juan@inmochile.cl",
    "password": "admin123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 2,
    "email": "juan@inmochile.cl",
    "name": "Juan Pérez",
    "role": "admin",
    "broker_id": 1
  }
}
```

**Guarda el nuevo token:**
```bash
export ADMIN_TOKEN="eyJhbGciOiJIUzI1NiIs..."
```

---

## 5️⃣ Configurar el Broker (Admin)

### 5.1 Ver Configuración Actual

**Request:**
```bash
curl -X GET http://localhost:8000/api/broker/config \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Response:**
```json
{
  "broker": {
    "id": 1,
    "name": "InmoChile",
    "phone": "+56912345678",
    "email": "contacto@inmochile.cl"
  },
  "prompt_config": {
    "agent_name": "Sofía",
    "agent_role": "asesora inmobiliaria",
    "business_context": null,
    "behavior_rules": null,
    "enable_appointment_booking": true
  },
  "lead_config": {
    "field_weights": {
      "name": 10,
      "phone": 15,
      "email": 10,
      "location": 15,
      "monthly_income": 25,
      "dicom_status": 20,
      "budget": 10
    },
    "cold_max_score": 20,
    "warm_max_score": 50,
    "hot_min_score": 50,
    "income_ranges": {
      "insufficient": {"min": 0, "max": 500000},
      "low": {"min": 500000, "max": 1000000},
      "medium": {"min": 1000000, "max": 2000000},
      "good": {"min": 2000000, "max": 4000000},
      "excellent": {"min": 4000000, "max": null}
    },
    "qualification_criteria": {
      "calificado": {
        "min_monthly_income": 1000000,
        "dicom_status": ["clean"],
        "max_debt_amount": 0
      },
      "potencial": {
        "min_monthly_income": 500000,
        "dicom_status": ["clean", "has_debt"],
        "max_debt_amount": 500000
      }
    }
  }
}
```

---

### 5.2 Configurar el Agente IA

**Request:**
```bash
curl -X PUT http://localhost:8000/api/broker/config/prompt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "agent_name": "Carolina",
    "agent_role": "asesora inmobiliaria senior",
    "business_context": "Somos InmoChile, la inmobiliaria líder en Santiago. Nos especializamos en propiedades de lujo en Las Condes, Vitacura y Lo Barnechea. Contamos con más de 15 años de experiencia.",
    "behavior_rules": "- Sé formal y usa \"usted\"\n- Máximo 2 oraciones por mensaje\n- Responde rápido y conciso\n- Siempre confirma lo que ya tienes antes de preguntar",
    "restrictions": "- NUNCA inventes precios\n- NO menciones competidores\n- NO des asesoría legal o financiera\n- NO hagas promesas de aprobación crediticia",
    "enable_appointment_booking": true
  }'
```

**Response:**
```json
{
  "message": "Configuración de prompts actualizada",
  "updated_fields": [
    "agent_name",
    "business_context",
    "behavior_rules",
    "restrictions"
  ]
}
```

---

### 5.3 Configurar Criterios de Calificación

**Request:**
```bash
curl -X PUT http://localhost:8000/api/broker/config/leads \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "field_weights": {
      "name": 10,
      "phone": 15,
      "email": 10,
      "location": 15,
      "monthly_income": 30,
      "dicom_status": 20,
      "budget": 10
    },
    "cold_max_score": 25,
    "warm_max_score": 55,
    "hot_min_score": 70,
    "income_ranges": {
      "insufficient": {"min": 0, "max": 800000, "label": "Insuficiente"},
      "low": {"min": 800000, "max": 1500000, "label": "Bajo"},
      "medium": {"min": 1500000, "max": 3000000, "label": "Medio"},
      "good": {"min": 3000000, "max": 6000000, "label": "Bueno"},
      "excellent": {"min": 6000000, "max": null, "label": "Excelente"}
    },
    "qualification_criteria": {
      "calificado": {
        "min_monthly_income": 1500000,
        "dicom_status": ["clean"],
        "max_debt_amount": 0
      },
      "potencial": {
        "min_monthly_income": 800000,
        "dicom_status": ["clean", "has_debt"],
        "max_debt_amount": 800000
      },
      "no_calificado": {
        "conditions": [
          {"monthly_income_below": 800000},
          {"debt_amount_above": 800000}
        ]
      }
    },
    "max_acceptable_debt": 800000,
    "alert_on_hot_lead": true,
    "alert_score_threshold": 75,
    "alert_email": "alertas@inmochile.cl"
  }'
```

**Response:**
```json
{
  "message": "Configuración de calificación actualizada",
  "summary": {
    "calificado_min_income": 1500000,
    "potencial_min_income": 800000,
    "max_acceptable_debt": 800000,
    "hot_threshold": 70
  }
}
```

---

### 5.4 Ver Preview del Prompt

**Request:**
```bash
curl -X GET http://localhost:8000/api/broker/config/prompt/preview \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Response:**
```json
{
  "prompt": "## ROL\nEres Carolina, asesora inmobiliaria senior de InmoChile.\n\n## CONTEXTO\nSomos InmoChile, la inmobiliaria líder en Santiago. Nos especializamos en propiedades de lujo en Las Condes, Vitacura y Lo Barnechea...\n\n## REGLAS\n- Sé formal y usa \"usted\"\n- Máximo 2 oraciones por mensaje...\n\n## RESTRICCIONES\n- NUNCA inventes precios...\n\n## HERRAMIENTAS\n- get_available_appointment_slots\n- create_appointment..."
}
```

---

## 6️⃣ Crear Agentes (Admin)

### 6.1 Crear Agente 1: María

**Request:**
```bash
curl -X POST http://localhost:8000/api/broker/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "email": "maria@inmochile.cl",
    "password": "agent123",
    "name": "María González",
    "role": "agent"
  }'
```

**Response:**
```json
{
  "id": 3,
  "email": "maria@inmochile.cl",
  "name": "María González",
  "role": "agent",
  "broker_id": 1,
  "is_active": true
}
```

---

### 6.2 Crear Agente 2: Pedro

**Request:**
```bash
curl -X POST http://localhost:8000/api/broker/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "email": "pedro@inmochile.cl",
    "password": "agent456",
    "name": "Pedro Soto",
    "role": "agent"
  }'
```

**Response:**
```json
{
  "id": 4,
  "email": "pedro@inmochile.cl",
  "name": "Pedro Soto",
  "role": "agent",
  "broker_id": 1,
  "is_active": true
}
```

---

### 6.3 Ver Todos los Usuarios del Broker

**Request:**
```bash
curl -X GET http://localhost:8000/api/broker/users \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Response:**
```json
[
  {
    "id": 2,
    "email": "juan@inmochile.cl",
    "name": "Juan Pérez",
    "role": "admin",
    "broker_id": 1,
    "is_active": true
  },
  {
    "id": 3,
    "email": "maria@inmochile.cl",
    "name": "María González",
    "role": "agent",
    "broker_id": 1,
    "is_active": true
  },
  {
    "id": 4,
    "email": "pedro@inmochile.cl",
    "name": "Pedro Soto",
    "role": "agent",
    "broker_id": 1,
    "is_active": true
  }
]
```

---

## 7️⃣ Login como Agente

### Entrar como María (Agente)

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "maria@inmochile.cl",
    "password": "agent123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 3,
    "email": "maria@inmochile.cl",
    "name": "María González",
    "role": "agent",
    "broker_id": 1
  }
}
```

**Guarda el token del agente:**
```bash
export AGENT_TOKEN="eyJhbGciOiJIUzI1NiIs..."
```

---

## 8️⃣ Probar el Sistema

### 8.1 Como Agente: Ver Mis Leads

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/leads \
  -H "Authorization: Bearer $AGENT_TOKEN"
```

**Response:**
```json
{
  "leads": [
    {
      "id": 1,
      "name": "Cliente Test",
      "phone": "+56987654321",
      "status": "warm",
      "pipeline_stage": "perfilamiento",
      "assigned_to": 3,
      "assigned_agent": {
        "id": 3,
        "name": "María González"
      }
    }
  ],
  "total": 1,
  "message": "Mostrando solo leads asignados a ti"
}
```

---

### 8.2 Como Agente: Intentar Ver Configuración (Debe Fallar)

**Request:**
```bash
curl -X GET http://localhost:8000/api/broker/config \
  -H "Authorization: Bearer $AGENT_TOKEN"
```

**Response:**
```json
{
  "detail": "Se requiere rol de administrador"
}
```

**Status:** `403 Forbidden` ✅ Correcto!

---

### 8.3 Como Admin: Asignar Lead a María

**Request:**
```bash
curl -X PUT http://localhost:8000/api/v1/leads/1/assign \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "agent_id": 3
  }'
```

**Response:**
```json
{
  "message": "Lead asignado exitosamente",
  "lead_id": 1,
  "assigned_to": 3,
  "assigned_agent": {
    "id": 3,
    "name": "María González"
  }
}
```

---

### 8.4 Como Admin: Ver Todos los Leads

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/leads \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Response:**
```json
{
  "leads": [
    {
      "id": 1,
      "name": "Cliente Test 1",
      "assigned_to": 3
    },
    {
      "id": 2,
      "name": "Cliente Test 2",
      "assigned_to": 4
    },
    {
      "id": 3,
      "name": "Cliente Test 3",
      "assigned_to": null
    }
  ],
  "total": 3,
  "message": "Mostrando todos los leads del broker"
}
```

---

## 📊 Resumen de Permisos

| Acción | Superadmin | Admin | Agent |
|--------|------------|-------|-------|
| Crear brokers | ✅ | ❌ | ❌ |
| Ver configuración | ✅ | ✅ | ❌ |
| Editar configuración | ✅ | ✅ | ❌ |
| Crear usuarios | ✅ | ✅ (solo de su broker) | ❌ |
| Ver todos los leads | ✅ | ✅ (solo de su broker) | ❌ |
| Ver leads asignados | ✅ | ✅ | ✅ |
| Asignar leads | ✅ | ✅ | ❌ |
| Chat con leads | ✅ | ✅ | ✅ |
| Pipeline | ✅ | ✅ | ✅ |
| Campañas | ✅ | ✅ | ✅ (solo ver) |

---

## 🔄 Flujo Completo Visual

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO COMPLETO                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1️⃣ TÚ (Superadmin)                                            │
│     │                                                           │
│     ├── POST /api/brokers                                      │
│     │   Body: {name: "InmoChile", slug: "inmochile", ...}      │
│     │   Response: {id: 1, name: "InmoChile"}                   │
│     │                                                           │
│     └── POST /api/broker/users                                 │
│         Body: {email: "juan@inmochile.cl", role: "admin"}      │
│         Response: {id: 2, role: "admin", broker_id: 1}         │
│                                                                 │
│  2️⃣ Juan (Admin) - Login                                       │
│     │                                                           │
│     ├── POST /api/auth/login                                   │
│     │   Body: {email: "juan@inmochile.cl", password: "..."}    │
│     │   Response: {access_token: "...", role: "admin"}         │
│     │                                                           │
│     ├── PUT /api/broker/config/prompt                          │
│     │   Body: {agent_name: "Carolina", business_context: ...}  │
│     │                                                           │
│     ├── PUT /api/broker/config/leads                           │
│     │   Body: {income_ranges: {...}, qualification_criteria...}│
│     │                                                           │
│     └── POST /api/broker/users (x2)                            │
│         Body: {email: "maria@...", role: "agent"}              │
│         Body: {email: "pedro@...", role: "agent"}              │
│                                                                 │
│  3️⃣ María (Agent) - Login                                      │
│     │                                                           │
│     ├── POST /api/auth/login                                   │
│     │   Body: {email: "maria@inmochile.cl", password: "..."}   │
│     │   Response: {access_token: "...", role: "agent"}         │
│     │                                                           │
│     ├── GET /api/v1/leads                                      │
│     │   Response: [leads asignados solo a ella]                │
│     │                                                           │
│     ├── GET /api/broker/config  ❌ 403 Forbidden               │
│     │                                                           │
│     └── GET /api/pipeline                                      │
│         Response: Pipeline de sus leads ✅                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧪 Script de Testing Completo

```bash
#!/bin/bash
# test_roles.sh

echo "🚀 Testing Role-Based System"
echo "=============================="

# 1. Login como Superadmin
echo "1️⃣ Login as Superadmin..."
SUPER_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"superadmin@tuempresa.com","password":"tu_password"}' \
  | jq -r '.access_token')
echo "✅ Superadmin token: ${SUPER_TOKEN:0:20}..."

# 2. Crear Broker
echo ""
echo "2️⃣ Creating Broker..."
BROKER=$(curl -s -X POST http://localhost:8000/api/brokers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPER_TOKEN" \
  -d '{
    "name": "InmoChile",
    "slug": "inmochile",
    "phone": "+56912345678",
    "email": "contacto@inmochile.cl"
  }')
BROKER_ID=$(echo $BROKER | jq -r '.id')
echo "✅ Broker created: ID=$BROKER_ID"

# 3. Crear Admin
echo ""
echo "3️⃣ Creating Admin..."
ADMIN=$(curl -s -X POST http://localhost:8000/api/broker/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SUPER_TOKEN" \
  -d "{
    \"email\": \"juan@inmochile.cl\",
    \"password\": \"admin123\",
    \"name\": \"Juan Pérez\",
    \"role\": \"admin\",
    \"broker_id\": $BROKER_ID
  }")
echo "✅ Admin created: $(echo $ADMIN | jq -r '.email')"

# 4. Login como Admin
echo ""
echo "4️⃣ Login as Admin..."
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"juan@inmochile.cl","password":"admin123"}' \
  | jq -r '.access_token')
echo "✅ Admin token: ${ADMIN_TOKEN:0:20}..."

# 5. Configurar Broker
echo ""
echo "5️⃣ Configuring Broker..."
curl -s -X PUT http://localhost:8000/api/broker/config/prompt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "agent_name": "Carolina",
    "business_context": "Inmobiliaria de lujo en Santiago"
  }' > /dev/null
echo "✅ Prompt configured"

# 6. Crear Agentes
echo ""
echo "6️⃣ Creating Agents..."
curl -s -X POST http://localhost:8000/api/broker/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "email": "maria@inmochile.cl",
    "password": "agent123",
    "name": "María González",
    "role": "agent"
  }' > /dev/null
echo "✅ Agent María created"

curl -s -X POST http://localhost:8000/api/broker/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "email": "pedro@inmochile.cl",
    "password": "agent456",
    "name": "Pedro Soto",
    "role": "agent"
  }' > /dev/null
echo "✅ Agent Pedro created"

# 7. Login como Agent
echo ""
echo "7️⃣ Login as Agent..."
AGENT_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maria@inmochile.cl","password":"agent123"}' \
  | jq -r '.access_token')
echo "✅ Agent token: ${AGENT_TOKEN:0:20}..."

# 8. Test Permissions
echo ""
echo "8️⃣ Testing Permissions..."

echo "  📋 Agent trying to see config (should fail)..."
RESULT=$(curl -s -X GET http://localhost:8000/api/broker/config \
  -H "Authorization: Bearer $AGENT_TOKEN")
if echo $RESULT | grep -q "403\|administrador"; then
  echo "  ✅ Correctly denied"
else
  echo "  ❌ FAILED - Agent can see config!"
fi

echo "  📋 Admin trying to see config (should work)..."
RESULT=$(curl -s -X GET http://localhost:8000/api/broker/config \
  -H "Authorization: Bearer $ADMIN_TOKEN")
if echo $RESULT | grep -q "prompt_config\|lead_config"; then
  echo "  ✅ Correctly allowed"
else
  echo "  ❌ FAILED - Admin cannot see config!"
fi

echo ""
echo "🎉 Testing Complete!"
echo "===================="
echo ""
echo "📝 Summary:"
echo "  - Broker ID: $BROKER_ID"
echo "  - Admin: juan@inmochile.cl (password: admin123)"
echo "  - Agent 1: maria@inmochile.cl (password: agent123)"
echo "  - Agent 2: pedro@inmochile.cl (password: agent456)"
echo ""
echo "🔑 Tokens:"
echo "  - Superadmin: $SUPER_TOKEN"
echo "  - Admin: $ADMIN_TOKEN"
echo "  - Agent: $AGENT_TOKEN"
```

**Ejecutar:**
```bash
chmod +x test_roles.sh
./test_roles.sh
```

---

## 🎓 Resumen

### Orden de Operaciones:
1. **Superadmin** crea Broker
2. **Superadmin** crea Admin del Broker
3. **Admin** configura el agente IA
4. **Admin** configura criterios de calificación
5. **Admin** crea Agentes
6. **Agentes** trabajan con sus leads asignados

### URLs Frontend:
- Admin: `http://localhost:3000/settings` ✅
- Admin: `http://localhost:3000/users` ✅
- Agent: `http://localhost:3000/leads` ✅ (solo sus leads)
- Agent: `http://localhost:3000/settings` ❌ (403 Forbidden)

### Credenciales de Prueba:
```
Superadmin:
- Email: superadmin@tuempresa.com
- Password: tu_password_seguro

Admin (InmoChile):
- Email: juan@inmochile.cl
- Password: admin123

Agente 1 (InmoChile):
- Email: maria@inmochile.cl
- Password: agent123

Agente 2 (InmoChile):
- Email: pedro@inmochile.cl
- Password: agent456
```

---

¿Necesitas ayuda con algún paso específico?



