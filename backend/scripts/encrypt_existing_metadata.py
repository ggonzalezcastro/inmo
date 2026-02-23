"""
One-time script: encrypt sensitive fields in existing lead_metadata rows.

Idempotent — already-encrypted fields (starting with "enc:") are skipped.

Usage (inside Docker, requires SECRET_KEY env var):
    docker compose run --rm backend python scripts/encrypt_existing_metadata.py

DRY RUN (no writes):
    DRY_RUN=true docker compose run --rm backend python scripts/encrypt_existing_metadata.py
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
from app.models.lead import Lead
from app.core.encryption import encrypt_metadata_fields, SENSITIVE_FIELDS


DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


async def run():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        result = await db.execute(select(Lead))
        leads = result.scalars().all()

        updated = 0
        skipped = 0
        no_sensitive = 0

        for lead in leads:
            meta = lead.lead_metadata
            if not isinstance(meta, dict):
                no_sensitive += 1
                continue

            has_sensitive = any(meta.get(f) is not None for f in SENSITIVE_FIELDS)
            if not has_sensitive:
                no_sensitive += 1
                continue

            all_encrypted = all(
                not isinstance(meta.get(f), str) or meta.get(f, "").startswith("enc:")
                for f in SENSITIVE_FIELDS
                if meta.get(f) is not None
            )
            if all_encrypted:
                skipped += 1
                continue

            new_meta = encrypt_metadata_fields(meta)
            print(f"  [ENCRYPT] lead_id={lead.id} fields={[f for f in SENSITIVE_FIELDS if meta.get(f)]}")

            if not DRY_RUN:
                lead.lead_metadata = new_meta
                updated += 1

        if not DRY_RUN:
            await db.commit()

    await engine.dispose()
    print(
        f"\nDone. Updated: {updated}, Already encrypted (skipped): {skipped}, "
        f"No sensitive data: {no_sensitive}"
    )
    if DRY_RUN:
        print("(DRY RUN — no changes written)")


if __name__ == "__main__":
    asyncio.run(run())
