# Investigación: Sistema de Agendamiento de Citas

## Objetivo
Implementar un sistema de agendamiento de citas con gestión de disponibilidad para leads inmobiliarios, integrable con el chat AI y el dashboard.

## Opciones Investigadas

### 1. **APIs de Calendario Externas**

#### Google Calendar API
- **Ventajas:**
  - Gratis para uso básico
  - Sincronización automática con Google Calendar
  - API robusta y bien documentada
  - Soporte para eventos recurrentes, zonas horarias
  - Webhooks para notificaciones en tiempo real

- **Desventajas:**
  - Requiere autenticación OAuth2
  - Límites de cuota (1,000,000 requests/día)
  - Dependencia de Google

- **Librerías Python:**
  - `google-api-python-client`
  - `google-auth-httplib2`
  - `google-auth-oauthlib`

#### Microsoft Outlook/Calendar API
- **Ventajas:**
  - Integración con Office 365
  - Similar a Google Calendar
  - Buen soporte empresarial

- **Desventajas:**
  - Más complejo que Google
  - Requiere Azure AD

#### Cal.com API (Open Source)
- **Ventajas:**
  - Open source y self-hosted
  - API REST completa
  - Widgets embeddables
  - Muy flexible

- **Desventajas:**
  - Requiere hosting propio
  - Más configuración inicial

### 2. **Solución Propia (Recomendada)**

#### Arquitectura Propuesta:
```
┌─────────────────┐
│   Chat AI       │───┐
└─────────────────┘   │
                      ├──> Sistema de Agendamiento
┌─────────────────┐   │
│   Dashboard     │───┘
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   Base de Datos │
│   - Appointments│
│   - Availability │
│   - Slots        │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   Google/Outlook│ (Opcional)
│   Calendar Sync │
└─────────────────┘
```

## Modelos de Datos Propuestos

### 1. Appointment (Cita)
```python
- id: int
- lead_id: int (FK)
- agent_id: int (FK a users) - opcional
- appointment_type: str (visita_propiedad, reunion_virtual, llamada)
- status: enum (scheduled, confirmed, cancelled, completed)
- start_time: datetime
- end_time: datetime
- duration_minutes: int
- location: str (dirección física o link virtual)
- notes: text
- reminder_sent: bool
- created_at: datetime
- updated_at: datetime
```

### 2. AvailabilitySlot (Horarios Disponibles)
```python
- id: int
- agent_id: int (FK a users) - NULL = todos los agentes
- day_of_week: int (0-6, lunes-domingo)
- start_time: time
- end_time: time
- is_recurring: bool
- valid_from: date
- valid_until: date (NULL = indefinido)
- appointment_type: str
- max_appointments_per_slot: int
```

### 3. AppointmentBlock (Bloqueos de Calendario)
```python
- id: int
- agent_id: int (FK) - NULL = todos
- start_time: datetime
- end_time: datetime
- reason: str (vacaciones, reunión interna, etc.)
- is_recurring: bool
```

## Funcionalidades Clave

### 1. **Gestión de Disponibilidad**
- Horarios de trabajo configurables por agente
- Bloques de tiempo no disponibles (vacaciones, reuniones)
- Slots de tiempo disponibles (ej: 30 min, 1 hora)
- Diferentes tipos de citas con duraciones distintas

### 2. **Agendamiento desde Chat AI**
- El AI puede sugerir horarios disponibles
- El lead puede confirmar directamente desde el chat
- Formato: "¿Te funciona el martes 15 a las 14:00 para visitar la propiedad?"

### 3. **Sincronización con Calendarios Externos** (Opcional)
- Sincronización bidireccional con Google Calendar
- Crear eventos automáticamente cuando se agenda una cita
- Actualizar disponibilidad basado en eventos externos

### 4. **Notificaciones**
- Email/SMS de confirmación
- Recordatorios 24h y 1h antes
- Notificaciones al agente asignado

## Integración con el Sistema Actual

### 1. **En el Chat AI**
```python
# El LLM puede detectar intención de agendar
if "agendar" in message or "cita" in message or "visita" in message:
    # Obtener disponibilidad
    available_slots = AppointmentService.get_available_slots(
        lead_id=lead.id,
        days_ahead=14
    )
    # Formatear para el prompt del LLM
    slots_text = format_slots_for_llm(available_slots)
    # El LLM sugiere horarios
```

### 2. **En el Dashboard**
- Vista de calendario con todas las citas
- Filtros por agente, estado, tipo
- Drag & drop para reagendar
- Vista de disponibilidad por agente

### 3. **En Lead Context**
- Agregar próximas citas al contexto del lead
- Historial de citas en el detalle del lead

## Librerías Python Recomendadas

### Para Manejo de Fechas/Horarios
- `python-dateutil` - Parsing flexible de fechas
- `pytz` - Manejo de zonas horarias
- `arrow` - Alternativa más moderna a datetime

### Para Calendarios Externos
- `google-api-python-client` - Google Calendar
- `msal` + `requests` - Microsoft Graph API

### Para Notificaciones
- `celery` - Ya lo tenemos para tareas asíncronas
- `sendgrid` o `resend` - Email
- `twilio` - SMS (si se necesita)

## Flujo de Agendamiento Propuesto

```
1. Lead menciona interés en agendar (chat)
   ↓
2. AI detecta intención y consulta disponibilidad
   ↓
3. AI presenta opciones: "¿Te funciona el martes 15 a las 14:00?"
   ↓
4. Lead confirma: "Sí, perfecto"
   ↓
5. Sistema crea Appointment
   ↓
6. Bloquea el slot de disponibilidad
   ↓
7. Envía confirmación (email/SMS)
   ↓
8. Crea evento en Google Calendar (opcional)
   ↓
9. Programa recordatorios (Celery)
```

## Próximos Pasos

1. ✅ Crear modelos de datos (Appointment, AvailabilitySlot, AppointmentBlock)
2. ✅ Crear migración de Alembic
3. ✅ Crear servicios (AppointmentService, AvailabilityService)
4. ✅ Crear endpoints API
5. ✅ Integrar con chat AI (detectar intención, sugerir horarios)
6. ✅ Crear componente de calendario en frontend
7. ⏳ Integración opcional con Google Calendar
8. ⏳ Sistema de notificaciones

## Consideraciones Técnicas

### Zona Horaria
- Guardar todo en UTC en la BD
- Convertir a zona horaria del usuario/agente al mostrar
- Considerar zona horaria de Chile (America/Santiago)

### Conflictos
- Validar que no haya doble agendamiento
- Verificar disponibilidad antes de confirmar
- Manejar race conditions con locks de BD

### Escalabilidad
- Cachear disponibilidad (Redis)
- Indexar por fecha/hora en BD
- Paginación en consultas de disponibilidad

## Referencias

- [Google Calendar API Docs](https://developers.google.com/calendar/api/v3/reference)
- [Cal.com Documentation](https://cal.com/docs)
- [Python Dateutil](https://dateutil.readthedocs.io/)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)


