# 🚀 Guía de Deployment a Vercel

## 📋 Resumen

Este proyecto está dividido en dos partes:
- **Frontend**: React + Vite (se despliega en Vercel)
- **Backend**: FastAPI + PostgreSQL + Redis + Celery (requiere otro servicio)

## 🎯 Frontend en Vercel

### Paso 1: Preparar el Repositorio

1. **Inicializar Git** (si aún no lo has hecho):
```bash
git init
git add .
git commit -m "Initial commit: Preparar proyecto para Vercel"
```

2. **Subir a GitHub/GitLab/Bitbucket**:
```bash
# Crear repositorio en GitHub primero, luego:
git remote add origin https://github.com/tu-usuario/tu-repo.git
git branch -M main
git push -u origin main
```

### Paso 2: Configurar Vercel

1. **Ir a Vercel**: https://vercel.com
2. **Importar Proyecto**: 
   - Click en "Add New Project"
   - Selecciona tu repositorio
   - Vercel detectará automáticamente la configuración

3. **Variables de Entorno**:
   En el dashboard de Vercel, añade:
   ```
   VITE_API_URL=https://tu-backend-url.com
   ```
   ⚠️ **IMPORTANTE**: Necesitas deployar el backend primero para obtener esta URL

### Paso 3: Deploy

Click en **"Deploy"** y Vercel se encargará del resto.

---

## 🔧 Backend (Opciones de Deployment)

El backend **NO puede** estar en Vercel porque requiere:
- Base de datos PostgreSQL persistente
- Redis para caché y colas
- Celery workers para tareas asíncronas
- Procesos de larga duración

### Opción 1: Railway.app (Recomendado) 🌟

**Ventajas**: Fácil, soporta PostgreSQL, Redis, y múltiples servicios

1. Ir a https://railway.app
2. "New Project" → "Deploy from GitHub repo"
3. Seleccionar tu repositorio
4. Railway detectará automáticamente el backend
5. Añadir servicios:
   - PostgreSQL (Add → Database → PostgreSQL)
   - Redis (Add → Database → Redis)
6. Configurar variables de entorno automáticamente
7. Deploy

**Costo**: Plan gratuito con $5 de crédito mensual, luego ~$5-20/mes

### Opción 2: Render.com

**Ventajas**: Plan gratuito generoso, buena documentación

1. Ir a https://render.com
2. "New Web Service"
3. Conectar repositorio
4. Configurar:
   - Build Command: `pip install -r backend/requirements.txt`
   - Start Command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Añadir PostgreSQL y Redis como servicios adicionales
6. Configurar variables de entorno

**Costo**: Plan gratuito (con limitaciones), luego ~$7-25/mes

### Opción 3: DigitalOcean App Platform

**Ventajas**: Más control, escalable

1. Ir a https://www.digitalocean.com/products/app-platform
2. "Create App" → GitHub
3. Configurar componentes:
   - Web Service (FastAPI)
   - Database (PostgreSQL)
   - Redis
   - Workers (Celery)
4. Deploy

**Costo**: ~$12-30/mes

### Opción 4: Heroku

**Ventajas**: Clásico, bien documentado

⚠️ **Nota**: Heroku eliminó su plan gratuito en 2022

1. Instalar Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli
2. Crear app:
```bash
heroku create tu-app-backend
```
3. Añadir add-ons:
```bash
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini
```
4. Crear `Procfile` en la raíz del proyecto:
```
web: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: cd backend && celery -A app.celery_app worker --loglevel=info
beat: cd backend && celery -A app.celery_app beat --loglevel=info
```
5. Deploy:
```bash
git push heroku main
```

**Costo**: ~$7-25/mes

---

## 🔄 Flujo Completo de Deployment

### 1️⃣ Deployar Backend Primero

Elige una de las opciones anteriores y deploya el backend. Obtendrás una URL como:
- Railway: `https://tu-app-production.up.railway.app`
- Render: `https://tu-app.onrender.com`
- Digital Ocean: `https://tu-app-xxxxx.ondigitalocean.app`

### 2️⃣ Configurar Variables de Entorno del Backend

En el servicio que elijas, configura:

```env
# Database (usualmente auto-configurada)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# Redis (usualmente auto-configurada)
REDIS_URL=redis://host:6379/0

# Celery
CELERY_BROKER_URL=redis://host:6379/1
CELERY_RESULT_BACKEND=redis://host:6379/2

# API Keys
GEMINI_API_KEY=tu-gemini-api-key
TELEGRAM_TOKEN=tu-telegram-token
SECRET_KEY=tu-secret-key-segura

# CORS (importante)
ALLOWED_ORIGINS=https://tu-frontend.vercel.app

# Google Calendar (si aplica)
GOOGLE_CALENDAR_CREDENTIALS=...
```

### 3️⃣ Actualizar Frontend en Vercel

1. En Vercel → Settings → Environment Variables
2. Añadir:
```
VITE_API_URL=https://tu-backend-url.com
```
3. Redeploy (Vercel lo hará automáticamente)

### 4️⃣ Configurar CORS en el Backend

En `backend/app/main.py`, asegúrate de tener:

```python
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# Configurar CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Tu dominio de Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5️⃣ Verificar

1. Frontend: https://tu-app.vercel.app
2. Backend: https://tu-backend.railway.app/docs (FastAPI docs)
3. Health check: https://tu-backend.railway.app/health

---

## 🛠️ Comandos Útiles

### Desarrollo Local
```bash
# Frontend
cd frontend
npm install
npm run dev

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Build Local (Testing)
```bash
cd frontend
npm run build
npm run preview
```

### Ver Logs en Vercel
```bash
# Instalar Vercel CLI
npm i -g vercel

# Login
vercel login

# Ver logs
vercel logs
```

---

## ⚠️ Checklist Pre-Deployment

- [ ] Backend deployado y funcionando
- [ ] Base de datos configurada y migrada
- [ ] Redis funcionando
- [ ] Variables de entorno configuradas en backend
- [ ] `VITE_API_URL` configurada en Vercel
- [ ] CORS configurado correctamente en backend
- [ ] SSL/HTTPS habilitado (automático en Vercel y la mayoría de servicios)
- [ ] Git repository actualizado
- [ ] Secretos y API keys seguros (no en el código)

---

## 🐛 Troubleshooting

### Error: "Network Error" o "Failed to fetch"

**Problema**: El frontend no puede conectar con el backend

**Soluciones**:
1. Verificar que `VITE_API_URL` esté correcta en Vercel
2. Verificar CORS en el backend
3. Asegurarse de que el backend esté corriendo
4. Verificar que el backend tenga HTTPS (no HTTP)

### Error: "502 Bad Gateway" en Backend

**Problema**: El backend no está respondiendo

**Soluciones**:
1. Verificar logs del servicio de backend
2. Verificar que la base de datos esté conectada
3. Verificar variables de entorno
4. Aumentar memoria/recursos del servicio

### Error: Build Failed en Vercel

**Problema**: El build del frontend falla

**Soluciones**:
1. Verificar que `package.json` tenga todas las dependencias
2. Probar build localmente: `npm run build`
3. Verificar logs en Vercel
4. Limpiar cache: Vercel → Settings → Clear Cache

---

## 💡 Recomendación

**Para empezar rápido**: Usa **Railway** para el backend
- Es el más fácil de configurar
- Detecta automáticamente PostgreSQL y Redis
- Configuración mínima
- Plan gratuito para empezar

**URL Final**:
- Frontend: `https://inmo.vercel.app` (o tu dominio custom)
- Backend: `https://inmo-backend.up.railway.app`

---

## 📚 Recursos

- [Vercel Docs](https://vercel.com/docs)
- [Railway Docs](https://docs.railway.app)
- [Render Docs](https://render.com/docs)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

---

## 🎉 ¡Listo!

Una vez completados todos los pasos, tu aplicación estará en producción. ¡Éxito! 🚀
