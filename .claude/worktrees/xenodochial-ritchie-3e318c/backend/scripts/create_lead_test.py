#!/usr/bin/env python3
"""
Crea un lead de prueba con teléfono +56954100804 asignado a un broker existente.
Uso: python scripts/create_lead_test.py

Con Docker: docker compose exec backend python scripts/create_lead_test.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.lead import Lead, LeadStatus
from app.models.broker import Broker
from app.models.user import User


async def main():
    phone = "+56954100804"

    async with AsyncSessionLocal() as db:
        # Cualquier broker (empresa)
        broker_result = await db.execute(select(Broker).where(Broker.is_active == True).limit(1))
        broker = broker_result.scalars().first()
        if not broker:
            print("No hay ningún broker en la BD. Crea uno antes (p. ej. registrando un usuario).")
            sys.exit(1)

        # Algún usuario de ese broker (agente) para assigned_to
        user_result = await db.execute(
            select(User).where(User.broker_id == broker.id).limit(1)
        )
        user = user_result.scalars().first()

        lead = Lead(
            phone=phone,
            name="Lead prueba voz",
            status=LeadStatus.COLD,
            broker_id=broker.id,
            assigned_to=user.id if user else None,
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        print("Lead de prueba creado:")
        print(f"  Lead ID:    {lead.id}")
        print(f"  Teléfono:  {lead.phone}")
        print(f"  Broker ID: {lead.broker_id} ({broker.name})")
        print(f"  Asignado a user_id: {lead.assigned_to}")
        print()
        print("Para probar llamada por API con este lead:")
        print(f"  POST /api/v1/voice/initiate  body: {{ \"lead_id\": {lead.id} }}")
        print()
        print("O con el script (usa broker_id del broker, no lead_id):")
        print(f"  python scripts/test_voice_call_full.py {broker.id} {phone}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
