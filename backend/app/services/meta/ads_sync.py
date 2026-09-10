"""Idempotent periodic synchronization for Meta forms, leads, and Ads insights."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta import MetaAsset
from app.models.meta_ads import MetaAdInsightDaily, MetaLeadForm, MetaSyncRun
from app.services.meta.client import MetaGraphClient
from app.services.meta.feature_flags import MetaFeatureFlagService
from app.services.meta.lead_ads import MetaLeadFormService, MetaLeadgenService
from app.services.meta.normalization import NormalizedLeadgen
from app.services.meta.resolver import MetaAssetResolver


def _action_count(actions: list[dict[str, Any]], names: set[str]) -> int:
    total = Decimal(0)
    for item in actions:
        if str(item.get("action_type") or "") in names:
            try:
                total += Decimal(str(item.get("value") or 0))
            except Exception:
                continue
    return int(total)


class MetaAdsSyncService:
    @staticmethod
    async def sync_insights_for_account(
        db: AsyncSession,
        *,
        account: MetaAsset,
        since: date,
        until: date,
    ) -> int:
        run = MetaSyncRun(
            broker_id=account.broker_id,
            sync_type="insights",
            status="running",
            checkpoint={"account_asset_id": account.id, "since": since.isoformat(), "until": until.isoformat()},
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.commit()
        count = 0
        try:
            resolved = await MetaAssetResolver.by_external_id(
                db,
                asset_type="ad_account",
                external_id=account.external_id,
                broker_id=account.broker_id,
                require_capability="ads",
            )
            graph = MetaGraphClient(access_token=resolved.access_token)
            account_path = account.external_id if account.external_id.startswith("act_") else f"act_{account.external_id}"
            async for row in graph.iterate(f"/{account_path}/insights", params={
                "fields": "date_start,date_stop,account_id,campaign_id,adset_id,ad_id,spend,impressions,reach,frequency,clicks,actions",
                "level": "ad",
                "time_increment": 1,
                "time_range": json.dumps({"since": since.isoformat(), "until": until.isoformat()}),
                "limit": 500,
            }):
                actions = row.get("actions") or []
                values = {
                    "broker_id": account.broker_id,
                    "insight_date": date.fromisoformat(row["date_start"]),
                    "account_external_id": str(row.get("account_id") or account.external_id).removeprefix("act_"),
                    "campaign_external_id": str(row.get("campaign_id") or ""),
                    "ad_set_external_id": str(row.get("adset_id") or ""),
                    "ad_external_id": str(row.get("ad_id") or ""),
                    "spend": Decimal(str(row.get("spend") or 0)),
                    "impressions": int(row.get("impressions") or 0),
                    "reach": int(row.get("reach") or 0),
                    "frequency": Decimal(str(row.get("frequency") or 0)),
                    "clicks": int(row.get("clicks") or 0),
                    "conversations": _action_count(actions, {"onsite_conversion.messaging_conversation_started_7d", "messaging_conversation_started_7d"}),
                    "leads": _action_count(actions, {"lead", "onsite_conversion.lead_grouped"}),
                    "raw_actions": actions,
                }
                statement = insert(MetaAdInsightDaily).values(**values).on_conflict_do_update(
                    constraint="uq_meta_ad_insight_grain",
                    set_={key: value for key, value in values.items() if key not in {"broker_id", "insight_date", "account_external_id", "campaign_external_id", "ad_set_external_id", "ad_external_id"}},
                )
                await db.execute(statement)
                count += 1
            run.status = "completed"
            run.result = {"rows": count}
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return count
        except Exception as exc:
            await db.rollback()
            run = await db.scalar(select(MetaSyncRun).where(MetaSyncRun.id == run.id))
            if run:
                run.status = "failed"
                run.error_code = type(exc).__name__
                run.error_detail = str(exc)[:1000]
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
            raise

    @staticmethod
    async def sync_all_insights(db: AsyncSession, *, backfill_days: int = 1) -> dict[str, int]:
        today = datetime.now(timezone.utc).date()
        accounts = list((await db.scalars(select(MetaAsset).where(
            MetaAsset.asset_type == "ad_account",
            MetaAsset.owner_type == "broker",
            MetaAsset.approval_status == "approved",
            MetaAsset.status == "active",
        ))).all())
        synced = failed = 0
        for account in accounts:
            flags = await MetaFeatureFlagService.effective(db, account.broker_id)
            if not flags["channels"].get("ads", False):
                continue
            try:
                synced += await MetaAdsSyncService.sync_insights_for_account(
                    db,
                    account=account,
                    since=today - timedelta(days=max(0, backfill_days)),
                    until=today,
                )
            except Exception:
                failed += 1
        return {"rows": synced, "failed_accounts": failed}

    @staticmethod
    async def reconcile_lead_forms(db: AsyncSession) -> dict[str, int]:
        pages = list((await db.scalars(select(MetaAsset).where(
            MetaAsset.asset_type == "facebook_page",
            MetaAsset.owner_type == "broker",
            MetaAsset.approval_status == "approved",
            MetaAsset.status == "active",
        ))).all())
        forms_synced = leads_seen = failed_pages = 0
        for page in pages:
            flags = await MetaFeatureFlagService.effective(db, page.broker_id)
            if not flags["channels"].get("lead_ads", False):
                continue
            try:
                forms_synced += await MetaLeadFormService.sync_page(db, page_asset=page)
                resolved = await MetaAssetResolver.by_external_id(
                    db,
                    asset_type="facebook_page",
                    external_id=page.external_id,
                    broker_id=page.broker_id,
                )
                graph = MetaGraphClient(access_token=resolved.access_token)
                forms = list((await db.scalars(select(MetaLeadForm).where(
                    MetaLeadForm.broker_id == page.broker_id,
                    MetaLeadForm.page_asset_id == page.id,
                    MetaLeadForm.status == "active",
                ))).all())
                for form in forms:
                    async for remote in graph.iterate(f"/{form.external_id}/leads", params={"fields": "id,ad_id,adset_id,form_id", "limit": 100}):
                        leadgen_id = str(remote.get("id") or "")
                        if not leadgen_id:
                            continue
                        await MetaLeadgenService.process(db, NormalizedLeadgen(
                            asset_external_id=page.external_id,
                            leadgen_id=leadgen_id,
                            form_id=str(remote.get("form_id") or form.external_id),
                            ad_id=str(remote.get("ad_id")) if remote.get("ad_id") else None,
                            adgroup_id=str(remote.get("adset_id")) if remote.get("adset_id") else None,
                            metadata={"source": "reconciliation"},
                        ))
                        leads_seen += 1
            except Exception:
                failed_pages += 1
        return {"forms": forms_synced, "leads_seen": leads_seen, "failed_pages": failed_pages}
