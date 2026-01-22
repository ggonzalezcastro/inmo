# ✅ Checklist de Deployment

Usa esta lista para asegurarte de que todo esté configurado correctamente antes de hacer deploy.

## 📦 Pre-Deployment

### Código y Repositorio
- [ ] Código está en un repositorio Git (GitHub, GitLab, o Bitbucket)
- [ ] Todos los cambios están committed
- [ ] `.gitignore` está configurado correctamente (no incluye `.env`, `node_modules`, etc.)
- [ ] Branch principal se llama `main` o `master`

### Archivos de Configuración
- [ ] `vercel.json` existe en la raíz del proyecto
- [ ] `.vercelignore` existe en la raíz del proyecto
- [ ] `Procfile` existe (si usas Heroku)
- [ ] `railway.json` existe (si usas Railway)
- [ ] `render.yaml` existe (si usas Render)

### Frontend
- [ ] `npm install` funciona sin errores
- [ ] `npm run build` funciona localmente sin errores
- [ ] `npm run preview` muestra la app correctamente
- [ ] `.env.production.example` está documentado

### Backend
- [ ] `pip install -r backend/requirements.txt` funciona sin errores
- [ ] Servidor inicia correctamente: `uvicorn app.main:app --reload`
- [ ] Endpoint `/health` responde correctamente
- [ ] Endpoint `/docs` muestra la documentación de FastAPI
- [ ] `.env.production.example` está documentado
- [ ] CORS está configurado dinámicamente (`ALLOWED_ORIGINS`)

---

## 🚀 Backend Deployment

### Elegir Plataforma
- [ ] Elegida plataforma para backend: 
  - [ ] Railway
  - [ ] Render
  - [ ] Heroku
  - [ ] DigitalOcean
  - [ ] Otra: ___________

### PostgreSQL
- [ ] Base de datos PostgreSQL creada
- [ ] `DATABASE_URL` obtenida
- [ ] Conexión a la base de datos verificada

### Redis
- [ ] Redis creado/provisionado
- [ ] `REDIS_URL` obtenida
- [ ] Conexión a Redis verificada

### Variables de Entorno (Backend)
- [ ] `DATABASE_URL` configurada
- [ ] `REDIS_URL` configurada
- [ ] `CELERY_BROKER_URL` configurada
- [ ] `CELERY_RESULT_BACKEND` configurada
- [ ] `SECRET_KEY` configurada (generada de forma segura)
- [ ] `GEMINI_API_KEY` configurada
- [ ] `TELEGRAM_TOKEN` configurada (si aplica)
- [ ] `GOOGLE_CLIENT_ID` configurada (si aplica)
- [ ] `GOOGLE_CLIENT_SECRET` configurada (si aplica)
- [ ] `GOOGLE_REFRESH_TOKEN` configurada (si aplica)
- [ ] `TWILIO_ACCOUNT_SID` configurada (si aplica)
- [ ] `TWILIO_AUTH_TOKEN` configurada (si aplica)
- [ ] `ALLOWED_ORIGINS` configurada con URL de Vercel
- [ ] `ENVIRONMENT=production` configurada
- [ ] `DEBUG=False` configurada

### Servicios Workers
- [ ] Celery Worker está corriendo
- [ ] Celery Beat está corriendo (si aplica)
- [ ] Logs de workers se ven sin errores

### Migraciones de Base de Datos
- [ ] Migraciones ejecutadas: `alembic upgrade head`
- [ ] Tablas creadas correctamente
- [ ] Superadmin creado (si aplica)

### Verificación Backend
- [ ] Backend URL obtenida: `https://___________________`
- [ ] `https://tu-backend/health` responde con status 200
- [ ] `https://tu-backend/docs` muestra documentación
- [ ] Endpoint de login funciona desde Postman/curl

---

## 🎨 Frontend Deployment (Vercel)

### Preparación
- [ ] Código subido a GitHub/GitLab/Bitbucket
- [ ] Backend ya deployado y funcionando

### Configuración en Vercel
- [ ] Cuenta de Vercel creada
- [ ] Proyecto importado desde repositorio
- [ ] Framework detectado automáticamente
- [ ] Build settings verificados:
  - Build Command: `cd frontend && npm install && npm run build`
  - Output Directory: `frontend/dist`

### Variables de Entorno (Frontend)
- [ ] `VITE_API_URL` configurada con URL del backend
  - Valor: `https://___________________`

### Deployment
- [ ] Primer deploy iniciado
- [ ] Build completado exitosamente
- [ ] Deploy completado sin errores
- [ ] URL de producción obtenida: `https://___________________`

### Verificación Frontend
- [ ] Página carga correctamente
- [ ] Assets (CSS, JS, imágenes) cargan correctamente
- [ ] No hay errores en la consola del navegador
- [ ] Rutas funcionan correctamente (React Router)

---

## 🔗 Integración Frontend-Backend

### CORS
- [ ] `ALLOWED_ORIGINS` en backend incluye URL de Vercel
- [ ] No hay errores de CORS en la consola del navegador
- [ ] Requests del frontend llegan al backend

### Funcionalidades
- [ ] Login funciona correctamente
- [ ] Registro funciona correctamente
- [ ] Dashboard carga datos
- [ ] API calls funcionan
- [ ] WebSockets funcionan (si aplica)
- [ ] Uploads de archivos funcionan (si aplica)

---

## 🔐 Seguridad

### Secrets y API Keys
- [ ] Todas las API keys están en variables de entorno (no en el código)
- [ ] `SECRET_KEY` es fuerte y única (mínimo 32 caracteres)
- [ ] No hay `.env` en el repositorio Git
- [ ] Tokens sensibles no están expuestos en logs

### HTTPS
- [ ] Frontend usa HTTPS (automático en Vercel)
- [ ] Backend usa HTTPS
- [ ] No hay mixed content warnings

### Permisos
- [ ] Roles y permisos funcionan correctamente
- [ ] Usuarios no autorizados no pueden acceder a rutas protegidas
- [ ] Tokens JWT expiran correctamente

---

## 📊 Monitoreo y Testing

### Logs
- [ ] Logs del backend son accesibles
- [ ] Logs del frontend son accesibles (Vercel)
- [ ] No hay errores críticos en logs

### Performance
- [ ] Tiempo de respuesta del backend < 2s
- [ ] Tiempo de carga del frontend < 3s
- [ ] Base de datos responde rápidamente

### Testing
- [ ] Crear usuario nuevo funciona
- [ ] Login funciona
- [ ] CRUD de leads funciona
- [ ] Pipeline funciona
- [ ] Campaigns funcionan
- [ ] Templates funcionan
- [ ] Chat funciona
- [ ] Llamadas de voz funcionan (si aplica)
- [ ] Telegram funciona (si aplica)

---

## 📱 Post-Deployment

### Documentación
- [ ] README actualizado con URLs de producción
- [ ] Documentación de API actualizada
- [ ] Guía de usuario creada (si aplica)

### Dominio Custom (Opcional)
- [ ] Dominio comprado
- [ ] DNS configurado
- [ ] Dominio añadido en Vercel
- [ ] SSL/TLS verificado

### Backups
- [ ] Backups automáticos de base de datos configurados
- [ ] Plan de recuperación ante desastres documentado

### Alertas
- [ ] Alertas de downtime configuradas
- [ ] Alertas de errores configuradas
- [ ] Monitoreo de uso configurado

---

## 🎉 ¡Deployment Completo!

Si todos los items están marcados, ¡felicitaciones! Tu aplicación está en producción.

### URLs Finales

- **Frontend**: `https://___________________`
- **Backend**: `https://___________________`
- **API Docs**: `https://___________________/docs`

### Próximos Pasos

1. Comparte la URL con usuarios beta
2. Monitorea logs por las primeras 24-48 horas
3. Recopila feedback
4. Itera y mejora

---

## 📞 ¿Problemas?

Consulta:
- `DEPLOYMENT_VERCEL.md` - Guía completa de deployment
- `README_VERCEL_QUICKSTART.md` - Guía rápida
- Logs del servicio de hosting
- Consola del navegador (F12)

---

**Última actualización**: $(date)
