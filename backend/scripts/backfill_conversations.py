"""
One-time backfill: create Conversation records from existing ChatMessage data.

For each (lead_id, provider) pair that has messages but no Conversation record,
this script creates one Conversation and links all matching ChatMessages to it.

Idempotent — skips lead+channel combos that already have a Conversation.

Usage:
    # Dry run (no writes)
    DRY_RUN=true docker compose run --rm backend python scripts/backfill_conversations.py

    # Real run
    docker compose run --rm backend python scripts/backfill_conversations.py

    # Or locally (with DATABASE_URL set)
    python scripts/backfill_conversations.py
"""
import asyncio
import os
import sys
from datetime import timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, update as sa_update, text

from app.config import settings
from app.models.lead import Lead
from app.models.chat_message import ChatMessage
from app.models.conversation import Conversation

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

BATCH_SIZE = 200


async def backfill():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. Find all distinct (lead_id, provider) pairs from chat_messages
        pairs_result = await db.execute(
            select(
                ChatMessage.lead_id,
                ChatMessage.broker_id,
                ChatMessage.provider,
                func.min(ChatMessage.created_at).label("first_msg_at"),
                func.max(ChatMessage.created_at).label("last_msg_at"),
                func.count(ChatMessage.id).label("msg_count"),
            )
            .group_by(ChatMessage.lead_id, ChatMessage.broker_id, ChatMessage.provider)
            .order_by(ChatMessage.lead_id)
        )
        pairs = pairs_result.all()

    print(f"Found {len(pairs)} lead+channel combinations in chat_messages")
    if DRY_RUN:
        print("DRY RUN — no writes will be made")

    created = 0
    skipped = 0
    linked = 0

    async with async_session() as db:
        for row in pairs:
            lead_id = row.lead_id
            broker_id = row.broker_id
            provider_val = row.provider.value if hasattr(row.provider, "value") else str(row.provider)

            # Check if a Conversation already exists for this lead+channel
            existing = (await db.execute(
                select(Conversation).where(
                    Conversation.lead_id == lead_id,
                    Conversation.broker_id == broker_id,
                    Conversation.channel == provider_val,
                ).limit(1)
            )).scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            # Load lead to get human_mode / pipeline_stage / current_agent
            lead = (await db.execute(
                select(Lead).where(Lead.id == lead_id)
            )).scalar_one_or_none()

            if not lead:
                print(f"  WARN: lead_id={lead_id} not found, skipping")
                skipped += 1
                continue

            meta = lead.lead_metadata or {}
            current_agent = meta.get("current_agent")
            conv_state = meta.get("conversation_state")

            status = "human_mode" if lead.human_mode else "active"

            if DRY_RUN:
                print(
                    f"  [DRY] Would create Conversation lead={lead_id} channel={provider_val} "
                    f"msgs={row.msg_count} agent={current_agent} status={status}"
                )
                created += 1
                continue

            conv = Conversation(
                lead_id=lead_id,
                broker_id=broker_id,
                channel=provider_val,
                status=status,
                current_agent=current_agent,
                conversation_state=conv_state,
                human_mode=bool(lead.human_mode),
                human_assigned_to=lead.human_assigned_to,
                started_at=row.first_msg_at,
                last_message_at=row.last_msg_at,
                message_count=row.msg_count,
            )
            db.add(conv)
            await db.flush()  # get conv.id

            # Link all ChatMessages for this lead+channel to the new conversation
            result = await db.execute(
                sa_update(ChatMessage)
                .where(
                    ChatMessage.lead_id == lead_id,
                    ChatMessage.provider == row.provider,
                    ChatMessage.conversation_id.is_(None),
                )
                .values(conversation_id=conv.id)
            )
            linked += result.rowcount
            created += 1

            if created % BATCH_SIZE == 0:
                await db.commit()
                print(f"  ... committed {created} conversations so far")

        if not DRY_RUN:
            await db.commit()

    print(f"\nDone.")
    print(f"  Created : {created}")
    print(f"  Skipped : {skipped} (already existed)")
    if not DRY_RUN:
        print(f"  Linked  : {linked} chat_messages → conversation_id")


if __name__ == "__main__":
    asyncio.run(backfill())
