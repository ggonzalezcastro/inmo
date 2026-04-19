"""
Seed script: create v1.1.0 (adds few-shot examples) for every broker
that does not yet have it. Activates v1.1.0 and deactivates all others.

Safe to run multiple times (idempotent).

Usage (inside Docker):
    docker compose run --rm backend python scripts/seed_prompt_v1_1.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update

from app.config import settings
from app.models.broker import Broker
from app.models.prompt_version import PromptVersion
from app.services.broker.prompt_defaults import DEFAULT_SYSTEM_PROMPT


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        result = await db.execute(select(Broker).where(Broker.is_active == True))
        brokers = result.scalars().all()

        seeded = 0
        skipped = 0

        for broker in brokers:
            existing = await db.execute(
                select(PromptVersion).where(
                    PromptVersion.broker_id == broker.id,
                    PromptVersion.version_tag == "v1.1.0",
                )
            )
            if existing.scalars().first():
                print(f"  [SKIP]  broker_id={broker.id} ({broker.name}) — v1.1.0 already exists")
                skipped += 1
                continue

            # Deactivate previous versions
            await db.execute(
                update(PromptVersion)
                .where(PromptVersion.broker_id == broker.id)
                .values(is_active=False)
            )

            pv = PromptVersion(
                broker_id=broker.id,
                version_tag="v1.1.0",
                content=DEFAULT_SYSTEM_PROMPT,
                sections_json={"includes_few_shots": True},
                is_active=True,
                created_by=None,
            )
            db.add(pv)
            print(f"  [SEED]  broker_id={broker.id} ({broker.name}) — v1.1.0 created (active)")
            seeded += 1

        await db.commit()

    await engine.dispose()
    print(f"\nDone. Seeded: {seeded}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(seed())
