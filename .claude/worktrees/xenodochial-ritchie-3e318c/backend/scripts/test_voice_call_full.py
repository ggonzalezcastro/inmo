#!/usr/bin/env python3
"""
Prueba de llamada de voz usando configuración por broker (BD).
Edita los valores en CONFIG abajo o pásalos por argumentos.

Uso:
  python scripts/test_voice_call_full.py
  python scripts/test_voice_call_full.py <broker_id> <telefono>
  python scripts/test_voice_call_full.py 1 +56912345678

Con Docker:
  docker compose exec backend python scripts/test_voice_call_full.py
  docker compose exec backend python scripts/test_voice_call_full.py 1 +56912345678
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- CONFIG (editar en duro para tu prueba) ---
BROKER_ID = 1
PHONE = "+56912345678"
AGENT_TYPE = None  # opcional: "perfilador", "calificador", "agendador", "seguimiento"
# --- fin CONFIG ---

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.voice import get_voice_provider
from app.services.broker import BrokerVoiceConfigService


async def run():
    broker_id = BROKER_ID
    phone = PHONE
    agent_type = AGENT_TYPE

    if len(sys.argv) >= 3:
        try:
            broker_id = int(sys.argv[1])
            phone = sys.argv[2]
        except ValueError:
            print("Uso: python scripts/test_voice_call_full.py [broker_id] [telefono]")
            sys.exit(1)
    elif len(sys.argv) == 2:
        phone = sys.argv[1]

    print("Prueba de llamada (config por broker)")
    print("=" * 50)
    print(f"  Broker ID (empresa): {broker_id}")
    print(f"  Teléfono:            {phone}")
    print(f"  Agent type:          {agent_type or '(default)'}")
    print("=" * 50)

    if not getattr(settings, "VAPI_API_KEY", None):
        print("Error: VAPI_API_KEY no configurada en .env")
        sys.exit(1)

    webhook_base = getattr(settings, "WEBHOOK_BASE_URL", "http://localhost:8000")
    webhook_url = f"{webhook_base}/api/v1/calls/webhooks/voice"

    provider = get_voice_provider()

    async with AsyncSessionLocal() as db:
        try:
            phone_number_id = await BrokerVoiceConfigService.get_phone_number_id(db, broker_id)
            assistant_id = await BrokerVoiceConfigService.get_assistant_id(db, broker_id, agent_type)
            print(f"  Phone Number ID:     {phone_number_id[:20]}...")
            print(f"  Assistant ID:        {assistant_id[:20]}...")
            print("=" * 50)
        except Exception as e:
            print(f"Error al leer config del broker: {e}")
            print("Asegúrate de que exista BrokerVoiceConfig para este broker y que tenga")
            print("phone_number_id y/o assistant_id_default, o define VAPI_PHONE_NUMBER_ID y")
            print("VAPI_ASSISTANT_ID en .env como fallback global.")
            sys.exit(1)

        context = {
            "db": db,
            "broker_id": broker_id,
            "agent_type": agent_type,
            "lead_id": None,
            "campaign_id": None,
        }
        try:
            call_id = await provider.make_call(
                phone=phone,
                webhook_url=webhook_url,
                context=context,
            )
            print("Llamada iniciada correctamente")
            print(f"  Call ID: {call_id}")
            print(f"  Dashboard: https://dashboard.vapi.ai/calls/{call_id}")
        except Exception as e:
            print(f"Error al iniciar llamada: {e}")
            sys.exit(1)

    print("=" * 50)
    print("Esperando 5 s y consultando estado...")
    await asyncio.sleep(5)
    try:
        status = await provider.get_call_status(call_id)
        print(f"  Status: {status.get('status')}")
        print(f"  From:   {status.get('from')}")
        print(f"  To:     {status.get('to')}")
    except Exception as e:
        print(f"  (no se pudo obtener estado: {e})")


if __name__ == "__main__":
    asyncio.run(run())
