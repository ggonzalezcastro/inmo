"""
Seed script: register DEFAULT_SYSTEM_PROMPT as v1.0.0 for every broker
that does not yet have any prompt_versions row.

Safe to run multiple times (idempotent — skips brokers that already have a v1.0.0).

Usage (inside Docker):
    docker compose run --rm backend python scripts/seed_prompt_v1.py
"""
import asyncio
import os
import sys

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from app.config import settings
from app.models.broker import Broker
from app.models.prompt_version import PromptVersion
from app.services.broker.prompt_defaults import DEFAULT_SYSTEM_PROMPT


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Fetch all active brokers
        result = await db.execute(select(Broker).where(Broker.is_active == True))
        brokers = result.scalars().all()

        seeded = 0
        skipped = 0

        for broker in brokers:
            # Check whether v1.0.0 already exists
            existing = await db.execute(
                select(PromptVersion).where(
                    PromptVersion.broker_id == broker.id,
                    PromptVersion.version_tag == "v1.0.0",
                )
            )
            if existing.scalars().first():
                print(f"  [SKIP]  broker_id={broker.id} ({broker.name}) — v1.0.0 already exists")
                skipped += 1
                continue

            # Deactivate any existing active versions (shouldn't be any yet)
            pv = PromptVersion(
                broker_id=broker.id,
                version_tag="v1.0.0",
                content=DEFAULT_SYSTEM_PROMPT,
                is_active=True,
                created_by=None,
            )
            db.add(pv)
            print(f"  [SEED]  broker_id={broker.id} ({broker.name}) — v1.0.0 created (active)")
            seeded += 1

        await db.commit()

    await engine.dispose()
    print(f"\nDone. Seeded: {seeded}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(seed())
