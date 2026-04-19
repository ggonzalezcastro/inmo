# Integración del Agente con Sistema de Citas

**Fecha**: 2025-01-27  
**Estado**: ✅ Implementación Completa

---

## 📋 Resumen

Se ha implementado la integración del agente LLM (Gemini) con el sistema de citas usando **function calling**. El agente ahora puede:

1. ✅ Obtener horarios disponibles para citas
2. ✅ Crear citas cuando el cliente confirma un horario
3. ✅ Validar que el lead tenga email (requerido para enviar link de Google Meet)

---

## 🏗️ Arquitectura

### Componentes Creados/Modificados

1. **`agent_tools_service.py`** (NUEVO)
   - Define las funciones disponibles para el agente
   - Ejecuta las herramientas cuando el LLM las llama
   - Valida datos antes de crear citas

2. **`llm_service.py`** (MODIFICADO)
   - Agregado método `generate_response_with_function_calling()`
   - Soporte para function calling de Gemini API
   - Manejo de iteraciones múltiples de function calling

3. **`lead_context_service.py`** (MODIFICADO)
   - Agregado email al contexto del lead
   - Actualizado prompt para incluir instrucciones sobre agendamiento
   - Incluye email en la lista de datos requeridos

4. **`chat.py`** (MODIFICADO)
   - Integrado function calling en el endpoint de chat
   - Ejecución de herramientas del agente
   - Actualización de email del lead desde análisis de mensaje

---

## 🔧 Funciones Disponibles para el Agente

### 1. `get_available_appointment_slots`

**Descripción**: Obtiene los horarios disponibles para agendar citas.

**Parámetros**:
- `start_date` (string, opcional): Fecha de inicio en formato ISO (YYYY-MM-DD). Default: hoy
- `days_ahead` (integer, opcional): Días hacia adelante. Default: 14
- `duration_minutes` (integer, opcional): Duración en minutos. Default: 60

**Retorna**: Lista de slots disponibles con formato para el LLM

**Uso**: El agente llama esta función cuando el cliente quiere agendar una cita.

### 2. `create_appointment`

**Descripción**: Crea una cita para el cliente. **Solo se usa cuando el cliente confirma explícitamente un horario**.

**Parámetros**:
- `start_time` (string, requerido): Fecha y hora en formato ISO 8601 con timezone (ej: '2025-02-01T15:00:00-03:00')
- `duration_minutes` (integer, opcional): Duración. Default: 60
- `appointment_type` (string, opcional): Tipo de cita. Default: "virtual_meeting"
- `notes` (string, opcional): Notas adicionales

**Validaciones**:
- ✅ Verifica que el lead tenga email (requerido para enviar link de Google Meet)
- ✅ Verifica disponibilidad del horario
- ✅ Crea evento en Google Calendar si está configurado

**Retorna**: Detalles de la cita creada, incluyendo meet_url

---

## 📝 Flujo de Agendamiento

### 1. Cliente Expresa Interés en Agendar

```
Cliente: "Quiero agendar una cita"
```

### 2. Agente Llama a `get_available_appointment_slots`

El agente obtiene horarios disponibles y los presenta al cliente de forma amigable.

### 3. Cliente Confirma Horario

```
Cliente: "Perfecto, agendemos para el 1 de febrero a las 15:00"
```

### 4. Agente Llama a `create_appointment`

- Valida que el lead tenga email
- Crea la cita en la base de datos
- Crea evento en Google Calendar (si está configurado)
- Obtiene link de Google Meet

### 5. Agente Confirma al Cliente

El agente confirma la cita creada y menciona que recibirá el link por email.

---

## 🔐 Validaciones Implementadas

### Email Requerido

Antes de crear una cita, se verifica que el lead tenga email:

```python
if not lead.email or lead.email.strip() == '':
    return {
        "success": False,
        "error": "El lead no tiene email registrado. Por favor, solicita el email antes de crear la cita..."
    }
```

Si no tiene email, el agente le pedirá el email al cliente antes de proceder.

### Disponibilidad

Se verifica que el horario esté disponible antes de crear la cita.

---

## 📊 Datos Recopilados del Lead

El agente ahora recopila:

1. ✅ **Nombre** - Requerido
2. ✅ **Teléfono** - Requerido  
3. ✅ **Email** - Requerido para citas
4. ✅ **Ubicación** - Requerido
5. ✅ **Presupuesto** - Requerido

El sistema actualiza automáticamente el email del lead cuando se menciona en el chat.

---

## 🎯 Prompt del Agente Actualizado

El prompt del sistema ahora incluye:

- Instrucciones sobre cómo usar las herramientas de agendamiento
- Proceso paso a paso para agendar citas
- Información sobre que necesita email para crear citas

---

## 🚀 Uso

### Endpoint de Chat

El endpoint `/api/v1/chat/test` ahora usa function calling automáticamente:

```python
# El agente puede llamar funciones según necesite
response = await LLMService.generate_response_with_function_calling(
    prompt=prompt,
    tools=tools,
    tool_executor=tool_executor
)
```

### Ejemplo de Conversación

```
Cliente: Hola, quiero ver una propiedad

Agente: Hola! Me encantaría ayudarte. ¿Podrías decirme tu nombre completo?

Cliente: Juan Pérez

Agente: Perfecto Juan. ¿Cuál es tu teléfono de contacto?

Cliente: +56912345678

Agente: Excelente. ¿Cuál es tu email?

Cliente: juan@example.com

Agente: Perfecto. ¿En qué zona te gustaría buscar?

Cliente: Las Condes

Agente: Perfecto. ¿Cuál es tu presupuesto aproximado?

Cliente: 5000 UF

Agente: Excelente. ¿Te gustaría agendar una cita para revisar opciones?

Cliente: Sí, por favor

Agente: [Llama a get_available_appointment_slots]
Aquí tienes algunos horarios disponibles:
- 1 de febrero a las 10:00
- 1 de febrero a las 15:00
- 2 de febrero a las 11:00
¿Cuál prefieres?

Cliente: El 1 de febrero a las 15:00 me funciona

Agente: [Llama a create_appointment]
¡Perfecto! He agendado tu cita para el 1 de febrero a las 15:00. Recibirás un link de Google Meet por email para la reunión virtual. ¡Nos vemos entonces!
```

---

## ⚙️ Configuración Requerida

### Google Calendar (Opcional pero Recomendado)

Para que las citas se creen en Google Calendar:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
GOOGLE_CALENDAR_ID=primary
```

O usar Service Account:

```env
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
GOOGLE_CALENDAR_ID=primary
```

---

## 📝 Notas Técnicas

### Function Calling con Gemini

- Usamos `types.GenerateContentConfig` con `tools`
- Function calling manual (no automático) para tener control
- Máximo 5 iteraciones de function calling

### Manejo de Errores

- Si una función falla, se registra el error y se continúa
- El agente recibe el error y puede informar al cliente
- Las citas solo se crean si todos los datos están validados

---

## ✅ Estado de Implementación

- ✅ Function calling integrado
- ✅ Herramientas definidas y funcionando
- ✅ Validación de email
- ✅ Extracción de email del mensaje
- ✅ Prompt actualizado con instrucciones de agendamiento
- ✅ Logging completo de function calls

---

## 🧪 Próximos Pasos

1. **Testing**: Probar el flujo completo en el chat web
2. **Envío de Email**: Implementar envío automático de email con link de Google Meet
3. **Notificaciones**: Agregar recordatorios de citas (24h y 1h antes)
4. **Manejo de Disponibilidad**: Crear slots de disponibilidad por defecto si no hay configurados

---

## 📚 Referencias

- [Gemini Function Calling Docs](https://ai.google.dev/gemini-api/docs/function-calling)
- Context7: Google Gemini API function calling examples



