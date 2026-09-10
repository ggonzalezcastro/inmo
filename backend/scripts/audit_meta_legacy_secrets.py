"""Audit legacy WhatsApp secrets without printing or modifying credential values.

Usage from backend/:
    python -m scripts.audit_meta_legacy_secrets
    python -m scripts.audit_meta_legacy_secrets --require-migrated
    python -m scripts.audit_meta_legacy_secrets --require-retired
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os

from app.core.config import settings
from app.database import AsyncSessionLocal
from app.services.meta.legacy_audit import (
    LEGACY_ENVIRONMENT_VARIABLES,
    audit_legacy_secret_state,
    migration_readiness_errors,
    retirement_errors,
)


async def _run(*, require_migrated: bool, require_retired: bool) -> int:
    environment_presence = {
        key: bool(os.getenv(key)) for key in LEGACY_ENVIRONMENT_VARIABLES
    }
    async with AsyncSessionLocal() as db:
        report = await audit_legacy_secret_state(
            db,
            legacy_environment=environment_presence,
            fallback_enabled=settings.META_WHATSAPP_LEGACY_FALLBACK_ENABLED,
        )

    print(json.dumps(report.as_dict(), sort_keys=True, indent=2))
    errors = (
        retirement_errors(report)
        if require_retired
        else migration_readiness_errors(report)
        if require_migrated
        else []
    )
    if errors:
        print("Legacy Meta secret audit: FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    mode = "retired" if require_retired else "migrated" if require_migrated else "inventory"
    print(f"Legacy Meta secret audit: PASS ({mode})")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--require-migrated", action="store_true")
    group.add_argument("--require-retired", action="store_true")
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                require_migrated=args.require_migrated,
                require_retired=args.require_retired,
            )
        )
    )


if __name__ == "__main__":
    main()
