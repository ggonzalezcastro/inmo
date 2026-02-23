# 🚀 Guía de Migración a Vapi.ai

## ¿Por qué migrar a Vapi.ai?

### Ventajas vs Twilio

| Característica | Twilio (Actual) | Vapi.ai (Nuevo) |
|----------------|-----------------|-----------------|
| **Tipo** | Telefonía básica | Agente de IA completo |
| **Conversación** | Manual (TwiML) | Automática con IA |
| **Transcripción** | Básica/Manual | Automática en tiempo real |
| **Análisis** | Manual | Automático con resumen |
| **Multiidioma** | Limitado | Nativo (Español incluido) |
| **Complejidad** | Alta (requiere programación) | Baja (configuración) |
| **Calificación de leads** | Manual | Automática con IA |
| **Costo por minuto** | ~$0.013 | ~$0.05-0.10 |
| **Setup inicial** | Complejo | Simple |

**Resultado**: Aunque Vapi es más caro por minuto, reduce significativamente:
- Tiempo de desarrollo
- Costo de mantenimiento
- Necesidad de agentes humanos
- Tiempo de calificación de leads

---

## 📋 Paso 1: Crear Cuenta en Vapi.ai

1. Ve a [https://vapi.ai](https://vapi.ai)
2. Regístrate con tu correo empresarial
3. Verifica tu cuenta
4. Accede al Dashboard

---

## 🔑 Paso 2: Obtener Credenciales

### 2.1 API Key

1. En el dashboard, ve a **Settings** → **API Keys**
2. Click en **Create New API Key**
3. Copia la clave (solo se muestra una vez)
4. Guárdala en tu `.env`:

```bash
VAPI_API_KEY=tu-vapi-api-key-aqui
```

### 2.2 Número de Teléfono

1. Ve a **Phone Numbers** en el dashboard
2. Click en **Buy Phone Number**
3. Selecciona país (ej: Chile +56, México +52)
4. Elige un número disponible
5. Confirma la compra
6. Copia el `Phone Number ID`

```bash
VAPI_PHONE_NUMBER_ID=eba2fb13-259f-4123-abfa-xxxxxxxxxxx
```

---

## 🤖 Paso 3: Crear Asistente de IA

Tienes dos opciones:

### Opción A: Usar el Dashboard (Recomendado para empezar)

1. Ve a **Assistants** en el dashboard
2. Click en **Create Assistant**
3. Configura:
   - **Name**: "Agente Inmobiliario - [Tu Empresa]"
   - **Model**: OpenAI GPT-4o
   - **Voice**: Azure Spanish (es-MX-DaliaNeural)
   - **Language**: Spanish (es)
   - **First Message**: "Hola, ¿cómo estás? Soy [Nombre] de [Empresa]..."

4. En **System Prompt**, copia el prompt de calificación (ver abajo)
5. Guarda y copia el `Assistant ID`

```bash
VAPI_ASSISTANT_ID=29d47d31-ba3c-451c-86ce-xxxxxxxxx
```

### Opción B: Crear por API (Usando nuestro servicio)

Ya tenemos un servicio creado (`vapi_assistant_service.py`) que crea asistentes optimizados.

Usa este script para crear uno:

```python
# scripts/create_vapi_assistant.py
import asyncio
from app.services.vapi_assistant_service import VapiAssistantService

async def main():
    assistant = await VapiAssistantService.create_real_estate_assistant(
        broker_name="Tu Nombre",
        broker_company="Tu Inmobiliaria"
    )
    
    print(f"✅ Asistente creado!")
    print(f"Assistant ID: {assistant['id']}")
    print(f"Agrega esto a tu .env:")
    print(f"VAPI_ASSISTANT_ID={assistant['id']}")

if __name__ == "__main__":
    asyncio.run(main())
```

Ejecuta:

```bash
cd backend
python scripts/create_vapi_assistant.py
```

---

## 📝 Paso 4: Configurar Variables de Entorno

Actualiza tu `.env`:

```bash
# Vapi.ai Configuration
VAPI_API_KEY=tu-vapi-api-key-aqui
VAPI_PHONE_NUMBER_ID=tu-phone-number-id
VAPI_ASSISTANT_ID=tu-assistant-id

# Webhook URL (tu backend público)
WEBHOOK_BASE_URL=https://tu-backend.railway.app
```

---

## 🔄 Paso 5: Configurar Webhooks en Vapi

1. En el dashboard de Vapi, ve a **Settings** → **Webhooks**
2. Agrega tu webhook URL:

```
https://tu-backend.railway.app/api/v1/calls/webhooks/voice
```

3. Selecciona los eventos que quieres recibir:
   - ✅ `call.started` - Llamada iniciada
   - ✅ `status-update` - Actualizaciones de estado
   - ✅ `transcript` - Transcripción en tiempo real
   - ✅ `call.ended` - Llamada finalizada

4. Guarda los cambios

---

## 🧪 Paso 6: Probar la Integración

### Prueba 1: Verificar Credenciales

```bash
cd backend
python -c "from app.config import settings; print(f'✅ Vapi API Key: {settings.VAPI_API_KEY[:10]}...'); print(f'✅ Phone ID: {settings.VAPI_PHONE_NUMBER_ID[:10]}...'); print(f'✅ Assistant ID: {settings.VAPI_ASSISTANT_ID[:10]}...')"
```

### Prueba 2: Hacer Llamada de Prueba

Crea este script:

```python
# scripts/test_vapi_call.py
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.services.voice_call_service import VoiceCallService

async def test_call(phone_number: str):
    """Hacer llamada de prueba a un número"""
    
    # Crear sesión de base de datos
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            # Usar un lead existente o crear uno temporal
            lead_id = 1  # Cambia esto por un lead real
            broker_id = 1  # Cambia esto por tu broker ID
            
            print(f"📞 Iniciando llamada a {phone_number}...")
            
            voice_call = await VoiceCallService.initiate_call(
                db=db,
                lead_id=lead_id,
                campaign_id=None,
                broker_id=broker_id,
                agent_type="vapi"
            )
            
            print(f"✅ Llamada iniciada!")
            print(f"Call ID: {voice_call.id}")
            print(f"External Call ID: {voice_call.external_call_id}")
            print(f"Status: {voice_call.status}")
            
            return voice_call
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_vapi_call.py +56912345678")
        sys.exit(1)
    
    phone = sys.argv[1]
    asyncio.run(test_call(phone))
```

Ejecuta:

```bash
python scripts/test_vapi_call.py +56912345678
```

### Prueba 3: Monitorear en Dashboard

1. Ve al dashboard de Vapi
2. Abre **Calls** → **Recent Calls**
3. Deberías ver tu llamada de prueba
4. Click en ella para ver:
   - Estado en tiempo real
   - Transcripción
   - Audio de la grabación
   - Costo

---

## 📊 Paso 7: Comparar Costos

### Cálculo de Ejemplo

Supongamos **100 llamadas/mes**, promedio **3 minutos** cada una:

#### Twilio (Actual)
- Llamada: 100 × 3 min × $0.013/min = **$3.90/mes**
- TTS (texto a voz): ~$1.00
- Transcripción: ~$2.00
- Desarrollo/Mantenimiento: ~$500/mes (tiempo de dev)
- **TOTAL: ~$506.90/mes**

#### Vapi.ai (Nuevo)
- Llamadas: 100 × 3 min × $0.08/min = **$24.00/mes**
- Todo incluido: IA, TTS, Transcripción, Análisis
- Sin desarrollo adicional
- **TOTAL: ~$24.00/mes**

**💰 Ahorro estimado: $482.90/mes** (95% menos)

---

## 🔍 Paso 8: Monitorear y Analizar

### Métricas Clave en Vapi Dashboard

1. **Call Success Rate**: % de llamadas completadas
2. **Average Duration**: Duración promedio
3. **Lead Qualification Rate**: % de leads calificados
4. **Cost per Call**: Costo por llamada
5. **Transcript Quality**: Calidad de transcripción

### Optimización Continua

1. **Semana 1**: Monitorear transcripciones y ajustar el prompt
2. **Semana 2**: Analizar objeciones comunes y mejorar respuestas
3. **Semana 3**: Optimizar tiempo de llamada (reducir a 2-3 min)
4. **Semana 4**: Evaluar tasa de conversión vs llamadas manuales

---

## 🎯 Prompt Optimizado para Agente Inmobiliario

Este prompt ya está incluido en `vapi_assistant_service.py`, pero puedes personalizarlo:

```text
# Agente de Calificación de Leads - [Tu Empresa]

## Tu Identidad
Eres [Nombre], un asistente de voz profesional y amable de [Tu Empresa]. 
Tu objetivo es calificar leads de manera natural y conversacional.

## Información a Obtener (en orden de prioridad):

1. Nombre completo
2. Ubicación preferida (comuna/sector)
3. Presupuesto aproximado
4. Ingresos mensuales
5. Estado DICOM
6. Tipo de propiedad deseada
7. Número de dormitorios
8. Plazo de compra

## Reglas de Oro:

✅ DEBES:
- Hacer UNA pregunta a la vez
- Ser empático y natural
- Agradecer cada respuesta
- Mantener respuestas cortas (2-3 oraciones)
- Ofrecer agendar cita si califica

❌ NO DEBES:
- Sonar robótico
- Hacer múltiples preguntas juntas
- Presionar al cliente
- Hablar de temas no relacionados

## Ejemplos de Conversación:

Cliente: "Hola"
Tú: "¡Hola! ¿Cómo estás? Soy [Nombre] de [Empresa]. Te llamo porque 
vimos tu interés en nuestras propiedades. ¿Tienes un momento?"

Cliente: "Sí, dime"
Tú: "Perfecto. Para poder ayudarte mejor, ¿en qué sector estás buscando?"

Cliente: "En Providencia"
Tú: "Excelente elección. ¿Y qué presupuesto aproximado tienes en mente?"
```

---

## 🚨 Troubleshooting

### Problema: "La voz suena robótica"

**Solución:**
1. Ve a Settings → Voice
2. Cambia a voces premium:
   - `es-MX-DaliaNeural` (Mexico, femenina)
   - `es-MX-JorgeNeural` (Mexico, masculina)
   - `es-CL-CatalinaNeural` (Chile, femenina)

### Problema: "El asistente no entiende el español chileno"

**Solución:**
1. En el prompt, agrega ejemplos de modismos:
```
Reconoce estas expresiones chilenas:
- "cachar" = entender
- "al tiro" = inmediatamente
- "pololo/polola" = novio/novia
```

2. Usa transcriber chileno:
```json
"transcriber": {
    "provider": "deepgram",
    "model": "nova-2",
    "language": "es-CL"
}
```

### Problema: "Las llamadas son muy caras"

**Solución:**
1. Reduce `maxDurationSeconds` a 180 (3 minutos)
2. Entrena al asistente para ser más directo
3. Usa modelo más económico: `gpt-3.5-turbo` en lugar de `gpt-4o`

### Problema: "El webhook no recibe eventos"

**Solución:**
1. Verifica que tu backend esté público (no localhost)
2. Revisa logs de Vapi Dashboard → Webhooks → Deliveries
3. Asegúrate de que la URL sea HTTPS
4. Verifica que el endpoint responda con 200 OK

---

## 📚 Recursos Adicionales

- **Documentación oficial**: https://docs.vapi.ai
- **Dashboard**: https://dashboard.vapi.ai
- **Comunidad**: https://discord.gg/vapi
- **Ejemplos de código**: https://github.com/VapiAI/examples
- **Pricing**: https://vapi.ai/pricing

---

## ✅ Checklist de Migración

- [ ] Cuenta de Vapi.ai creada
- [ ] API Key obtenida
- [ ] Número de teléfono configurado
- [ ] Asistente creado y configurado
- [ ] Variables de entorno actualizadas
- [ ] Webhooks configurados
- [ ] Llamada de prueba exitosa
- [ ] Prompt personalizado
- [ ] Monitoreo configurado
- [ ] Equipo capacitado

---

## 🎓 Próximos Pasos

1. **Migración gradual**: Mantén Twilio activo durante 2 semanas
2. **A/B Testing**: Compara resultados Vapi vs manual
3. **Capacitación**: Entrena a tu equipo en el dashboard de Vapi
4. **Optimización**: Ajusta el prompt según feedback real
5. **Escalado**: Una vez validado, migra el 100% a Vapi

---

## 🆘 Soporte

Si tienes problemas:
1. Revisa los logs en Railway: `railway logs`
2. Revisa el dashboard de Vapi: https://dashboard.vapi.ai
3. Contacta a soporte de Vapi: support@vapi.ai
4. Revisa la documentación: https://docs.vapi.ai

---

**¡Éxito con la migración! 🚀**
