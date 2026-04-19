# ✅ Checklist de Implementación Vapi.ai

Use este checklist para implementar Vapi.ai paso a paso.

---

## 📋 Pre-Requisitos

- [ ] Cuenta de email empresarial
- [ ] Tarjeta de crédito para Vapi.ai
- [ ] Acceso al servidor backend
- [ ] Permisos para editar .env

---

## 🚀 Fase 1: Configuración Inicial (15 min)

### Paso 1: Crear Cuenta
- [ ] Ir a https://vapi.ai
- [ ] Registrarse con email
- [ ] Verificar email
- [ ] Acceder al dashboard

### Paso 2: Obtener API Key
- [ ] Dashboard → Settings → API Keys
- [ ] Click "Create New API Key"
- [ ] Copiar clave (solo se muestra una vez)
- [ ] Guardar en lugar seguro

### Paso 3: Configurar Número de Teléfono

- [ ] Dashboard → Phone Numbers → Buy Phone Number
- [ ] Seleccionar país (ej: Chile +56, México +52)
- [ ] Elegir número disponible
- [ ] Confirmar compra
- [ ] Copiar Phone Number ID

### Paso 4: Actualizar .env
```bash
VAPI_API_KEY=pegar-aqui
VAPI_PHONE_NUMBER_ID=pegar-aqui
```

---

## 🤖 Fase 2: Crear Asistente (10 min)

### Paso 5: Crear Asistente de IA

**Opción A: Via Script (Recomendado)**
```bash
cd backend
python scripts/verify_vapi_setup.py  # Verificar primero
python scripts/create_vapi_assistant.py
```

- [ ] Ejecutar script
- [ ] Ingresar nombre del agente
- [ ] Ingresar nombre de la empresa
- [ ] Copiar Assistant ID
- [ ] Agregar a .env: `VAPI_ASSISTANT_ID=...`

**Opción B: Via Dashboard**
- [ ] Dashboard → Assistants → Create Assistant
- [ ] Name: "Agente Inmobiliario - [Tu Empresa]"
- [ ] Model: OpenAI GPT-4o
- [ ] Voice: Azure Spanish (es-MX-DaliaNeural)
- [ ] Copiar prompt de `vapi_assistant_service.py`
- [ ] Guardar y copiar Assistant ID

### Paso 6: Configurar Webhooks
- [ ] Dashboard → Settings → Webhooks
- [ ] Add webhook URL: `https://tu-backend.railway.app/api/v1/calls/webhooks/voice`
- [ ] Seleccionar eventos:
  - [ ] call.started
  - [ ] status-update
  - [ ] transcript
  - [ ] call.ended
- [ ] Guardar

---

## 🧪 Fase 3: Pruebas (30 min)

### Paso 7: Verificar Configuración
```bash
python scripts/verify_vapi_setup.py
```

- [ ] Todas las variables ✅
- [ ] VOICE_PROVIDER = vapi
- [ ] Webhook URL es HTTPS (no localhost)

### Paso 8: Llamada de Prueba Interna
```bash
python scripts/test_vapi_call.py +56912345678
```

- [ ] Llamada inicia sin errores
- [ ] Teléfono suena
- [ ] Asistente habla en español
- [ ] Conversación es natural
- [ ] Se reciben webhooks
- [ ] Se guarda transcripción

### Paso 9: Revisar en Dashboard
- [ ] Ir a https://dashboard.vapi.ai/calls
- [ ] Encontrar la llamada de prueba
- [ ] Escuchar audio
- [ ] Leer transcripción
- [ ] Verificar resumen generado
- [ ] Revisar costo

### Paso 10: Ajustar Prompt (Si es necesario)
- [ ] Identificar mejoras en la conversación
- [ ] Editar en Dashboard → Assistants
- [ ] Hacer otra llamada de prueba
- [ ] Iterar hasta que esté perfecto

---

## 🎯 Fase 4: Piloto (2-3 días)

### Paso 11: Llamadas Reales de Prueba
- [ ] Seleccionar 5-10 leads para piloto
- [ ] Hacer llamadas con Vapi
- [ ] Documentar feedback
- [ ] Medir métricas:
  - [ ] Tasa de completitud
  - [ ] Duración promedio
  - [ ] Datos capturados correctamente
  - [ ] Satisfacción del lead

### Paso 12: Optimización
- [ ] Revisar transcripciones
- [ ] Identificar objeciones comunes
- [ ] Ajustar prompt para manejarlas
- [ ] Reducir tiempo de llamada si es muy largo
- [ ] Mejorar preguntas poco claras

---

## 🚢 Fase 5: Producción (1 semana)

### Paso 13: Rollout Gradual

**Día 1-2: 10% de llamadas**
- [ ] Configurar 10% de leads para Vapi
- [ ] Mantener 90% en sistema anterior
- [ ] Monitorear errores
- [ ] Recopilar feedback

**Día 3-4: 50% de llamadas**
- [ ] Aumentar a 50% si todo va bien
- [ ] Comparar métricas vs sistema anterior
- [ ] Ajustar prompt según resultados

**Día 5-7: 100% de llamadas**
- [ ] Migrar 100% a Vapi
- [ ] Mantener Twilio como backup
- [ ] Documentar proceso completo

### Paso 14: Capacitación del Equipo
- [ ] Entrenar en uso de dashboard Vapi
- [ ] Enseñar cómo editar prompts
- [ ] Mostrar cómo revisar llamadas
- [ ] Documentar proceso de escalación

---

## 📊 Fase 6: Monitoreo Continuo

### Paso 15: Configurar Métricas
- [ ] Dashboard para KPIs
- [ ] Alertas para fallas
- [ ] Reportes semanales
- [ ] Comparación con objetivos

### Métricas a Revisar:
- [ ] **Tasa de éxito**: >85%
- [ ] **Duración promedio**: 2-3 min
- [ ] **Costo por lead**: <$0.50
- [ ] **Tasa de calificación**: >70%
- [ ] **Satisfacción**: Sin quejas

### Paso 16: Optimización Continua
- [ ] Semana 1: Ajustar prompt
- [ ] Semana 2: Optimizar duración
- [ ] Semana 3: Mejorar tasa de conversión
- [ ] Semana 4: Reducir costos

---

## 🎓 Documentación y Soporte

### Documentación Interna:
- [ ] Leer `VAPI_QUICKSTART.md`
- [ ] Leer `VAPI_MIGRATION_GUIDE.md`
- [ ] Leer `backend/scripts/README.md`
- [ ] Bookmark dashboard de Vapi

### Contactos de Soporte:
- [ ] Guardar: support@vapi.ai
- [ ] Unirse a Discord: https://discord.gg/vapi
- [ ] Bookmark: https://docs.vapi.ai

---

## ✅ Go-Live Final

### Checklist Técnico:
- [ ] API Key funcionando
- [ ] Número activo
- [ ] Asistente configurado
- [ ] Webhooks recibiendo eventos
- [ ] Logs monitoreados
- [ ] Backup de Twilio activo
- [ ] Scripts funcionando
- [ ] Base de datos sincronizada

### Checklist Negocio:
- [ ] Equipo capacitado
- [ ] Prompt aprobado por management
- [ ] Presupuesto asignado
- [ ] Métricas definidas
- [ ] Plan de rollback documentado
- [ ] Comunicación a stakeholders
- [ ] Feedback loop establecido

---

## 🎉 ¡Éxito!

Cuando todos los ítems estén ✅:

🎊 **¡Felicidades! Tu sistema de agentes de voz con IA está en producción**

**Beneficios logrados:**
- ✅ 95% reducción de costos
- ✅ Conversaciones naturales
- ✅ Disponibilidad 24/7
- ✅ Escalabilidad ilimitada
- ✅ Transcripción automática

---

## 📱 Contactos Rápidos

**Vapi Support**: support@vapi.ai  
**Dashboard**: https://dashboard.vapi.ai  
**Docs**: https://docs.vapi.ai  
**Status**: https://status.vapi.ai

---

**Versión**: 1.0  
**Última actualización**: 26 Enero 2026  
**Estado**: ✅ Ready for Production
