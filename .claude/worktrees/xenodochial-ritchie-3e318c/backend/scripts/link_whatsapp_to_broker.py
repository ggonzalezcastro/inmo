#!/usr/bin/env python3
"""
Vincula el phone_number_id de Meta al broker en broker_chat_configs.

Sin esto, el webhook recibe el POST pero la tarea Celery no encuentra broker y no procesa.

Uso (desde backend/, con .env cargado — mismo directorio que uvicorn):
  export WHATSAPP_PHONE_NUMBER_ID=1005894865947616
  python scripts/link_whatsapp_to_broker.py 1

  # o pasar el id explícito:
  python scripts/link_whatsapp_to_broker.py 1 1005894865947616

Docker:
  docker compose exec backend python scripts/link_whatsapp_to_broker.py 1
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import AsyncSessionLocal
from app.models.broker import Broker
from app.models.broker_chat_config import BrokerChatConfig
from app.models.chat_message import ChatProvider


async def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    broker_id = int(sys.argv[1])
    phone_id = (sys.argv[2] if len(sys.argv) > 2 else os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")).strip()
    if not phone_id:
        print("Falta WHATSAPP_PHONE_NUMBER_ID en el entorno o como segundo argumento.")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        b = (await db.execute(select(Broker).where(Broker.id == broker_id))).scalars().first()
        if not b:
            print(f"No existe broker id={broker_id}")
            sys.exit(1)

        result = await db.execute(
            select(BrokerChatConfig).where(BrokerChatConfig.broker_id == broker_id)
        )
        row = result.scalars().first()

        if not row:
            row = BrokerChatConfig(
                broker_id=broker_id,
                enabled_providers=["whatsapp"],
                default_provider=ChatProvider.WHATSAPP,
                provider_configs={
                    "whatsapp": {
                        "phone_number_id": phone_id,
                    }
                },
            )
            db.add(row)
            print(f"Creado BrokerChatConfig para broker {broker_id} con whatsapp.phone_number_id={phone_id}")
        else:
            merged = dict(row.provider_configs or {})
            wa = dict(merged.get("whatsapp") or {})
            wa["phone_number_id"] = phone_id
            merged["whatsapp"] = wa
            row.provider_configs = merged
            flag_modified(row, "provider_configs")

            enabled = list(row.enabled_providers or [])
            if "whatsapp" not in enabled:
                enabled.append("whatsapp")
                row.enabled_providers = enabled
                flag_modified(row, "enabled_providers")

            print(f"Actualizado broker {broker_id}: whatsapp.phone_number_id={phone_id}")

        await db.commit()

    print("Listo. En Meta el webhook debe apuntar a .../webhooks/whatsapp con el mismo WHATSAPP_VERIFY_TOKEN.")


if __name__ == "__main__":
    asyncio.run(main())
