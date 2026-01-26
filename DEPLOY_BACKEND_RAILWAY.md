# 🚂 Desplegar Backend en Railway - Guía Paso a Paso

## Por qué Railway (y no Vercel)

Vercel = Solo frontend estático
Railway = Backend completo (FastAPI + PostgreSQL + Redis + Celery)

---

## 📋 Paso a Paso (10 minutos)

### 1️⃣ Crear Cuenta en Railway

1. Ve a https://railway.app
2. Click en **"Start a New Project"**
3. Autentícate con GitHub (usa la misma cuenta)

---

### 2️⃣ Crear Proyecto desde GitHub

1. En Railway, click en **"New Project"**
2. Selecciona **"Deploy from GitHub repo"**
3. Busca y selecciona tu repositorio: `ggonzalezcastro/inmo`
4. Railway escaneará el repo y detectará Python/FastAPI

---

### 3️⃣ Configurar el Build

Railway debería detectar automáticamente, pero verifica:

**Build Command**: `cd backend && pip install -r requirements.txt`
**Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Railway usa el archivo `railway.json` que ya creamos, así que esto debería ser automático.

---

### 4️⃣ Añadir PostgreSQL

1. En tu proyecto de Railway, click en **"New"**
2. Selecciona **"Database"**
3. Selecciona **"Add PostgreSQL"**
4. Railway creará la base de datos automáticamente
5. Railway conectará automáticamente `DATABASE_URL` al servicio

✅ PostgreSQL configurado

---

### 5️⃣ Añadir Redis

1. Click en **"New"** otra vez
2. Selecciona **"Database"**
3. Selecciona **"Add Redis"**
4. Railway creará Redis automáticamente
5. Railway conectará automáticamente `REDIS_URL` al servicio

✅ Redis configurado

---

### 6️⃣ Configurar Variables de Entorno

1. Click en el servicio de tu backend (el que dice "inmo" o similar)
2. Ve a la pestaña **"Variables"**
3. Añade estas variables una por una:

```env
# Celery (usa la misma URL de Redis)
CELERY_BROKER_URL=${{Redis.REDIS_URL}}/1
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}/2

# Seguridad (IMPORTANTE: Cambia este valor)
SECRET_KEY=cambia-esto-por-una-clave-super-segura-de-minimo-32-caracteres-random

# API Keys (reemplaza con tus valores reales)
GEMINI_API_KEY=tu-gemini-api-key-aqui
TELEGRAM_TOKEN=tu-telegram-bot-token-aqui

# Opcionales (solo si los usas)
GOOGLE_CLIENT_ID=tu-google-client-id
GOOGLE_CLIENT_SECRET=tu-google-client-secret
GOOGLE_REFRESH_TOKEN=tu-google-refresh-token
TWILIO_ACCOUNT_SID=tu-twilio-sid
TWILIO_AUTH_TOKEN=tu-twilio-token
TWILIO_PHONE_NUMBER=+1234567890

# Producción
ENVIRONMENT=production
DEBUG=False

# CORS - IMPORTANTE: Añade tu URL de Vercel
ALLOWED_ORIGINS=https://tu-proyecto.vercel.app
```

**⚠️ IMPORTANTE**: Cambia `https://tu-proyecto.vercel.app` por tu URL real de Vercel

**💡 Tip**: Para `SECRET_KEY`, genera una clave segura:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

### 7️⃣ Generar Dominio Público

1. En el servicio backend, ve a **"Settings"**
2. Busca la sección **"Networking"** o **"Domains"**
3. Click en **"Generate Domain"**
4. Railway te dará una URL como:
   ```
   https://inmo-production-xxxx.up.railway.app
   ```

✅ **Guarda esta URL** - la necesitarás para Vercel

---

### 8️⃣ Ejecutar Migraciones

Una vez que el servicio esté corriendo:

1. Ve al servicio backend en Railway
2. Click en la pestaña **"Deploy"** o **"Deployments"**
3. Espera a que el deploy termine (puede tardar 2-3 minutos)
4. Una vez listo, ve a **"Settings"** → **"CLI"** o usa Railway CLI

**Opción A: Desde Railway Web**
- No hay forma fácil de ejecutar comandos desde la web

**Opción B: Instalar Railway CLI** (Recomendado)

```bash
# Instalar Railway CLI
brew install railway  # macOS
# o
npm i -g @railway/cli  # cualquier OS

# Login
railway login

# Conectar a tu proyecto
railway link

# Ejecutar migraciones
railway run cd backend && alembic upgrade head

# Crear superadmin (opcional)
railway run cd backend && python scripts/create_superadmin_simple.py
```

**Opción C: Las migraciones se ejecutan automáticamente**

Si el backend arranca correctamente, deberías poder crear usuarios desde el frontend.

---

### 9️⃣ Verificar que el Backend Funciona

Abre en tu navegador:

```
https://tu-backend-url.up.railway.app/health
```

**Deberías ver**:
```json
{
  "status": "healthy",
  "database": "ok",
  "redis": "ok"
}
```

También prueba la documentación:
```
https://tu-backend-url.up.railway.app/docs
```

Deberías ver la documentación interactiva de FastAPI.

---

### 🔟 Conectar Vercel con Railway

Ahora que tu backend está corriendo, actualiza Vercel:

1. Ve a https://vercel.com
2. Abre tu proyecto
3. Ve a **"Settings"** → **"Environment Variables"**
4. Añade o actualiza:

```
VITE_API_URL=https://tu-backend-url.up.railway.app
```

5. Ve a **"Deployments"**
6. Click en los 3 puntos del último deployment
7. Click en **"Redeploy"**
8. Espera 1-2 minutos

---

## ✅ Verificación Final

### Backend
- [ ] `https://tu-backend.railway.app/health` responde
- [ ] `https://tu-backend.railway.app/docs` muestra documentación
- [ ] PostgreSQL conectada (status: ok en /health)
- [ ] Redis conectada (status: ok en /health)

### Frontend
- [ ] `https://tu-proyecto.vercel.app` carga
- [ ] Abre DevTools (F12) → No hay errores de CORS
- [ ] Puedes hacer login o registro

### Integración
1. Abre tu frontend en Vercel
2. Abre DevTools (F12)
3. Ve a la pestaña **Network**
4. Intenta hacer login
5. Deberías ver requests a tu backend de Railway

---

## 🐛 Troubleshooting

### Error: "Network Error" en el frontend

**Causa**: CORS no configurado correctamente

**Solución**:
1. Verifica que `ALLOWED_ORIGINS` en Railway incluya tu URL de Vercel
2. Debe ser exactamente: `https://tu-proyecto.vercel.app` (sin barra al final)
3. Reinicia el servicio en Railway

### Error: 502 Bad Gateway

**Causa**: El backend no está iniciando correctamente

**Solución**:
1. Ve a Railway → Tu servicio → **"Logs"**
2. Busca errores
3. Usualmente es una variable de entorno faltante

### Error: Database connection failed

**Causa**: `DATABASE_URL` no está configurada o es incorrecta

**Solución**:
1. Verifica que PostgreSQL esté corriendo en Railway
2. Railway debería conectar automáticamente `DATABASE_URL`
3. Si no, copia la URL desde PostgreSQL y pégala manualmente en Variables

---

## 💰 Costos

- **Plan Gratuito**: $5 de crédito/mes
- Si se acaba: ~$5-15/mes según uso
- PostgreSQL: Incluido (1GB)
- Redis: Incluido (100MB)

---

## 🎉 ¡Listo!

Una vez completados estos pasos:

```
Internet
   │
   ├─► Vercel ──────► Frontend (React)
   │   ✅ Funcionando
   │
   └─► Railway ─────► Backend (FastAPI)
       ✅ Funcionando  ├─► PostgreSQL ✅
                       ├─► Redis ✅
                       └─► Celery ✅
```

Tu aplicación completa estará en producción! 🚀

---

## 📞 ¿Necesitas Ayuda?

1. Revisa los logs en Railway: Servicio → Deployments → View Logs
2. Revisa errores en Vercel: Deployments → Runtime Logs
3. Abre DevTools (F12) en el frontend para ver errores de red

---

**¡Éxito con el deployment!** 🎊
