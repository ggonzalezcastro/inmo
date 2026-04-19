# 🚀 Quick Start: Deploy a Vercel

## ⚡ Resumen Rápido

Tu proyecto ya está **100% preparado** para Vercel. Solo necesitas seguir estos 3 pasos:

---

## 📦 Paso 1: Subir a Git

```bash
# Inicializar Git (si no lo has hecho)
git init
git add .
git commit -m "Ready for Vercel deployment"

# Subir a GitHub
git remote add origin https://github.com/tu-usuario/tu-repo.git
git branch -M main
git push -u origin main
```

---

## 🎯 Paso 2: Deploy Frontend en Vercel

1. Ve a https://vercel.com y haz login
2. Click en **"Add New Project"**
3. Importa tu repositorio de GitHub
4. Vercel detectará automáticamente la configuración (ya está en `vercel.json`)
5. **NO añadas variables de entorno todavía** (lo haremos en el paso 3)
6. Click en **"Deploy"**

✅ Tu frontend estará live en: `https://tu-proyecto.vercel.app`

---

## 🔧 Paso 3: Deploy Backend

⚠️ **El backend NO puede estar en Vercel**. Usa una de estas opciones:

### Opción A: Railway (Recomendado - Más fácil)

1. Ve a https://railway.app
2. Click en **"Start a New Project"**
3. Selecciona **"Deploy from GitHub repo"**
4. Autoriza Railway a acceder a tu repo
5. Railway detectará automáticamente el backend
6. Click en **"Add PostgreSQL"** (Railway lo conectará automáticamente)
7. Click en **"Add Redis"** (Railway lo conectará automáticamente)
8. Ve a **Variables** y añade:
   ```
   GEMINI_API_KEY=tu-key
   TELEGRAM_TOKEN=tu-token
   SECRET_KEY=una-clave-super-segura-de-32-chars
   ALLOWED_ORIGINS=https://tu-proyecto.vercel.app
   ENVIRONMENT=production
   DEBUG=False
   ```
9. Railway desplegará automáticamente

✅ Tu backend estará en: `https://tu-proyecto-production.up.railway.app`

**Costo**: $5 de crédito gratis/mes, luego ~$5-10/mes

### Opción B: Render.com

1. Ve a https://render.com
2. Click en **"New +"** → **"Web Service"**
3. Conecta tu repositorio
4. Configurar:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Añadir **PostgreSQL**: New → PostgreSQL
6. Añadir **Redis**: New → Redis
7. En Variables de entorno, añadir las mismas que Railway
8. Deploy

✅ Tu backend estará en: `https://tu-proyecto.onrender.com`

**Costo**: Plan gratuito (con sleep después de inactividad), luego ~$7/mes

---

## 🔗 Paso 4: Conectar Frontend con Backend

1. Ve a tu proyecto en Vercel
2. **Settings** → **Environment Variables**
3. Añade:
   ```
   VITE_API_URL=https://tu-backend-url.railway.app
   ```
   (o la URL que te dio Render)
4. **Deployments** → Click en los 3 puntos del último deploy → **"Redeploy"**

---

## ✅ Verificación

1. **Frontend**: Ve a `https://tu-proyecto.vercel.app` → Debería cargar
2. **Backend**: Ve a `https://tu-backend.railway.app/docs` → Debería mostrar la documentación de FastAPI
3. **Conexión**: Intenta hacer login en el frontend

---

## 🐛 Problemas Comunes

### "Network Error" al hacer login

**Causa**: CORS no configurado correctamente

**Solución**: 
1. Verifica que `ALLOWED_ORIGINS` en el backend incluya tu URL de Vercel
2. Formato correcto: `https://tu-proyecto.vercel.app` (sin barra final)
3. Reinicia el servicio del backend

### Backend tarda mucho en responder

**Causa**: Plan gratuito de Render duerme después de 15 min de inactividad

**Solución**: 
- Espera 30 segundos (se despertará)
- O actualiza al plan de pago ($7/mes)
- O usa Railway (no tiene sleep en plan gratuito)

### Build Failed en Vercel

**Causa**: Falta alguna dependencia

**Solución**:
1. Prueba localmente: `cd frontend && npm run build`
2. Si falla, instala la dependencia faltante
3. Si funciona localmente, limpia caché en Vercel

---

## 📚 Documentación Completa

Para más detalles, ver `DEPLOYMENT_VERCEL.md`

---

## 💡 Tips

- **Dominio Custom**: Puedes añadir tu dominio en Vercel → Settings → Domains
- **Logs**: En Vercel, ve a tu proyecto → Deployments → click en el deployment → Runtime Logs
- **Monitoreo**: Railway y Render tienen dashboards con métricas

---

## 🎉 ¡Eso es todo!

Tu app está en producción. 🚀

**¿Necesitas ayuda?** Revisa `DEPLOYMENT_VERCEL.md` para troubleshooting detallado.
