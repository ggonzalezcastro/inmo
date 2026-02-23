#!/usr/bin/env python3
"""
Script para asignar un phone_number_id de Vapi a un broker.
Usage: python scripts/assign_phone_number_to_broker.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.broker_voice_config import BrokerVoiceConfig


async def main():
    broker_id_str = input("Broker ID: ").strip()
    if not broker_id_str:
        print("Broker ID is required")
        sys.exit(1)
    try:
        broker_id = int(broker_id_str)
    except ValueError:
        print("Broker ID must be an integer")
        sys.exit(1)

    phone_number_id = input("Phone Number ID de Vapi: ").strip()
    if not phone_number_id:
        print("Phone Number ID is required")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BrokerVoiceConfig).where(BrokerVoiceConfig.broker_id == broker_id)
        )
        config = result.scalars().first()

        if not config:
            print(f"No existe BrokerVoiceConfig para broker {broker_id}")
            print("Ejecuta primero la inicialización del broker")
            sys.exit(1)

        config.phone_number_id = phone_number_id
        await db.commit()

        print(f"Phone number asignado al broker {broker_id}")
        print(f"   Phone Number ID: {phone_number_id}")


if __name__ == "__main__":
    asyncio.run(main())
