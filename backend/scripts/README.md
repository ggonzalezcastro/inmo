# 🛠️ Scripts de Vapi.ai

Scripts de utilidad para gestionar agentes de voz con Vapi.ai.

---

## 🐳 Con Docker

Si el proyecto corre con Docker (`docker compose up`), ejecuta migraciones y scripts **dentro del contenedor**:

```bash
# Migraciones de base de datos
docker compose exec backend alembic upgrade head

# Scripts (desde la raíz del repo, el backend está montado en /app)
docker compose exec backend python scripts/verify_vapi_setup.py
docker compose exec backend python scripts/create_vapi_assistant.py
docker compose exec backend python scripts/assign_phone_number_to_broker.py
```

---

## 📝 Scripts Disponibles

### 1. `verify_vapi_setup.py`
Verifica que todas las variables de entorno estén configuradas correctamente.

```bash
python scripts/verify_vapi_setup.py
```

**Uso:**
- Ejecutar ANTES de cualquier otra cosa
- Te dirá qué falta configurar
- Valida credenciales de Vapi

---

### 2. `create_vapi_assistant.py`
Crea un asistente de IA optimizado para calificación de leads inmobiliarios.

```bash
python scripts/create_vapi_assistant.py
```

**Proceso:**
1. Te pedirá el nombre del agente
2. Te pedirá el nombre de la empresa
3. Creará el asistente en Vapi
4. Te dará el `Assistant ID` para tu `.env`

**Personalización:**
- El prompt está en `app/services/vapi_assistant_service.py`
- Puedes modificarlo según tus necesidades
- La voz por defecto es español mexicano femenino

---

### 3. `list_vapi_assistants.py`
Lista todos los asistentes que tienes creados en Vapi.

```bash
python scripts/list_vapi_assistants.py
```

**Útil para:**
- Ver qué asistentes existen
- Copiar el ID de un asistente
- Verificar configuración de voces

---

### 4. `test_vapi_call.py`
Hace una llamada de prueba a un número de teléfono.

```bash
python scripts/test_vapi_call.py +56912345678
```

**Importante:**
- Usa formato E.164 (con +)
- Chile: `+56912345678`
- México: `+525512345678`
- USA: `+15551234567`

**Qué hace:**
1. Verifica configuración
2. Inicia la llamada con Vapi
3. Muestra el `Call ID`
4. Te da el link al dashboard
5. Espera 5 segundos y verifica el estado

---

## 🚀 Flujo Recomendado

### Primera vez:

```bash
# 1. Verificar configuración
python scripts/verify_vapi_setup.py

# 2. Crear asistente (si no tienes)
python scripts/create_vapi_assistant.py

# 3. Listar asistentes (confirmar)
python scripts/list_vapi_assistants.py

# 4. Probar llamada
python scripts/test_vapi_call.py +56912345678
```

### Uso diario:

```bash
# Hacer llamada de prueba
python scripts/test_vapi_call.py +56912345678

# Ver asistentes
python scripts/list_vapi_assistants.py
```

---

## 🔧 Troubleshooting

### Error: "ModuleNotFoundError"
```bash
# Asegúrate de estar en el directorio backend
cd backend
python scripts/verify_vapi_setup.py
```

### Error: "VAPI_API_KEY not configured"
```bash
# Verifica tu .env
cat .env | grep VAPI

# Debe tener:
# VAPI_API_KEY=...
# VAPI_PHONE_NUMBER_ID=...
# VAPI_ASSISTANT_ID=...
```

### Error al crear asistente
```bash
# Verifica que tu API Key sea válida
# Ve a: https://dashboard.vapi.ai/settings/api-keys
# Copia una nueva clave si es necesario
```

---

## 📚 Más Información

- **Guía de Migración**: Ver `VAPI_MIGRATION_GUIDE.md`
- **Quick Start**: Ver `VAPI_QUICKSTART.md`
- **Dashboard**: https://dashboard.vapi.ai
- **Docs**: https://docs.vapi.ai

---

## 💡 Tips

1. **Guardar Assistant IDs**: Cada asistente tiene un ID único. Guárdalo en tu `.env`
2. **Probar antes de producción**: Usa `test_vapi_call.py` con tu número primero
3. **Monitorear costos**: Revisa el dashboard regularmente
4. **Iterar el prompt**: Escucha las llamadas y ajusta el prompt según resultados
5. **Backup de configuración**: Guarda los IDs importantes en un lugar seguro

---

**¿Problemas?** Revisa la guía completa en `VAPI_MIGRATION_GUIDE.md`
