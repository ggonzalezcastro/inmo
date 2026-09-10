"""Backfill legacy WhatsApp configuration into the Meta asset model.

Usage from backend/:
    python scripts/backfill_meta_whatsapp.py --dry-run
    python scripts/backfill_meta_whatsapp.py --apply
    python scripts/backfill_meta_whatsapp.py --apply --broker-id 12
"""

from __future__ import annotations

import argparse
import asyncio
import json

from app.database import AsyncSessionLocal
from app.services.meta.legacy_migration import LegacyWhatsAppMigrationService


async def _run(*, dry_run: bool, broker_id: int | None) -> None:
    async with AsyncSessionLocal() as db:
        report = await LegacyWhatsAppMigrationService.run(
            db,
            dry_run=dry_run,
            broker_id=broker_id,
        )
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--broker-id", type=int)
    args = parser.parse_args()
    asyncio.run(_run(dry_run=not args.apply, broker_id=args.broker_id))


if __name__ == "__main__":
    main()
