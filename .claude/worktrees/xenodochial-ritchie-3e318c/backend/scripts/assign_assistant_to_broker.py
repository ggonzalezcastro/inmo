#!/usr/bin/env python3
"""
Asigna un assistant_id de Vapi a un broker (BrokerVoiceConfig.assistant_id_default).
Útil si ya creaste el asistente con create_vapi_assistant.py y no lo guardaste en BD.
Usage: python scripts/assign_assistant_to_broker.py

Con Docker: docker compose exec backend python scripts/assign_assistant_to_broker.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.broker_voice_config import BrokerVoiceConfig


async def main():
    broker_id_str = input("Broker ID (empresa): ").strip()
    if not broker_id_str:
        print("Broker ID is required")
        sys.exit(1)
    try:
        broker_id = int(broker_id_str)
    except ValueError:
        print("Broker ID must be an integer")
        sys.exit(1)

    assistant_id = input("Assistant ID (UUID de Vapi): ").strip()
    if not assistant_id:
        print("Assistant ID is required")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BrokerVoiceConfig).where(BrokerVoiceConfig.broker_id == broker_id)
        )
        config = result.scalars().first()

        if not config:
            print(f"No existe BrokerVoiceConfig para broker {broker_id}")
            print("Ejecuta primero la inicialización del broker.")
            sys.exit(1)

        config.assistant_id_default = assistant_id
        await db.commit()

        print(f"Asistente asignado al broker {broker_id}")
        print(f"   Assistant ID: {assistant_id}")


if __name__ == "__main__":
    asyncio.run(main())
