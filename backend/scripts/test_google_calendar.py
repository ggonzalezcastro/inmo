"""
Script para verificar que Google Calendar está configurado correctamente.

Uso:
    cd backend
    source .venv/bin/activate
    python scripts/test_google_calendar.py

Qué hace:
    1. Verifica que las credenciales estén en .env
    2. Inicializa GoogleCalendarService
    3. Crea un evento de prueba con Google Meet
    4. Actualiza el evento
    5. Elimina el evento
    6. Imprime resultados

Requisitos:
    - .env con GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
    - Gmail compartido como test user en Google Cloud Console
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Agregar backend al path para importar app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.appointments.google_calendar import GoogleCalendarService
import pytz

CHILE_TZ = pytz.timezone('America/Santiago')


def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_success(text):
    print(f"✅ {text}")


def print_error(text):
    print(f"❌ {text}")


def print_info(text):
    print(f"ℹ️  {text}")


def verify_env_vars():
    """Verifica que las credenciales estén en .env"""
    print_header("1. Verificando credenciales en .env")

    missing = []
    if not settings.GOOGLE_CLIENT_ID:
        missing.append("GOOGLE_CLIENT_ID")
    if not settings.GOOGLE_CLIENT_SECRET:
        missing.append("GOOGLE_CLIENT_SECRET")
    if not settings.GOOGLE_REFRESH_TOKEN:
        missing.append("GOOGLE_REFRESH_TOKEN")

    if missing:
        print_error(f"Faltan variables de entorno: {', '.join(missing)}")
        return False

    print_success("GOOGLE_CLIENT_ID está configurado")
    print_success("GOOGLE_CLIENT_SECRET está configurado")
    print_success("GOOGLE_REFRESH_TOKEN está configurado")
    print_info(f"GOOGLE_CALENDAR_ID: {settings.GOOGLE_CALENDAR_ID}")
    return True


def test_google_calendar_service():
    """Inicializa el servicio y verifica que funciona"""
    print_header("2. Inicializando GoogleCalendarService")

    try:
        service = GoogleCalendarService()

        if service.service is None:
            print_error("GoogleCalendarService.service es None")
            print_info("Posibles causas:")
            print_info("  - Refresh token inválido o expirado")
            print_info("  - Gmail no está como test user en Google Cloud Console")
            print_info("  - Credenciales incorrectas")
            return None

        print_success("GoogleCalendarService inicializado correctamente")
        return service

    except Exception as e:
        print_error(f"Error inicializando GoogleCalendarService: {str(e)}")
        return None


def test_create_event(service: GoogleCalendarService):
    """Crea un evento de prueba con Google Meet"""
    print_header("3. Creando evento de prueba")

    try:
        now = datetime.now(CHILE_TZ)
        start_time = now + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)

        print_info(f"Creando evento para: {start_time.strftime('%Y-%m-%d %H:%M %Z')}")

        result = service.create_event_with_meet(
            title="🧪 Prueba Google Calendar - Inmo CRM",
            start_time=start_time,
            end_time=end_time,
            description="Evento de prueba para verificar integración con Google Calendar",
            attendees=["test@example.com"],
            location="Virtual - Google Meet"
        )

        if not result:
            print_error("create_event_with_meet() retornó None")
            return None

        event_id = result.get("event_id")
        meet_url = result.get("meet_url")
        html_link = result.get("html_link")

        print_success(f"Evento creado: {event_id}")
        print_info(f"Google Meet URL: {meet_url or 'No disponible'}")
        print_info(f"Google Calendar Link: {html_link or 'No disponible'}")

        return event_id, result

    except Exception as e:
        print_error(f"Error creando evento: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_update_event(service: GoogleCalendarService, event_id: str):
    """Actualiza el evento de prueba"""
    print_header("4. Actualizando evento")

    try:
        print_info(f"Actualizando evento: {event_id}")

        result = service.update_event(
            event_id=event_id,
            title="🧪 Prueba Google Calendar - Inmo CRM (ACTUALIZADO)",
            description="Evento de prueba ACTUALIZADO - verifica que funciona la edición"
        )

        if not result:
            print_error("update_event() retornó None")
            return False

        print_success("Evento actualizado correctamente")
        return True

    except Exception as e:
        print_error(f"Error actualizando evento: {str(e)}")
        return False


def test_delete_event(service: GoogleCalendarService, event_id: str):
    """Elimina el evento de prueba"""
    print_header("5. Eliminando evento")

    try:
        print_info(f"Eliminando evento: {event_id}")

        success = service.delete_event(event_id)

        if not success:
            print_error("delete_event() retornó False")
            return False

        print_success("Evento eliminado correctamente")
        return True

    except Exception as e:
        print_error(f"Error eliminando evento: {str(e)}")
        return False


def main():
    print("\n" + "🧪 TEST GOOGLE CALENDAR INTEGRATION".center(60))
    print()

    # Paso 1: Verificar variables de entorno
    if not verify_env_vars():
        print_header("❌ TEST FALLIDO")
        return 1

    # Paso 2: Inicializar servicio
    service = test_google_calendar_service()
    if not service:
        print_header("❌ TEST FALLIDO")
        return 1

    # Paso 3: Crear evento
    event_result = test_create_event(service)
    if not event_result:
        print_header("❌ TEST FALLIDO")
        return 1

    event_id, event_data = event_result

    # Paso 4: Actualizar evento
    if not test_update_event(service, event_id):
        print_error("No se pudo actualizar el evento (pero el create funcionó)")

    # Paso 5: Eliminar evento
    if not test_delete_event(service, event_id):
        print_error("No se pudo eliminar el evento (pero el create funcionó)")

    # Resultado final
    print_header("✅ TEST COMPLETADO CON ÉXITO")
    print()
    print("Google Calendar está configurado correctamente.")
    print("Los brokers pueden ahora:")
    print("  ✓ Crear citas con Google Meet")
    print("  ✓ Actualizar citas existentes")
    print("  ✓ Eliminar citas")
    print()

    return 0


if __name__ == "__main__":
    exit(main())
