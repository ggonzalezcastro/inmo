# 👤 Cómo Crear Super Admin y Brokers

## 📋 Información del Sistema

El sistema tiene **3 tipos de roles**:

1. **SUPERADMIN** - Admin del sistema completo (puede crear brokers)
2. **ADMIN** - Admin de un broker específico (puede configurar el broker)
3. **AGENT** - Agente inmobiliario (trabaja con leads)

## 🔐 Crear el Primer Super Admin

### Opción 1: Desde el Backend (Recomendado)

El backend debe tener un endpoint o script para crear el primer superadmin. Consulta con el equipo de backend sobre:

- Script de inicialización
- Endpoint especial para crear superadmin
- O cómo insertar directamente en la base de datos

### Opción 2: Usando el Frontend (Si el backend lo permite)

Si el backend tiene un endpoint para crear superadmin, puedes:

1. **Registrarse normalmente** desde `/register`
2. **El backend debe asignar el rol** según alguna lógica (ej: primer usuario = superadmin)

### Opción 3: Modificar Temporalmente el Frontend

Puedes modificar temporalmente el formulario de registro para enviar `role: "superadmin"`:

```javascript
// En src/components/Register.jsx (temporalmente)
const handleSubmit = async (e) => {
  e.preventDefault();
  const success = await register(email, password, broker_name);
  // ... resto del código
};
```

Y modificar `authAPI.register` para incluir el rol:

```javascript
// En src/services/api.js (temporalmente)
register: (email, password, broker_name) =>
  api.post('/auth/register', { 
    email, 
    password, 
    broker_name,
    role: 'superadmin' // Solo para el primer usuario
  }),
```

⚠️ **IMPORTANTE**: Esto solo funcionará si el backend acepta el campo `role` en el registro.

---

## 🏢 Crear un Broker

### Como Super Admin

Una vez que tengas un usuario superadmin, deberías poder:

1. **Acceder a una página de gestión de brokers** (si existe)
2. **Crear nuevos brokers** desde esa página
3. **Asignar usuarios a brokers**

### Si no existe la página de gestión de brokers

Puedes usar el RoleDebugger para simular ser superadmin y ver qué opciones aparecen.

---

## 🧪 Probar con el RoleDebugger

1. **Abre el frontend** en desarrollo
2. **Usa el RoleDebugger** (botón en esquina inferior derecha)
3. **Simula ser superadmin**:
   ```javascript
   // En consola del navegador
   localStorage.setItem('user', JSON.stringify({
     id: 1,
     email: 'superadmin@test.com',
     name: 'Super Admin',
     role: 'superadmin'
   }));
   window.location.reload();
   ```

4. **Verifica qué opciones aparecen** en el NavBar

---

## 📝 Notas Importantes

1. **El superadmin NO pertenece a ningún broker** (`broker_id = NULL`)
2. **Los ADMIN y AGENT pertenecen a un broker** (`broker_id` tiene valor)
3. **El primer usuario registrado** podría ser automáticamente superadmin (depende del backend)

---

## 🔍 Verificar tu Rol Actual

Abre la consola del navegador (F12) y ejecuta:

```javascript
// Ver usuario actual
console.log(JSON.parse(localStorage.getItem('user')));

// Ver rol
const user = JSON.parse(localStorage.getItem('user'));
console.log('Rol:', user?.role);
```

---

## 💡 Recomendación

**Consulta con el equipo de backend** sobre:
- ¿Cómo se crea el primer superadmin?
- ¿Hay un script de inicialización?
- ¿El primer usuario registrado es automáticamente superadmin?
- ¿Hay un endpoint especial para crear superadmin?

El frontend está listo para manejar el rol `superadmin`, pero la creación del usuario debe hacerse desde el backend.


