#!/usr/bin/env python3
"""
Create a Vapi.ai assistant using broker configuration (same prompt as chat).
Usage: python scripts/create_vapi_assistant.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.voice import VapiAssistantService


async def main():
    print("Create Vapi assistant from broker config (same prompt as chat)\n")

    if not getattr(settings, "VAPI_API_KEY", None):
        print("Error: VAPI_API_KEY not set in .env")
        sys.exit(1)

    broker_id_str = input("Broker ID (company id from brokers table): ").strip()
    if not broker_id_str:
        print("Broker ID is required")
        sys.exit(1)
    try:
        broker_id = int(broker_id_str)
    except ValueError:
        print("Broker ID must be an integer")
        sys.exit(1)

    agent_type = input("Agent type (optional, e.g. perfilador; Enter for default): ").strip() or None

    try:
        async with AsyncSessionLocal() as db:
            assistant = await VapiAssistantService.create_assistant_for_broker(
                db, broker_id, agent_type
            )
            assistant_id = assistant.get("id")
            print("\nAssistant created (mismo prompt que el chat, adaptado para voz).")
            print("Assistant ID:", assistant_id)

            # Ofrecer guardar en BD para este broker
            from sqlalchemy import select
            from app.models.broker_voice_config import BrokerVoiceConfig

            result = await db.execute(
                select(BrokerVoiceConfig).where(BrokerVoiceConfig.broker_id == broker_id)
            )
            config = result.scalars().first()
            if config:
                save = input("\nGuardar este ID en BrokerVoiceConfig para este broker? (s/n): ").strip().lower()
                if save == "s":
                    config.assistant_id_default = assistant_id
                    await db.commit()
                    print(f"Guardado. Broker {broker_id} usará este asistente en llamadas.")
            else:
                print("\nNo existe BrokerVoiceConfig para este broker. Crea uno (p. ej. al inicializar broker).")
                print("Mientras tanto puedes usar VAPI_ASSISTANT_ID en .env con este ID:", assistant_id)

            print("\nTest: docker compose exec backend python scripts/test_voice_call_full.py", broker_id, "+56954100804")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
