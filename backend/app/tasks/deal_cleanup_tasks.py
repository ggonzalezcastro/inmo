"""
Celery tasks for Deal file lifecycle management.

cleanup_cancelled_deal_files:
  - Finds DealDocuments with storage_key set, belonging to Deals
    cancelled > 180 days ago
  - Deletes files from storage (Railway Volume)
  - Nullifies storage_key on the DB record (soft delete of file,
    keeping the audit record)
  - Runs daily via Celery Beat
"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.deal import Deal
from app.models.deal_document import DealDocument
from app.services.storage.facade import FileStorageService
from app.tasks.base import DLQTask

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(
    name="app.tasks.deal_cleanup_tasks.cleanup_cancelled_deal_files",
    base=DLQTask,
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def cleanup_cancelled_deal_files(self) -> None:
    """Delete files from storage for deals cancelled more than 180 days ago."""
    try:
        asyncio.run(_run_cleanup())
    except Exception as exc:
        logger.exception("[DealCleanup] Unexpected error: %s", exc)
        raise self.retry(exc=exc)


async def _run_cleanup() -> None:
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    total_deleted = 0
    total_nullified = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DealDocument)
            .join(Deal, DealDocument.deal_id == Deal.id)
            .where(
                and_(
                    Deal.stage == "cancelado",
                    Deal.cancelled_at < cutoff,
                    DealDocument.storage_key.isnot(None),
                )
            )
        )
        docs = result.scalars().all()

    logger.info("[DealCleanup] Found %d document(s) eligible for cleanup.", len(docs))

    batch: list[DealDocument] = []
    for doc in docs:
        key = doc.storage_key
        try:
            await FileStorageService.delete(key)
            total_deleted += 1
        except FileNotFoundError:
            logger.debug("[DealCleanup] File already gone for storage_key=%r — nullifying.", key)
        except Exception as exc:
            logger.error("[DealCleanup] Could not delete storage_key=%r: %s", key, exc)
            continue

        doc.storage_key = None
        total_nullified += 1
        batch.append(doc)

        if len(batch) >= _BATCH_SIZE:
            await _commit_batch(batch)
            batch = []

    if batch:
        await _commit_batch(batch)

    logger.info(
        "[DealCleanup] Done. Files deleted: %d, DB records nullified: %d.",
        total_deleted,
        total_nullified,
    )


async def _commit_batch(docs: list[DealDocument]) -> None:
    async with AsyncSessionLocal() as db:
        for doc in docs:
            await db.merge(doc)
        await db.commit()
    logger.debug("[DealCleanup] Committed batch of %d record(s).", len(docs))
