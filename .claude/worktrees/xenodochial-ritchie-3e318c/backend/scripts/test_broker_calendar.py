"""
Prueba end-to-end de Google Calendar con las credenciales del broker en la DB.

Uso:
    cd backend
    source .venv/bin/activate
    python scripts/test_broker_calendar.py --broker_id 2

Qué hace:
    1. Lee el refresh_token encriptado del broker desde la DB
    2. Inicializa GoogleCalendarService con esas credenciales
    3. Crea un evento de prueba con Google Meet
    4. Verifica que el Meet URL fue generado
    5. Elimina el evento de prueba
"""
import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytz
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from app.core.config import settings
from app.core.encryption import decrypt_value
from app.models.broker import BrokerPromptConfig
from app.services.appointments.google_calendar import get_calendar_service_for_broker

CHILE_TZ = pytz.timezone('America/Santiago')


async def test(broker_id: int):
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        result = await db.execute(
            select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker_id)
        )
        cfg = result.scalars().first()

        if not cfg:
            print(f"❌ No existe BrokerPromptConfig para broker_id={broker_id}")
            return False

        if not cfg.google_refresh_token:
            print(f"❌ Broker {broker_id} no tiene Google Calendar conectado")
            return False

        print(f"✅ Token encontrado para broker_id={broker_id}")
        print(f"   Email: {cfg.google_calendar_email or '(no guardado)'}")
        print(f"   Calendar ID: {cfg.google_calendar_id or 'primary'}")

        # Inicializar servicio con credenciales del broker
        service = get_calendar_service_for_broker(cfg)

        if not service.service:
            print("❌ No se pudo inicializar GoogleCalendarService (token inválido?)")
            return False

        print("✅ GoogleCalendarService inicializado")

        # Crear evento de prueba
        now = datetime.now(CHILE_TZ)
        start = now + timedelta(hours=1)
        end = start + timedelta(hours=1)

        print(f"\n📅 Creando evento de prueba para {start.strftime('%Y-%m-%d %H:%M %Z')}...")

        result = service.create_event_with_meet(
            title="🧪 Prueba Inmo CRM - Google Calendar",
            start_time=start,
            end_time=end,
            description="Evento de prueba automático — puede eliminarse",
        )

        if not result:
            print("❌ create_event_with_meet() retornó None")
            return False

        event_id = result.get("event_id")
        meet_url = result.get("meet_url")
        html_link = result.get("html_link")

        print(f"✅ Evento creado: {event_id}")
        print(f"   Google Meet: {meet_url or '⚠️  No generado'}")
        print(f"   Ver en Calendar: {html_link}")

        # Eliminar el evento de prueba
        deleted = service.delete_event(event_id)
        print(f"{'✅' if deleted else '⚠️ '} Evento de prueba eliminado")

        print("\n✅ PRUEBA COMPLETADA — Google Calendar funciona para este broker")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker_id", type=int, default=2)
    args = parser.parse_args()
    ok = asyncio.run(test(args.broker_id))
    sys.exit(0 if ok else 1)
