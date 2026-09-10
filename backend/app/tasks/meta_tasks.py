"""Celery processing and maintenance tasks for the Meta webhook inbox."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, update

from app.tasks.base import DLQTask


@shared_task(
    name="app.tasks.meta_tasks.process_meta_webhook_event",
    base=DLQTask,
    bind=True,
    max_retries=3,
)
def process_meta_webhook_event(self, event_id: int):
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.config import settings
        from app.core.meta_encryption import decrypt_meta_json
        from app.models.meta import MetaWebhookEvent
        from app.services.meta.inbound import MetaInboundMessageService, MetaMessageStatusService
        from app.services.meta.normalization import (
            NormalizedLeadgen,
            NormalizedMetaMessage,
            NormalizedMetaStatus,
            normalize_meta_payload,
        )

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as db:
                event = await db.scalar(
                    select(MetaWebhookEvent).where(MetaWebhookEvent.id == event_id)
                )
                if not event or event.status in {"processed", "ignored"}:
                    return
                event.status = "processing"
                event.attempt_count = (event.attempt_count or 0) + 1
                await db.commit()
                try:
                    payload = decrypt_meta_json(event.payload_ciphertext)
                    normalized = normalize_meta_payload(payload)
                    handled = False
                    for item in normalized:
                        if isinstance(item, NormalizedMetaMessage):
                            await MetaInboundMessageService.process(db, item)
                            handled = True
                        elif isinstance(item, NormalizedMetaStatus):
                            await MetaMessageStatusService.process(db, item)
                            handled = True
                        elif isinstance(item, NormalizedLeadgen):
                            from app.services.meta.lead_ads import MetaLeadgenService

                            lead = await MetaLeadgenService.process(db, item)
                            handled = handled or lead is not None
                    event = await db.scalar(
                        select(MetaWebhookEvent).where(MetaWebhookEvent.id == event_id)
                    )
                    event.status = "processed" if handled else "ignored"
                    event.processed_at = datetime.now(timezone.utc)
                    event.last_error = None
                    await db.commit()
                except Exception as exc:
                    await db.rollback()
                    event = await db.scalar(
                        select(MetaWebhookEvent).where(MetaWebhookEvent.id == event_id)
                    )
                    if event:
                        event.status = "failed"
                        event.last_error = f"{type(exc).__name__}: {str(exc)[:1000]}"
                        await db.commit()
                    raise
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(300, 2 ** (self.request.retries + 1) * 15))


@shared_task(
    name="app.tasks.meta_tasks.cleanup_expired_meta_webhook_payloads",
    base=DLQTask,
)
def cleanup_expired_meta_webhook_payloads():
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.config import settings
        from app.models.meta import MetaWebhookEvent

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as db:
                result = await db.execute(
                    update(MetaWebhookEvent)
                    .where(
                        MetaWebhookEvent.payload_expires_at < datetime.now(timezone.utc),
                        MetaWebhookEvent.payload_ciphertext.isnot(None),
                    )
                    .values(payload_ciphertext=None)
                )
                await db.commit()
                return result.rowcount or 0
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@shared_task(
    name="app.tasks.meta_tasks.revalidate_meta_connections",
    base=DLQTask,
)
def revalidate_meta_connections():
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.config import settings
        from app.services.meta.health import MetaConnectionHealthService

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        checked = 0
        failed = 0
        try:
            async with session_factory() as db:
                connection_ids = await MetaConnectionHealthService.connection_ids_for_maintenance(db)
            for connection_id in connection_ids:
                async with session_factory() as db:
                    try:
                        await MetaConnectionHealthService.revalidate(
                            db,
                            connection_id=connection_id,
                        )
                        checked += 1
                    except Exception:
                        failed += 1
            return {"checked": checked, "failed": failed}
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@shared_task(
    name="app.tasks.meta_tasks.synchronize_meta_assets",
    base=DLQTask,
)
def synchronize_meta_assets():
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.config import settings
        from app.services.meta.health import MetaConnectionHealthService

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        synced = 0
        failed = 0
        try:
            async with session_factory() as db:
                connection_ids = await MetaConnectionHealthService.connection_ids_for_maintenance(db)
            for connection_id in connection_ids:
                async with session_factory() as db:
                    try:
                        synced += await MetaConnectionHealthService.sync_assets(
                            db,
                            connection_id=connection_id,
                        )
                    except Exception:
                        failed += 1
            return {"assets_synced": synced, "connections_failed": failed}
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@shared_task(
    name="app.tasks.meta_tasks.synchronize_meta_ads_insights",
    base=DLQTask,
)
def synchronize_meta_ads_insights(backfill_days: int = 1):
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.config import settings
        from app.services.meta.ads_sync import MetaAdsSyncService

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as db:
                return await MetaAdsSyncService.sync_all_insights(
                    db,
                    backfill_days=max(0, min(int(backfill_days), 90)),
                )
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@shared_task(
    name="app.tasks.meta_tasks.reconcile_meta_lead_forms",
    base=DLQTask,
)
def reconcile_meta_lead_forms():
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.config import settings
        from app.services.meta.ads_sync import MetaAdsSyncService

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as db:
                return await MetaAdsSyncService.reconcile_lead_forms(db)
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@shared_task(
    name="app.tasks.meta_tasks.send_meta_purchase_conversion",
    base=DLQTask,
    bind=True,
    max_retries=3,
)
def send_meta_purchase_conversion(self, deal_id: int):
    async def _run():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.core.config import settings
        from app.services.meta.conversions import MetaConversionsService

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_factory() as db:
                return await MetaConversionsService.send_purchase_for_deal(db, deal_id=deal_id)
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(900, 30 * 2 ** self.request.retries))
