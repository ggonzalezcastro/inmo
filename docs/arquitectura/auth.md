# Sistema de Autenticación — Arquitectura

**Fecha:** 17 de abril de 2026
**Última actualización:** 17 de abril de 2026

---

## 1. Visión General

El sistema de autenticación utiliza **JWT (JSON Web Tokens)** con HS256 para autenticación sin estado. Cada token lleva la información del usuario (ID, email, rol, broker_id) y se valida en cada request mediante middleware.

```
┌─────────────┐     POST /auth/register      ┌──────────────┐
│   Cliente    │ ──────────────────────────► │  FastAPI     │
│  (Frontend)  │                              │  /auth/*     │
│              │ ◄────────────────────────── │              │
└─────────────┘     { access_token }         └──────┬───────┘
                                                     │
                                            ┌────────▼────────┐
                                            │  PostgreSQL    │
                                            │  (users,       │
                                            │   brokers)     │
                                            └────────────────┘
```

---

## 2. Estructura del JWT

### 2.1 Payload

```python
{
    "sub": str(user_id),        # ID del usuario (string)
    "email": user_email,        # Email del usuario
    "role": "ADMIN" | "AGENT" | "SUPERADMIN",  # Rol jerárquico
    "broker_id": int,           # ID del broker (tenant)
    "exp": datetime,            # Expiración (UTC)
    "iat": datetime             # Fecha de emisión (UTC)
}
```

### 2.2 Configuración

| Parámetro | Valor | Descripción |
|---|---|---|
| Algoritmo | HS256 | HMAC con SHA-256 |
| Secret Key | `settings.SECRET_KEY` | Clave secreta de la aplicación |
| Tiempo de expiración | 60 minutos (default) | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Tipo de token | Bearer | Estándar OAuth 2.0 |

### 2.3 Validación

El middleware valida en cada request:
1. Firma del token (matching con `SECRET_KEY`)
2. Fecha de expiración (`exp`)
3. Presencia de campos obligatorios (`sub`, `role`, `broker_id`)

---

## 3. Roles de Usuario

```python
class UserRole(str, Enum):
    SUPERADMIN = "superadmin"  # Acceso global a todos los brokers
    ADMIN = "admin"           # Acceso limitado al propio broker
    AGENT = "agent"           # Acceso restringido a leads asignados
```

### 3.1 Permisos por Rol

| Capacidad | SUPERADMIN | ADMIN | AGENT |
|---|---|---|---|
| Acceder a cualquier broker | ✓ | ✗ | ✗ |
| Ver costos de cualquier broker | ✓ | ✗ | ✗ |
| Gestionar usuarios de cualquier broker | ✓ | ✗ | ✗ |
| Acceder a rutas `/admin/*` | ✓ | ✗ | ✗ |
| Acceder a `/super-admin` | ✓ | ✗ | ✗ |
| Gestionar broker propio | ✓ | ✓ | ✗ |
| Crear/editar campañas | ✓ | ✓ | ✗ |
| Ver pipeline | ✓ | ✓ | ✗ |
| Acceder a conversaciones de cualquier agente | ✓ | ✗ | ✗ |
| Ver leads propios asignados | ✓ | ✓ | ✓ |
| Chatear con leads propios | ✓ | ✓ | ✓ |
| Gestionar citas propias | ✓ | ✓ | ✓ |

---

## 4. Flujos de Autenticación

### 4.1 Registro (Register)

```
POST /auth/register
```

**Flujo:**

```
1. ValidateRequest
   └─ ¿El email ya existe? → 400 si existe

2. CreateUser
   └─ Hash de password con bcrypt
   └─ Crear registro en tabla users

3. BrokerInitService.initialize()
   └─ Crear Broker
   └─ Crear BrokerPromptConfig (prompts por defecto)
   └─ Crear BrokerLeadConfig (scoring por defecto)
   └─ Crear BrokerChatConfig (canales por defecto)

4. GenerateJWT
   └─ Payload: { sub: user_id, email, role: ADMIN, broker_id, exp, iat }

5. Return { access_token, token_type: "bearer" }
```

**Request:**
```json
{
    "email": "usuario@empresa.cl",
    "password": "securePassword123",
    "full_name": "Juan Pérez"
}
```

**Response (201):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
}
```

### 4.2 Login

```
POST /auth/login
```

**Flujo:**

```
1. FindUser
   └─ Buscar usuario por email → 401 si no existe

2. VerifyPassword
   └─ Comparar password con hash almacenado → 401 si no coincide

3. GenerateJWT
   └─ Payload: { sub: user_id, email, role, broker_id, exp, iat }

4. Return { access_token, token_type: "bearer" }
```

**Request:**
```json
{
    "email": "usuario@empresa.cl",
    "password": "securePassword123"
}
```

**Response (200):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
}
```

---

## 5. Middleware y Dependencias

### 5.1 get_current_user

```python
# Dependency: Depends(get_current_user)
async def get_current_user(authorization: str = Header(...)) -> dict:
```

**Comportamiento:**

1. Extrae el token del header `Authorization: Bearer <token>`
2. Decodifica el JWT con `SECRET_KEY` y algoritmo `HS256`
3. Valida expiración (`exp`)
4. Retorna dict con:
   ```python
   {
       "user_id": str,
       "email": str,
       "role": "superadmin" | "admin" | "agent",
       "broker_id": int
   }
   ```

### 5.2 Dependencias por Rol

```python
def require_role(*allowed_roles: str):
    """Dependency factory para verificar rol específico."""
    async def checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403)
        return current_user
    return checker
```

---

## 6. Matriz de Control de Acceso

### 6.1 Rutas del Backend

| Ruta | Método | Roles Permitidos |
|---|---|---|
| `/auth/register` | POST | Público |
| `/auth/login` | POST | Público |
| `/admin/*` | * | SUPERADMIN |
| `/brokers/*` | * | SUPERADMIN |
| `/super-admin/*` | * | SUPERADMIN |
| `/costs/*` | * | ADMIN+ |
| `/settings/*` | * | ADMIN+ |
| `/users/*` | * | ADMIN+ |
| `/campaigns/*` | * | ADMIN+ |
| `/leads/*` | GET (propios) | AGENT+ |
| `/leads/*` | POST/PUT/DELETE | ADMIN+ |
| `/appointments/*` | * | AGENT+ |
| `/chat/*` | * | AGENT+ |
| `/pipeline/*` | * | AGENT+ |

### 6.2 Filtro Multi-Tenant

**CRÍTICO:** Cada query a la base de datos debe filtrar por `broker_id` excepto para SUPERADMIN.

```python
# Ejemplo: Obtener leads
if current_user["role"] == "superadmin":
    leads = db.query(Lead).all()
elif current_user["role"] == "admin":
    leads = db.query(Lead).filter(Lead.broker_id == current_user["broker_id"]).all()
else:  # agent
    leads = db.query(Lead).filter(
        Lead.broker_id == current_user["broker_id"],
        Lead.agent_id == current_user["user_id"]
    ).all()
```

---

## 7. Frontend — Guards y Rutas

### 7.1 AuthStore (Zustand)

```typescript
interface AuthState {
    user: {
        id: string;
        email: string;
        role: "superadmin" | "admin" | "agent";
        broker_id: number;
    } | null;
    token: string | null;
    loading: boolean;
    error: string | null;
}

interface AuthStore extends AuthState {
    login: (email: string, password: string) => Promise<void>;
    logout: () => void;
    register: (data: RegisterData) => Promise<void>;
    isLoggedIn: () => boolean;
}
```

**Persistencia:** El `token` se almacena en `localStorage`. Al inicializar el store, se reconstruye el estado desde localStorage.

### 7.2 AuthGuard

```typescript
const AuthGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const isLoggedIn = useAuthStore(s => s.isLoggedIn());

    if (!isLoggedIn) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
};
```

### 7.3 RoleGuard

```typescript
interface RoleGuardProps {
    allowedRoles: Array<"superadmin" | "admin" | "agent">;
    children: React.ReactNode;
    fallback?: React.ReactNode;
}

const RoleGuard: React.FC<RoleGuardProps> = ({ allowedRoles, children, fallback }) => {
    const role = useAuthStore(s => s.user?.role);

    if (!role || !allowedRoles.includes(role)) {
        return fallback ?? <Navigate to="/403" replace />;
    }

    return <>{children}</>;
};
```

### 7.4 Rutas Protegidas

| Ruta | Componente | Guard |
|---|---|---|
| `/login` | LoginPage | Redirect si ya logueado |
| `/register` | RegisterPage | Redirect si ya logueado |
| `/dashboard` | DashboardPage | AuthGuard |
| `/leads` | LeadsPage | AuthGuard |
| `/pipeline` | PipelinePage | AuthGuard |
| `/campaigns` | CampaignsPage | AuthGuard + RoleGuard(ADMIN+) |
| `/appointments` | AppointmentsPage | AuthGuard |
| `/chat` | ChatPage | AuthGuard |
| `/conversations` | ConversationsPage | AuthGuard |
| `/costs` | CostsPage | AuthGuard + RoleGuard(ADMIN+) |
| `/settings` | SettingsPage | AuthGuard + RoleGuard(ADMIN+) |
| `/users` | UsersPage | AuthGuard + RoleGuard(ADMIN+) |
| `/brokers` | BrokersPage | RoleGuard(SUPERADMIN) |
| `/super-admin` | SuperAdminPage | RoleGuard(SUPERADMIN) |

---

## 8. Seguridad

### 8.1 Contraseñas

- Hash con **bcrypt** (salt rounds: 12)
- Nunca se almacena ni se loguea la contraseña en texto plano
- Validación de fortaleza en registro (mínimo 8 caracteres)

### 8.2 Token

- Tiempo de vida corto (60 min default) para minimizar ventana de ataque
- Almacenamiento en `localStorage` (vulnerable a XSS; considerar httpOnly cookie en futuras iteraciones)
- Invalidación explícita en logout (cliente)

### 8.3 Headers de Seguridad

```
Authorization: Bearer <token>
Content-Type: application/json
```

---

## Changelog

| Fecha | Versión | Cambios |
|---|---|---|
| 17-abr-2026 | 1.0.0 | Creación del documento. Estructura completa del sistema JWT, roles, flujos register/login, middleware, matriz de acceso y frontend guards. |
