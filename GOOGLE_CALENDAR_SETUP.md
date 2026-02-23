# Configuración de Google Calendar API

Para generar URLs reales de Google Meet, necesitas configurar la integración con Google Calendar API.

## Opción 1: Service Account (Recomendado para Producción)

### Pasos:

1. **Crear un proyecto en Google Cloud Console**
   - Ve a [Google Cloud Console](https://console.cloud.google.com/)
   - Crea un nuevo proyecto o selecciona uno existente

2. **Habilitar Google Calendar API**
   - En el menú lateral, ve a "APIs & Services" > "Library"
   - Busca "Google Calendar API"
   - Haz clic en "Enable"

3. **Crear una Service Account**
   - Ve a "APIs & Services" > "Credentials"
   - Haz clic en "Create Credentials" > "Service Account"
   - Completa el formulario y crea la cuenta
   - Descarga el archivo JSON de credenciales

4. **Compartir el calendario con la Service Account**
   - Abre Google Calendar
   - Ve a "Settings" > "Settings for my calendars"
   - Selecciona el calendario que quieres usar
   - En "Share with specific people", agrega el email de la Service Account
   - Dale permisos de "Make changes to events"

5. **Configurar las variables de entorno**
   ```bash
   GOOGLE_CREDENTIALS_PATH=/path/to/service-account-credentials.json
   GOOGLE_CALENDAR_ID=primary  # o el ID de tu calendario específico
   ```

## Opción 2: OAuth2 (Para Desarrollo)

### Pasos:

1. **Crear un proyecto en Google Cloud Console**
   - Ve a [Google Cloud Console](https://console.cloud.google.com/)
   - Crea un nuevo proyecto o selecciona uno existente

2. **Habilitar Google Calendar API**
   - En el menú lateral, ve a "APIs & Services" > "Library"
   - Busca "Google Calendar API"
   - Haz clic en "Enable"

3. **Crear credenciales OAuth2**
   - Ve a "APIs & Services" > "Credentials"
   - Haz clic en "Create Credentials" > "OAuth client ID"
   - Selecciona "Desktop app" como tipo de aplicación
   - Descarga el archivo JSON de credenciales

4. **Obtener el Refresh Token**
   
   Ejecuta este script Python para obtener el refresh token:
   
   ```python
   from google_auth_oauthlib.flow import InstalledAppFlow
   import pickle
   
   SCOPES = ['https://www.googleapis.com/auth/calendar']
   
   flow = InstalledAppFlow.from_client_secrets_file(
       'credentials.json',  # El archivo JSON descargado
       SCOPES
   )
   creds = flow.run_local_server(port=0)
   
   # Guardar el refresh token
   with open('token.pickle', 'wb') as token:
       pickle.dump(creds, token)
   
   print(f"Refresh Token: {creds.refresh_token}")
   ```

5. **Configurar las variables de entorno**
   ```bash
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   GOOGLE_REFRESH_TOKEN=your-refresh-token
   GOOGLE_CALENDAR_ID=primary
   ```

## Verificación

Una vez configurado, puedes verificar que funciona ejecutando el script de pruebas:

```bash
cd backend
python scripts/test_appointments.py
```

Si la configuración es correcta, verás URLs reales de Google Meet en las citas creadas.

## Notas Importantes

- **Service Account**: Es más seguro para producción, no requiere interacción del usuario
- **OAuth2**: Requiere autenticación inicial, pero es más fácil de configurar para desarrollo
- **Límites**: Google Calendar API tiene límites de cuota (1,000,000 requests/día por defecto)
- **Seguridad**: Nunca subas los archivos de credenciales al repositorio. Agrégalos a `.gitignore`

## Troubleshooting

### Error: "Calendar not found"
- Verifica que el `GOOGLE_CALENDAR_ID` sea correcto
- Para Service Account, asegúrate de haber compartido el calendario con el email de la Service Account

### Error: "Insufficient permissions"
- Verifica que la Service Account tenga permisos de "Make changes to events" en el calendario
- Para OAuth2, verifica que el scope incluya `https://www.googleapis.com/auth/calendar`

### Error: "Invalid credentials"
- Verifica que las credenciales no hayan expirado
- Para OAuth2, regenera el refresh token si es necesario

