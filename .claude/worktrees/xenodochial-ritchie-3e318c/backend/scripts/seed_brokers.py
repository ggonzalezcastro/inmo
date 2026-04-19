"""
Seed script: crea 3 inmobiliarias con 2 agentes cada una.
Todas las cuentas tienen contraseña: 123

Idempotente — si ya existe un broker con ese slug, lo omite.

Uso (dentro de Docker):
    docker compose exec backend python scripts/seed_brokers.py

Uso (local con venv):
    cd backend && .venv/bin/python scripts/seed_brokers.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.config import settings
from app.middleware.auth import hash_password

# ──────────────────────────────────────────────
# Datos de seed
# ──────────────────────────────────────────────

BROKERS_DATA = [
    {
        "name": "Inmobiliaria Santiago Centro",
        "slug": "santiago-centro",
        "contact_email": "contacto@santiagocentro.cl",
        "contact_phone": "+56 2 2345 6789",
        "admin": {"name": "Admin Santiago Centro", "email": "admin@santiagocentro.cl"},
        "agents": [
            {"name": "Carlos Ramírez",   "email": "carlos@santiagocentro.cl"},
            {"name": "Valentina Torres", "email": "valentina@santiagocentro.cl"},
        ],
    },
    {
        "name": "Propiedades Las Condes",
        "slug": "las-condes",
        "contact_email": "info@lascondes.cl",
        "contact_phone": "+56 2 2987 6543",
        "admin": {"name": "Admin Las Condes", "email": "admin@lascondes.cl"},
        "agents": [
            {"name": "Andrés Morales",  "email": "andres@lascondes.cl"},
            {"name": "Catalina Vega",   "email": "catalina@lascondes.cl"},
        ],
    },
    {
        "name": "Inmobiliaria Ñuñoa",
        "slug": "nunoa",
        "contact_email": "ventas@nunoa.cl",
        "contact_phone": "+56 2 2111 2222",
        "admin": {"name": "Admin Ñuñoa", "email": "admin@nunoa.cl"},
        "agents": [
            {"name": "Felipe Herrera",  "email": "felipe@nunoa.cl"},
            {"name": "Sofía Castillo",  "email": "sofia@nunoa.cl"},
        ],
    },
]

PASSWORD = "123"


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        hashed_pw = hash_password(PASSWORD)

        for broker_data in BROKERS_DATA:
            # ── Verificar si ya existe ──────────────────────────────────────
            result = await db.execute(
                text("SELECT id FROM brokers WHERE slug = :slug"),
                {"slug": broker_data["slug"]},
            )
            row = result.fetchone()

            if row:
                broker_id = row[0]
                print(f"  [SKIP]  Broker '{broker_data['name']}' ya existe (id={broker_id})")
            else:
                # ── Crear broker ────────────────────────────────────────────
                result = await db.execute(
                    text("""
                        INSERT INTO brokers (name, slug, contact_email, contact_phone, is_active)
                        VALUES (:name, :slug, :contact_email, :contact_phone, true)
                        RETURNING id
                    """),
                    {
                        "name": broker_data["name"],
                        "slug": broker_data["slug"],
                        "contact_email": broker_data["contact_email"],
                        "contact_phone": broker_data["contact_phone"],
                    },
                )
                broker_id = result.fetchone()[0]

                # ── Crear BrokerPromptConfig ─────────────────────────────────
                await db.execute(
                    text("""
                        INSERT INTO broker_prompt_configs
                            (broker_id, agent_name, agent_role, enable_appointment_booking)
                        VALUES (:broker_id, 'Sofía', 'asesora inmobiliaria', true)
                        ON CONFLICT (broker_id) DO NOTHING
                    """),
                    {"broker_id": broker_id},
                )

                # ── Crear BrokerLeadConfig ───────────────────────────────────
                await db.execute(
                    text("""
                        INSERT INTO broker_lead_configs (broker_id)
                        VALUES (:broker_id)
                        ON CONFLICT (broker_id) DO NOTHING
                    """),
                    {"broker_id": broker_id},
                )

                print(f"  [OK]    Broker creado: '{broker_data['name']}' (id={broker_id})")

            # ── Crear admin del broker ──────────────────────────────────────
            admin_data = broker_data["admin"]
            existing_admin = await db.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": admin_data["email"]},
            )
            existing_row = existing_admin.fetchone()
            if existing_row:
                # Ensure role is ADMIN (fix accounts created with wrong role)
                await db.execute(
                    text("UPDATE users SET role = 'ADMIN', broker_id = :broker_id WHERE email = :email"),
                    {"email": admin_data["email"], "broker_id": broker_id},
                )
                print(f"           [FIX]  Admin '{admin_data['email']}' actualizado a ADMIN")
            else:
                await db.execute(
                    text("""
                        INSERT INTO users (email, hashed_password, name, role, broker_id, is_active)
                        VALUES (:email, :hashed_password, :name, 'ADMIN', :broker_id, true)
                    """),
                    {
                        "email": admin_data["email"],
                        "hashed_password": hashed_pw,
                        "name": admin_data["name"],
                        "broker_id": broker_id,
                    },
                )
                print(f"           [OK]   Admin creado:  {admin_data['name']} <{admin_data['email']}>")

            # ── Crear agentes del broker ────────────────────────────────────
            for agent_data in broker_data["agents"]:
                existing = await db.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": agent_data["email"]},
                )
                if existing.fetchone():
                    print(f"           [SKIP] Agente '{agent_data['email']}' ya existe")
                    continue

                await db.execute(
                    text("""
                        INSERT INTO users (email, hashed_password, name, role, broker_id, is_active)
                        VALUES (:email, :hashed_password, :name, 'AGENT', :broker_id, true)
                    """),
                    {
                        "email": agent_data["email"],
                        "hashed_password": hashed_pw,
                        "name": agent_data["name"],
                        "broker_id": broker_id,
                    },
                )
                print(f"           [OK]   Agente creado: {agent_data['name']} <{agent_data['email']}>")

        await db.commit()
        print("\n✅ Seed completado.")
        print(f"   Contraseña de todos los usuarios: {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
