"""
Script para obtener el refresh token de Google OAuth2.

Uso:
    cd backend
    source .venv/bin/activate
    python scripts/get_google_token.py

Requisitos:
    - credentials.json descargado de Google Cloud Console (OAuth 2.0 Desktop app)
    - El Gmail compartido debe estar como "Test user" en OAuth consent screen

Al finalizar imprime las variables de entorno listas para pegar en .env
"""
import os
import json
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
except ImportError:
    print("ERROR: Dependencias no instaladas.")
    print("Corre: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Buscar credentials.json en varias ubicaciones
SEARCH_PATHS = [
    Path("credentials.json"),
    Path("backend/credentials.json"),
    Path(__file__).parent.parent / "credentials.json",
]

credentials_path = None
for p in SEARCH_PATHS:
    if p.exists():
        credentials_path = p
        break

if not credentials_path:
    print("ERROR: No se encontró credentials.json")
    print("Descárgalo desde Google Cloud Console → APIs & Services → Credentials")
    print("y guárdalo en backend/credentials.json")
    sys.exit(1)

print(f"Usando credenciales: {credentials_path}")
print()
print("Se abrirá el navegador para autenticarte con el Gmail compartido.")
print("Asegúrate de iniciar sesión con la cuenta correcta.\n")

flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
creds = flow.run_local_server(port=0)

# Leer client_id y client_secret del archivo de credenciales
with open(credentials_path) as f:
    client_data = json.load(f)

client_info = client_data.get("installed") or client_data.get("web", {})
client_id = client_info.get("client_id", "")
client_secret = client_info.get("client_secret", "")

print("\n" + "=" * 60)
print("ÉXITO - Agrega estas variables a tu .env:")
print("=" * 60)
print(f"GOOGLE_CLIENT_ID={client_id}")
print(f"GOOGLE_CLIENT_SECRET={client_secret}")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
print(f"GOOGLE_CALENDAR_ID=primary")
print("=" * 60)
print()
print("NOTA: GOOGLE_CALENDAR_ID=primary usa el calendario principal del Gmail.")
print("Para usar un calendario específico, reemplázalo con el ID del calendario.")
print("(Se encuentra en Google Calendar → Configuración del calendario → ID del calendario)")
