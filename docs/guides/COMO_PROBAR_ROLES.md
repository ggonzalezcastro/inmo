# 🔧 Cómo Probar Roles en el Frontend

## Método 1: Usando el RoleDebugger (Recomendado)

He creado un componente `RoleDebugger` que aparece automáticamente en desarrollo.

### Pasos:

1. **Inicia el servidor de desarrollo:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Abre el navegador** y ve a cualquier página (Pipeline, Dashboard, etc.)

3. **Busca el botón "🔧 Debug Roles"** en la esquina inferior derecha

4. **Haz click** para abrir el panel de debug

5. **Selecciona el rol** que quieres probar:
   - 👔 **Admin** - Verá todas las opciones
   - 🏠 **Agent** - Verá solo Pipeline, Campañas y Chat

6. **La página se recargará** automáticamente con el nuevo rol

### Qué puedes probar:

#### Como Admin:
- ✅ Ver Dashboard
- ✅ Ver Pipeline
- ✅ Ver Campañas
- ✅ Ver Chat
- ✅ Ver **Configuración** (solo Admin)
- ✅ Ver **Usuarios** (solo Admin)
- ✅ NavBar muestra todas las opciones

#### Como Agent:
- ✅ Ver Pipeline
- ✅ Ver Campañas
- ✅ Ver Chat
- ❌ NO puede ver Dashboard
- ❌ NO puede ver Configuración
- ❌ NO puede ver Usuarios
- ✅ NavBar muestra solo opciones permitidas
- ✅ Si intenta acceder a `/settings` o `/users`, será redirigido a `/pipeline`

---

## Método 2: Modificar localStorage directamente

Si prefieres hacerlo manualmente:

1. **Abre la consola del navegador** (F12)

2. **Para simular Admin:**
   ```javascript
   localStorage.setItem('user', JSON.stringify({
     id: 1,
     email: 'admin@test.com',
     name: 'Admin User',
     role: 'admin'
   }));
   window.location.reload();
   ```

3. **Para simular Agent:**
   ```javascript
   localStorage.setItem('user', JSON.stringify({
     id: 2,
     email: 'agent@test.com',
     name: 'Agent User',
     role: 'agent'
   }));
   window.location.reload();
   ```

---

## Método 3: Modificar el authStore temporalmente

Si quieres probar sin recargar la página:

1. **Abre `src/store/authStore.js`**

2. **Modifica temporalmente `getUserRole()`:**
   ```javascript
   getUserRole: () => {
     // return user?.role || 'agent'; // Original
     return 'admin'; // Forzar admin
     // return 'agent'; // Forzar agent
   },
   ```

3. **Guarda y recarga** la página

⚠️ **No olvides revertir el cambio después de probar**

---

## Verificación de Funcionalidad

### Checklist para Admin:

- [ ] NavBar muestra: Dashboard, Pipeline, Campañas, Chat, Configuración, Usuarios
- [ ] Puede acceder a `/dashboard`
- [ ] Puede acceder a `/settings`
- [ ] Puede acceder a `/users`
- [ ] Puede ver el formulario de configuración del agente
- [ ] Puede ver la lista de usuarios
- [ ] Puede crear/editar usuarios

### Checklist para Agent:

- [ ] NavBar muestra solo: Pipeline, Campañas, Chat
- [ ] NO puede acceder a `/dashboard` (redirige a `/pipeline`)
- [ ] NO puede acceder a `/settings` (redirige a `/pipeline`)
- [ ] NO puede acceder a `/users` (redirige a `/pipeline`)
- [ ] Puede acceder a `/pipeline`
- [ ] Puede acceder a `/campaigns`
- [ ] Puede acceder a `/chat`

---

## Notas Importantes

1. **El RoleDebugger solo aparece en desarrollo** (no en producción)

2. **Los cambios se guardan en localStorage**, así que persisten hasta que:
   - Limpias el localStorage
   - Haces login con un usuario real
   - Cambias el rol manualmente

3. **Si el backend está corriendo**, el endpoint `/auth/me` puede sobrescribir el rol cuando:
   - Haces login
   - La app carga el usuario desde el servidor

4. **Para probar completamente**, necesitas:
   - Backend corriendo con endpoint `/auth/me`
   - Usuarios reales con roles diferentes en la base de datos

---

## Troubleshooting

### El RoleDebugger no aparece:
- Verifica que estás en modo desarrollo (`npm run dev`)
- Verifica que `import.meta.env.PROD` sea `false`

### El rol no cambia:
- Verifica la consola del navegador para errores
- Limpia localStorage: `localStorage.clear()`
- Recarga la página manualmente

### La navegación no cambia:
- Verifica que el NavBar esté usando `getUserRole()`
- Verifica que el usuario esté cargado en el store

---

## Ejemplo de Flujo de Prueba

1. **Inicia como Agent:**
   - Usa RoleDebugger → Selecciona "🏠 Agent"
   - Verifica que solo ves Pipeline, Campañas, Chat
   - Intenta ir a `/settings` → Debería redirigir a `/pipeline`

2. **Cambia a Admin:**
   - Usa RoleDebugger → Selecciona "👔 Admin"
   - Verifica que ahora ves todas las opciones
   - Ve a `/settings` → Debería funcionar
   - Ve a `/users` → Debería funcionar

3. **Prueba protección de rutas:**
   - Como Agent, escribe `/settings` en la URL
   - Debería redirigir automáticamente a `/pipeline`

---

**¡Listo! Ahora puedes probar todos los roles fácilmente.** 🎉


