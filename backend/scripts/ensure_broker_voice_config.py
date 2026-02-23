#!/usr/bin/env python3
"""
Lista brokers y crea BrokerVoiceConfig si no existe (p. ej. broker creado antes de tener voz).
Uso:
  python scripts/ensure_broker_voice_config.py          # listar y ofrecer crear
  python scripts/ensure_broker_voice_config.py 1         # asegurar broker_id=1

Con Docker: docker compose exec backend python scripts/ensure_broker_voice_config.py [broker_id]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.broker import Broker
from app.models.broker_voice_config import BrokerVoiceConfig


async def main():
    broker_id_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None

    async with AsyncSessionLocal() as db:
        if broker_id_arg:
            result = await db.execute(select(Broker).where(Broker.id == broker_id_arg))
            brokers = [result.scalars().first()] if result.scalars().first() else []
            if not brokers:
                print(f"No existe broker con id {broker_id_arg}")
                sys.exit(1)
        else:
            result = await db.execute(select(Broker).order_by(Broker.id))
            brokers = list(result.scalars().unique().all())

        if not brokers:
            print("No hay brokers en la BD.")
            sys.exit(0)

        print("Brokers en la BD:")
        print("-" * 60)
        for b in brokers:
            vc_result = await db.execute(
                select(BrokerVoiceConfig).where(BrokerVoiceConfig.broker_id == b.id)
            )
            voice_config = vc_result.scalars().first()
            tiene_voz = "sí" if voice_config else "no"
            print(f"  Broker ID: {b.id}  |  Nombre: {b.name}  |  BrokerVoiceConfig: {tiene_voz}")
        print("-" * 60)

        # Crear los que no tienen
        creados = 0
        for b in brokers:
            vc_result = await db.execute(
                select(BrokerVoiceConfig).where(BrokerVoiceConfig.broker_id == b.id)
            )
            if vc_result.scalars().first():
                continue
            voice_config = BrokerVoiceConfig(
                broker_id=b.id,
                recording_enabled=True,
            )
            db.add(voice_config)
            creados += 1
            print(f"Creado BrokerVoiceConfig para broker {b.id} ({b.name}).")

        if creados:
            await db.commit()
            print(f"\nListo. {creados} config(s) de voz creado(s).")
        else:
            print("\nTodos los brokers ya tienen BrokerVoiceConfig.")


if __name__ == "__main__":
    asyncio.run(main())
