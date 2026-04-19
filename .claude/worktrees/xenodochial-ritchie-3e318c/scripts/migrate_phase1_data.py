#!/usr/bin/env python3
"""
One-time data migration script for Phase 1 schema changes.

Run from the backend/ directory with the virtualenv activated:
    python ../scripts/migrate_phase1_data.py

Performs three operations:
1. Migrate knowledge_base entries with source_type='property' → properties table
2. Create Conversation records for all active leads that have chat messages
3. Backfill conversation_id in existing chat_messages (best-effort)

Safe to run multiple times — uses INSERT ... ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


async def main():
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select, text, func
    from app.models.lead import Lead
    from app.models.chat_message import ChatMessage
    from app.models.conversation import Conversation

    async with AsyncSessionLocal() as db:
        logger.info("=== Phase 1 Data Migration ===")

        # ── Step 1: Migrate KB property entries ────────────────────────────
        logger.info("Step 1: Migrating knowledge_base property entries…")
        try:
            result = await db.execute(text("""
                INSERT INTO properties (
                    broker_id, name, description, status,
                    created_at, updated_at
                )
                SELECT
                    broker_id,
                    COALESCE(metadata->>'name', title, 'Propiedad sin nombre'),
                    content,
                    'active',
                    created_at,
                    COALESCE(updated_at, created_at)
                FROM knowledge_base
                WHERE source_type = 'property'
                ON CONFLICT DO NOTHING
                RETURNING id
            """))
            migrated = len(result.fetchall())
            logger.info("  Migrated %d KB property entries → properties table", migrated)
        except Exception as exc:
            logger.warning("  KB migration skipped (table may not exist yet): %s", exc)

        # ── Step 2: Create Conversation records for active leads ────────────
        logger.info("Step 2: Creating Conversation records for leads with messages…")
        try:
            # Find leads that have messages but no conversation record
            leads_with_msgs = await db.execute(text("""
                SELECT DISTINCT cm.lead_id, l.broker_id,
                    MIN(cm.created_at) AS first_msg,
                    MAX(cm.created_at) AS last_msg,
                    COUNT(*) AS msg_count,
                    MAX(cm.provider::text) AS channel
                FROM chat_messages cm
                JOIN leads l ON l.id = cm.lead_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM conversations c WHERE c.lead_id = cm.lead_id
                )
                GROUP BY cm.lead_id, l.broker_id
                LIMIT 10000
            """))
            rows = leads_with_msgs.fetchall()
            logger.info("  Found %d leads needing Conversation records", len(rows))

            created = 0
            for row in rows:
                lead_id, broker_id, first_msg, last_msg, msg_count, channel = row
                conv = Conversation(
                    lead_id=lead_id,
                    broker_id=broker_id,
                    channel=channel or "unknown",
                    status="active",
                    message_count=msg_count,
                    started_at=first_msg,
                    last_message_at=last_msg,
                )
                db.add(conv)
                created += 1

            await db.flush()  # get IDs without committing
            logger.info("  Created %d Conversation records", created)

        except Exception as exc:
            logger.error("  Conversation creation failed: %s", exc)
            await db.rollback()
            return

        # ── Step 3: Backfill conversation_id in chat_messages ──────────────
        logger.info("Step 3: Backfilling conversation_id in chat_messages…")
        try:
            result = await db.execute(text("""
                UPDATE chat_messages cm
                SET conversation_id = c.id
                FROM conversations c
                WHERE c.lead_id = cm.lead_id
                  AND cm.conversation_id IS NULL
            """))
            logger.info("  Backfilled conversation_id in %d chat_messages", result.rowcount)
        except Exception as exc:
            logger.warning("  chat_messages backfill failed (column may not exist yet): %s", exc)

        await db.commit()
        logger.info("=== Migration complete ===")


if __name__ == "__main__":
    asyncio.run(main())
