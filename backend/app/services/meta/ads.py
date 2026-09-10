"""Meta Ads drafts, approval, paused publishing, activation, and analytics."""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.websocket_manager import ws_manager
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.deal import Deal
from app.models.lead import Lead
from app.models.lead_follow_up import LeadAdvisory
from app.models.meta import MetaAsset
from app.models.meta_ads import (
    MetaAd,
    MetaAdCampaign,
    MetaAdCreative,
    MetaAdInsightDaily,
    MetaAdsPolicy,
    MetaAdSet,
    MetaLeadAttribution,
    MetaLeadForm,
    MetaSyncRun,
)
from app.models.project import Project
from app.models.property import Property
from app.models.user import UserRole
from app.schemas.meta_ads import MetaAdCampaignCreate
from app.services.meta.client import MetaGraphClient, MetaGraphError
from app.services.meta.feature_flags import MetaFeatureFlagService
from app.services.meta.resolver import MetaAssetResolutionError, MetaAssetResolver
from app.services.meta.url_safety import is_public_https_url


HOUSING_TARGETING_KEYS = {
    "geo_locations",
    "excluded_geo_locations",
    "publisher_platforms",
    "facebook_positions",
    "instagram_positions",
    "messenger_positions",
    "device_platforms",
    "locales",
    "targeting_automation",
}
UNSAFE_CREATIVE_PATTERNS = (
    r"aprobaci[oó]n\s+garantizada",
    r"cr[eé]dito\s+garantizado",
    r"sin\s+dicom",
    r"100\s*%\s+financiamiento",
)


def _require_public_https(value: Any, label: str) -> None:
    if value is None:
        return
    if not is_public_https_url(value):
        raise HTTPException(status_code=422, detail=f"{label} debe ser una URL HTTPS pública")


def _identity(current_user: dict) -> tuple[int, int, str]:
    if current_user.get("broker_id") is None:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")
    raw_uid = current_user.get("user_id") or current_user.get("id")
    try:
        uid = int(raw_uid)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Identidad de usuario inválida") from exc
    return int(current_user["broker_id"]), uid, str(current_user.get("role") or "").upper()


def _money(value: Optional[Decimal]) -> Optional[str]:
    return format(value, "f") if value is not None else None


def _campaign_query():
    return select(MetaAdCampaign).options(
        selectinload(MetaAdCampaign.ad_sets),
        selectinload(MetaAdCampaign.creatives),
        selectinload(MetaAdCampaign.ads),
    )


def _audit(db: AsyncSession, campaign: MetaAdCampaign, user_id: int, action: str, changes: dict[str, Any]) -> None:
    db.add(AuditLog(
        user_id=user_id,
        broker_id=campaign.broker_id,
        action=action,
        resource_type="meta_ad_campaign",
        resource_id=campaign.id,
        changes=changes,
    ))


class MetaAdsValidationService:
    @staticmethod
    async def validate_draft(
        db: AsyncSession,
        *,
        broker_id: int,
        payload: MetaAdCampaignCreate,
    ) -> dict[str, Any]:
        account = await db.scalar(select(MetaAsset).where(
            MetaAsset.id == payload.ad_account_asset_id,
            MetaAsset.broker_id == broker_id,
            MetaAsset.asset_type == "ad_account",
            MetaAsset.owner_type == "broker",
            MetaAsset.approval_status == "approved",
            MetaAsset.status == "active",
        ))
        if not account or "ads" not in (account.capabilities or []):
            raise HTTPException(status_code=422, detail="La cuenta publicitaria corporativa no está disponible")
        if payload.project_id is not None:
            project = await db.scalar(select(Project.id).where(
                Project.id == payload.project_id,
                Project.broker_id == broker_id,
            ))
            if project is None:
                raise HTTPException(status_code=422, detail="El proyecto no pertenece al broker")
        if payload.special_ad_category != "HOUSING":
            raise HTTPException(status_code=422, detail="Las campañas inmobiliarias deben usar la categoría Housing")
        forbidden = sorted(set(payload.ad_set.targeting) - HOUSING_TARGETING_KEYS)
        if forbidden:
            raise HTTPException(
                status_code=422,
                detail=f"Segmentación no permitida para Housing: {', '.join(forbidden)}",
            )
        geo = payload.ad_set.targeting.get("geo_locations")
        if not isinstance(geo, dict) or not geo:
            raise HTTPException(status_code=422, detail="Housing requiere una ubicación geográfica válida")

        creative_assets = [payload.creative.page_asset_id]
        if payload.creative.instagram_asset_id is not None:
            creative_assets.append(payload.creative.instagram_asset_id)
        assets = list((await db.scalars(select(MetaAsset).where(
            MetaAsset.id.in_(creative_assets),
            MetaAsset.broker_id == broker_id,
            MetaAsset.owner_type == "broker",
            MetaAsset.approval_status == "approved",
            MetaAsset.status == "active",
        ))).all())
        if len({item.id for item in assets}) != len(set(creative_assets)):
            raise HTTPException(status_code=422, detail="El anuncio solo puede usar páginas e Instagram corporativos aprobados")
        page = next((item for item in assets if item.id == payload.creative.page_asset_id), None)
        instagram = next((item for item in assets if item.id == payload.creative.instagram_asset_id), None)
        if not page or page.asset_type != "facebook_page":
            raise HTTPException(status_code=422, detail="Selecciona una página corporativa válida")
        if instagram and instagram.asset_type != "instagram_account":
            raise HTTPException(status_code=422, detail="Selecciona una cuenta Instagram corporativa válida")

        combined_copy = " ".join(filter(None, [
            payload.creative.primary_text,
            payload.creative.headline,
            payload.creative.description,
        ])).lower()
        unsafe = [pattern for pattern in UNSAFE_CREATIVE_PATTERNS if re.search(pattern, combined_copy)]
        if unsafe:
            raise HTTPException(status_code=422, detail="El texto contiene una promesa financiera no permitida")
        _require_public_https(payload.creative.destination_url, "La URL de destino")
        _require_public_https(payload.creative.media_url, "La URL de la creatividad")

        promoted = payload.ad_set.promoted_object or {}
        if payload.destination_type == "lead_form":
            form_external_id = str(promoted.get("lead_gen_form_id") or "")
            form = await db.scalar(select(MetaLeadForm).where(
                MetaLeadForm.broker_id == broker_id,
                MetaLeadForm.page_asset_id == payload.creative.page_asset_id,
                MetaLeadForm.external_id == form_external_id,
                MetaLeadForm.status == "active",
            ))
            if not form:
                raise HTTPException(status_code=422, detail="El formulario no pertenece a la página corporativa seleccionada")
        elif payload.destination_type in {"whatsapp", "instagram"}:
            key = "whatsapp_phone_number" if payload.destination_type == "whatsapp" else "instagram_actor_id"
            expected_type = "whatsapp_phone" if payload.destination_type == "whatsapp" else "instagram_account"
            destination = await db.scalar(select(MetaAsset.id).where(
                MetaAsset.broker_id == broker_id,
                MetaAsset.owner_type == "broker",
                MetaAsset.approval_status == "approved",
                MetaAsset.status == "active",
                MetaAsset.asset_type == expected_type,
                MetaAsset.external_id == str(promoted.get(key) or ""),
            ))
            if destination is None:
                raise HTTPException(status_code=422, detail="El destino publicitario no pertenece al broker")

        policy = await MetaAdsPolicyService.get_or_create(db, broker_id=broker_id)
        if payload.currency != policy.currency:
            raise HTTPException(status_code=422, detail="La moneda no coincide con la política de publicidad")
        if payload.daily_budget is not None and (
            policy.max_daily_budget <= 0 or payload.daily_budget > policy.max_daily_budget
        ):
            raise HTTPException(status_code=422, detail="El presupuesto diario supera el máximo aprobado")
        if payload.lifetime_budget is not None and (
            policy.max_lifetime_budget <= 0 or payload.lifetime_budget > policy.max_lifetime_budget
        ):
            raise HTTPException(status_code=422, detail="El presupuesto total supera el máximo aprobado")
        return {"account": account, "page": page, "instagram": instagram, "policy": policy}


class MetaAdsPolicyService:
    @staticmethod
    async def get_or_create(db: AsyncSession, *, broker_id: int) -> MetaAdsPolicy:
        policy = await db.scalar(select(MetaAdsPolicy).where(MetaAdsPolicy.broker_id == broker_id))
        if policy is None:
            policy = MetaAdsPolicy(
                broker_id=broker_id,
                currency="CLP",
                max_daily_budget=0,
                max_lifetime_budget=0,
                require_budget_increase_confirmation=True,
            )
            db.add(policy)
            await db.flush()
        return policy

    @staticmethod
    async def update(db: AsyncSession, *, payload, current_user: dict) -> MetaAdsPolicy:
        broker_id, uid, role = _identity(current_user)
        if role != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Jefatura administra los límites de gasto")
        policy = await MetaAdsPolicyService.get_or_create(db, broker_id=broker_id)
        if policy.version != payload.expected_version:
            raise HTTPException(status_code=409, detail="La política cambió; recarga antes de guardar")
        before = {
            "currency": policy.currency,
            "max_daily_budget": _money(policy.max_daily_budget),
            "max_lifetime_budget": _money(policy.max_lifetime_budget),
            "version": policy.version,
        }
        policy.currency = payload.currency
        policy.max_daily_budget = payload.max_daily_budget
        policy.max_lifetime_budget = payload.max_lifetime_budget
        policy.require_budget_increase_confirmation = payload.require_budget_increase_confirmation
        policy.updated_by_user_id = uid
        policy.version += 1
        db.add(AuditLog(
            user_id=uid,
            broker_id=broker_id,
            action="meta_ads_policy_updated",
            resource_type="meta_ads_policy",
            resource_id=policy.id,
            changes={"before": before, "after": payload.model_dump(mode="json")},
        ))
        await db.commit()
        await db.refresh(policy)
        return policy


class MetaAdsCatalogService:
    @staticmethod
    async def assets(db: AsyncSession, *, current_user: dict) -> list[MetaAsset]:
        broker_id, _, role = _identity(current_user)
        if role not in {UserRole.ADMIN.value, UserRole.AGENT.value, UserRole.SUPERADMIN.value}:
            raise HTTPException(status_code=403, detail="Permiso insuficiente")
        return list((await db.scalars(select(MetaAsset).where(
            MetaAsset.broker_id == broker_id,
            MetaAsset.owner_type == "broker",
            MetaAsset.approval_status == "approved",
            MetaAsset.status.in_(["active", "paused", "disabled", "error"]),
            MetaAsset.asset_type.in_(["ad_account", "facebook_page", "instagram_account", "whatsapp_phone", "lead_form", "pixel"]),
        ).order_by(MetaAsset.asset_type, MetaAsset.display_name))).all())


class MetaCampaignDraftService:
    @staticmethod
    async def list(db: AsyncSession, *, current_user: dict, status: Optional[str] = None) -> list[MetaAdCampaign]:
        broker_id, uid, role = _identity(current_user)
        query = _campaign_query().where(MetaAdCampaign.broker_id == broker_id)
        if role == UserRole.AGENT.value:
            query = query.where(MetaAdCampaign.created_by_user_id == uid)
        if status:
            query = query.where(MetaAdCampaign.status == status)
        return list((await db.scalars(query.order_by(MetaAdCampaign.updated_at.desc()))).unique().all())

    @staticmethod
    async def get(db: AsyncSession, *, campaign_id: int, current_user: dict, manage: bool = False) -> MetaAdCampaign:
        broker_id, uid, role = _identity(current_user)
        campaign = await db.scalar(_campaign_query().where(
            MetaAdCampaign.id == campaign_id,
            MetaAdCampaign.broker_id == broker_id,
        ))
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaña Meta no encontrada")
        if role == UserRole.AGENT.value and campaign.created_by_user_id != uid:
            raise HTTPException(status_code=404, detail="Campaña Meta no encontrada")
        if manage and role != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Jefatura debe realizar esta acción")
        return campaign

    @staticmethod
    async def create(db: AsyncSession, *, payload: MetaAdCampaignCreate, current_user: dict) -> MetaAdCampaign:
        broker_id, uid, role = _identity(current_user)
        if role not in {UserRole.ADMIN.value, UserRole.AGENT.value}:
            raise HTTPException(status_code=403, detail="Permiso insuficiente")
        await MetaFeatureFlagService.require(db, broker_id=broker_id, feature="ads")
        await MetaAdsValidationService.validate_draft(db, broker_id=broker_id, payload=payload)
        campaign = MetaAdCampaign(
            broker_id=broker_id,
            ad_account_asset_id=payload.ad_account_asset_id,
            project_id=payload.project_id,
            created_by_user_id=uid,
            operation_uuid=str(uuid.uuid4()),
            name=payload.name,
            objective=payload.objective,
            destination_type=payload.destination_type,
            special_ad_category=payload.special_ad_category,
            daily_budget=payload.daily_budget,
            lifetime_budget=payload.lifetime_budget,
            currency=payload.currency,
            status="draft",
        )
        db.add(campaign)
        await db.flush()
        ad_set = MetaAdSet(
            broker_id=broker_id,
            campaign_id=campaign.id,
            **payload.ad_set.model_dump(),
        )
        creative = MetaAdCreative(
            broker_id=broker_id,
            campaign_id=campaign.id,
            **payload.creative.model_dump(mode="json"),
            validation_result={"housing": True, "financial_claims": "checked"},
        )
        db.add_all([ad_set, creative])
        await db.flush()
        db.add(MetaAd(
            broker_id=broker_id,
            campaign_id=campaign.id,
            ad_set_id=ad_set.id,
            creative_id=creative.id,
            name=payload.creative.name,
        ))
        _audit(db, campaign, uid, "meta_ad_campaign_created", {"payload": payload.model_dump(mode="json")})
        await db.commit()
        return await MetaCampaignDraftService.get(db, campaign_id=campaign.id, current_user=current_user)

    @staticmethod
    async def update(db: AsyncSession, *, campaign_id: int, payload, current_user: dict) -> MetaAdCampaign:
        broker_id, uid, role = _identity(current_user)
        if role not in {UserRole.ADMIN.value, UserRole.AGENT.value}:
            raise HTTPException(status_code=403, detail="Permiso insuficiente")
        campaign = await MetaCampaignDraftService.get(db, campaign_id=campaign_id, current_user=current_user)
        if campaign.status not in {"draft", "rejected"}:
            raise HTTPException(status_code=409, detail="La campaña ya no admite edición")
        if role == UserRole.AGENT.value and campaign.created_by_user_id != uid:
            raise HTTPException(status_code=403, detail="Solo el creador puede editar este borrador")
        if campaign.version != payload.expected_version:
            raise HTTPException(status_code=409, detail="El borrador cambió; recarga antes de guardar")
        base = MetaAdCampaignCreate.model_validate(payload.model_dump(exclude={"expected_version"}))
        await MetaAdsValidationService.validate_draft(db, broker_id=broker_id, payload=base)
        before_version = campaign.version
        for key in ("name", "ad_account_asset_id", "project_id", "objective", "destination_type", "special_ad_category", "daily_budget", "lifetime_budget", "currency"):
            setattr(campaign, key, getattr(base, key))
        campaign.version += 1
        campaign.status = "draft"
        campaign.rejection_comment = None
        ad_set = campaign.ad_sets[0]
        creative = campaign.creatives[0]
        for key, value in base.ad_set.model_dump().items():
            setattr(ad_set, key, value)
        for key, value in base.creative.model_dump(mode="json").items():
            setattr(creative, key, value)
        campaign.ads[0].name = creative.name
        _audit(db, campaign, uid, "meta_ad_campaign_updated", {"before_version": before_version, "after_version": campaign.version})
        await db.commit()
        return await MetaCampaignDraftService.get(db, campaign_id=campaign.id, current_user=current_user)

    @staticmethod
    def snapshot(campaign: MetaAdCampaign) -> dict[str, Any]:
        return {
            "name": campaign.name,
            "ad_account_asset_id": campaign.ad_account_asset_id,
            "project_id": campaign.project_id,
            "objective": campaign.objective,
            "destination_type": campaign.destination_type,
            "special_ad_category": campaign.special_ad_category,
            "daily_budget": _money(campaign.daily_budget),
            "lifetime_budget": _money(campaign.lifetime_budget),
            "currency": campaign.currency,
            "version": campaign.version,
            "ad_set": {
                "name": campaign.ad_sets[0].name,
                "optimization_goal": campaign.ad_sets[0].optimization_goal,
                "billing_event": campaign.ad_sets[0].billing_event,
                "targeting": campaign.ad_sets[0].targeting,
                "promoted_object": campaign.ad_sets[0].promoted_object,
                "start_at": campaign.ad_sets[0].start_at.isoformat() if campaign.ad_sets[0].start_at else None,
                "end_at": campaign.ad_sets[0].end_at.isoformat() if campaign.ad_sets[0].end_at else None,
            },
            "creative": {
                "page_asset_id": campaign.creatives[0].page_asset_id,
                "instagram_asset_id": campaign.creatives[0].instagram_asset_id,
                "name": campaign.creatives[0].name,
                "primary_text": campaign.creatives[0].primary_text,
                "headline": campaign.creatives[0].headline,
                "description": campaign.creatives[0].description,
                "call_to_action": campaign.creatives[0].call_to_action,
                "destination_url": campaign.creatives[0].destination_url,
                "media_url": campaign.creatives[0].media_url,
                "media_hash": campaign.creatives[0].media_hash,
            },
        }

    @staticmethod
    async def transition(db: AsyncSession, *, campaign_id: int, action: str, payload, current_user: dict) -> MetaAdCampaign:
        _, uid, role = _identity(current_user)
        if role not in {UserRole.ADMIN.value, UserRole.AGENT.value}:
            raise HTTPException(status_code=403, detail="Permiso insuficiente")
        manage = action in {"approve", "reject"}
        campaign = await MetaCampaignDraftService.get(db, campaign_id=campaign_id, current_user=current_user, manage=manage)
        if campaign.version != payload.expected_version:
            raise HTTPException(status_code=409, detail="La campaña cambió; recarga antes de continuar")
        now = datetime.now(timezone.utc)
        if action == "submit":
            if campaign.status not in {"draft", "rejected"}:
                raise HTTPException(status_code=409, detail="Solo un borrador puede enviarse a revisión")
            campaign.status = "pending_review"
            campaign.submission_snapshot = MetaCampaignDraftService.snapshot(campaign)
            campaign.submitted_at = now
        elif action == "approve":
            if campaign.status != "pending_review":
                raise HTTPException(status_code=409, detail="La campaña no está pendiente de revisión")
            campaign.status = "approved"
            campaign.approved_by_user_id = uid
            campaign.approved_at = now
        elif action == "reject":
            if role != UserRole.ADMIN.value or campaign.status != "pending_review":
                raise HTTPException(status_code=409, detail="La campaña no está pendiente de revisión")
            if not payload.comment or not payload.comment.strip():
                raise HTTPException(status_code=422, detail="Indica el motivo del rechazo")
            campaign.status = "rejected"
            campaign.rejection_comment = payload.comment.strip()
        else:
            raise HTTPException(status_code=422, detail="Transición inválida")
        campaign.version += 1
        _audit(db, campaign, uid, f"meta_ad_campaign_{action}", {"status": campaign.status, "comment": payload.comment})
        await db.commit()
        event_name = {
            "submit": "meta_ad_campaign_submitted",
            "approve": "meta_ad_campaign_approved",
            "reject": "meta_ad_campaign_rejected",
        }[action]
        await ws_manager.broadcast(campaign.broker_id, event_name, {"campaign_id": campaign.id, "status": campaign.status})
        return await MetaCampaignDraftService.get(db, campaign_id=campaign.id, current_user=current_user)


class MetaCampaignPublisher:
    @staticmethod
    async def publish(db: AsyncSession, *, campaign_id: int, expected_version: int, current_user: dict) -> MetaAdCampaign:
        _, uid, _ = _identity(current_user)
        campaign = await MetaCampaignDraftService.get(db, campaign_id=campaign_id, current_user=current_user, manage=True)
        if campaign.version != expected_version:
            raise HTTPException(status_code=409, detail="La campaña cambió; recarga antes de publicar")
        if campaign.status not in {"approved", "partial_error"}:
            raise HTTPException(status_code=409, detail="La campaña debe estar aprobada")
        account = await db.scalar(select(MetaAsset).where(MetaAsset.id == campaign.ad_account_asset_id, MetaAsset.broker_id == campaign.broker_id))
        if not account:
            raise HTTPException(status_code=422, detail="Cuenta publicitaria no disponible")
        try:
            resolved = await MetaAssetResolver.by_external_id(
                db,
                asset_type="ad_account",
                external_id=account.external_id,
                broker_id=campaign.broker_id,
                require_capability="ads",
            )
        except MetaAssetResolutionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        graph = MetaGraphClient(access_token=resolved.access_token)
        account_path = account.external_id if account.external_id.startswith("act_") else f"act_{account.external_id}"
        campaign.status = "publishing"
        campaign.version += 1
        await db.commit()
        try:
            if not campaign.external_id:
                remote = await graph.post(f"/{account_path}/campaigns", data={
                    "name": campaign.name,
                    "objective": campaign.objective,
                    "special_ad_categories": json.dumps(["HOUSING"]),
                    "status": "PAUSED",
                })
                campaign.external_id = str(remote["id"])
                campaign.remote_status = "PAUSED"
                await db.commit()

            ad_set = campaign.ad_sets[0]
            if not ad_set.external_id:
                data: dict[str, Any] = {
                    "name": ad_set.name,
                    "campaign_id": campaign.external_id,
                    "optimization_goal": ad_set.optimization_goal,
                    "billing_event": ad_set.billing_event,
                    "targeting": json.dumps(ad_set.targeting),
                    "promoted_object": json.dumps(ad_set.promoted_object),
                    "status": "PAUSED",
                }
                if campaign.daily_budget is not None:
                    data["daily_budget"] = str(int(campaign.daily_budget))
                if campaign.lifetime_budget is not None:
                    data["lifetime_budget"] = str(int(campaign.lifetime_budget))
                if ad_set.start_at:
                    data["start_time"] = ad_set.start_at.isoformat()
                if ad_set.end_at:
                    data["end_time"] = ad_set.end_at.isoformat()
                remote = await graph.post(f"/{account_path}/adsets", data=data)
                ad_set.external_id = str(remote["id"])
                ad_set.remote_status = "PAUSED"
                await db.commit()

            creative = campaign.creatives[0]
            page = await db.scalar(select(MetaAsset).where(MetaAsset.id == creative.page_asset_id, MetaAsset.broker_id == campaign.broker_id))
            instagram = await db.scalar(select(MetaAsset).where(MetaAsset.id == creative.instagram_asset_id, MetaAsset.broker_id == campaign.broker_id)) if creative.instagram_asset_id else None
            if not page:
                raise ValueError("Página corporativa no disponible")
            if not creative.external_id:
                link_data: dict[str, Any] = {
                    "message": creative.primary_text,
                    "name": creative.headline,
                    "description": creative.description or "",
                    "call_to_action": {"type": creative.call_to_action, "value": {}},
                }
                if creative.destination_url:
                    link_data["link"] = creative.destination_url
                if creative.media_hash:
                    link_data["image_hash"] = creative.media_hash
                object_story_spec: dict[str, Any] = {"page_id": page.external_id, "link_data": link_data}
                if instagram:
                    object_story_spec["instagram_actor_id"] = instagram.external_id
                remote = await graph.post(f"/{account_path}/adcreatives", data={
                    "name": creative.name,
                    "object_story_spec": json.dumps(object_story_spec),
                })
                creative.external_id = str(remote["id"])
                await db.commit()

            ad = campaign.ads[0]
            if not ad.external_id:
                remote = await graph.post(f"/{account_path}/ads", data={
                    "name": ad.name,
                    "adset_id": ad_set.external_id,
                    "creative": json.dumps({"creative_id": creative.external_id}),
                    "status": "PAUSED",
                })
                ad.external_id = str(remote["id"])
                ad.remote_status = "PAUSED"
                await db.commit()
            campaign.status = "published_paused"
            campaign.remote_status = "PAUSED"
            campaign.published_at = datetime.now(timezone.utc)
            campaign.last_error_code = None
            campaign.last_error_detail = None
            _audit(db, campaign, uid, "meta_ad_campaign_published", {"remote_status": "PAUSED"})
            await db.commit()
            await ws_manager.broadcast(campaign.broker_id, "meta_ad_campaign_published", {"campaign_id": campaign.id, "status": campaign.status})
        except (MetaGraphError, KeyError, ValueError) as exc:
            campaign.status = "partial_error"
            campaign.last_error_code = exc.category if isinstance(exc, MetaGraphError) else type(exc).__name__
            campaign.last_error_detail = str(exc)[:1000]
            _audit(db, campaign, uid, "meta_ad_campaign_publish_failed", {"error_code": campaign.last_error_code})
            await db.commit()
            await ws_manager.broadcast(campaign.broker_id, "meta_ad_campaign_error", {"campaign_id": campaign.id, "status": campaign.status})
            raise HTTPException(status_code=502, detail="Meta rechazó una parte de la publicación; los objetos creados permanecen pausados") from exc
        return await MetaCampaignDraftService.get(db, campaign_id=campaign.id, current_user=current_user)

    @staticmethod
    async def set_delivery(db: AsyncSession, *, campaign_id: int, activate: bool, payload, current_user: dict) -> MetaAdCampaign:
        _, uid, _ = _identity(current_user)
        campaign = await MetaCampaignDraftService.get(db, campaign_id=campaign_id, current_user=current_user, manage=True)
        if campaign.version != payload.expected_version:
            raise HTTPException(status_code=409, detail="La campaña cambió; recarga antes de continuar")
        if activate and not payload.confirm_spend:
            raise HTTPException(status_code=422, detail="Debes confirmar explícitamente la activación del gasto")
        allowed = {"published_paused", "paused"} if activate else {"active"}
        if campaign.status not in allowed or not campaign.external_id:
            raise HTTPException(status_code=409, detail="Estado de campaña incompatible con esta acción")
        account = await db.scalar(select(MetaAsset).where(MetaAsset.id == campaign.ad_account_asset_id, MetaAsset.broker_id == campaign.broker_id))
        if not account:
            raise HTTPException(status_code=422, detail="Cuenta publicitaria no disponible")
        try:
            resolved = await MetaAssetResolver.by_external_id(
                db,
                asset_type="ad_account",
                external_id=account.external_id,
                broker_id=campaign.broker_id,
                require_capability="ads",
            )
        except MetaAssetResolutionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        remote_status = "ACTIVE" if activate else "PAUSED"
        await MetaGraphClient(access_token=resolved.access_token).post(f"/{campaign.external_id}", data={"status": remote_status})
        now = datetime.now(timezone.utc)
        campaign.status = "active" if activate else "paused"
        campaign.remote_status = remote_status
        campaign.version += 1
        if activate:
            campaign.activated_at = now
        else:
            campaign.paused_at = now
        _audit(db, campaign, uid, "meta_ad_campaign_activated" if activate else "meta_ad_campaign_paused", {"remote_status": remote_status})
        await db.commit()
        await ws_manager.broadcast(campaign.broker_id, "meta_ad_campaign_activated" if activate else "meta_ad_campaign_paused", {"campaign_id": campaign.id, "status": campaign.status})
        return await MetaCampaignDraftService.get(db, campaign_id=campaign.id, current_user=current_user)


def _cost(spend: Decimal, count: int) -> Optional[Decimal]:
    return (spend / Decimal(count)).quantize(Decimal("0.01")) if count else None


class MetaAdsAnalyticsService:
    @staticmethod
    async def summary(
        db: AsyncSession,
        *,
        current_user: dict,
        date_from: date,
        date_to: date,
        account_external_id: Optional[str] = None,
        campaign_external_id: Optional[str] = None,
        project_id: Optional[int] = None,
        executive_id: Optional[int] = None,
    ) -> dict[str, Any]:
        broker_id, uid, role = _identity(current_user)
        if role == UserRole.AGENT.value:
            executive_id = uid
        scoped_campaign_ids: Optional[list[str]] = None
        if role == UserRole.AGENT.value:
            scoped_campaign_ids = list((await db.scalars(select(MetaAdCampaign.external_id).where(
                MetaAdCampaign.broker_id == broker_id,
                MetaAdCampaign.created_by_user_id == uid,
                MetaAdCampaign.external_id.isnot(None),
            ))).all())
            if campaign_external_id and campaign_external_id not in scoped_campaign_ids:
                raise HTTPException(status_code=404, detail="Campaña Meta no encontrada")
        elif (project_id or executive_id) and not campaign_external_id:
            campaign_scope = select(distinct(MetaLeadAttribution.campaign_external_id)).where(
                MetaLeadAttribution.broker_id == broker_id,
                MetaLeadAttribution.campaign_external_id.isnot(None),
            )
            if project_id:
                campaign_scope = campaign_scope.where(MetaLeadAttribution.project_id == project_id)
            if executive_id:
                campaign_scope = campaign_scope.join(Lead, Lead.id == MetaLeadAttribution.lead_id).where(
                    Lead.broker_id == broker_id,
                    Lead.assigned_to == executive_id,
                )
            scoped_campaign_ids = list((await db.scalars(campaign_scope)).all())
        insight_filters = [
            MetaAdInsightDaily.broker_id == broker_id,
            MetaAdInsightDaily.insight_date >= date_from,
            MetaAdInsightDaily.insight_date <= date_to,
        ]
        if account_external_id:
            insight_filters.append(MetaAdInsightDaily.account_external_id == account_external_id)
        if campaign_external_id:
            insight_filters.append(MetaAdInsightDaily.campaign_external_id == campaign_external_id)
        elif scoped_campaign_ids is not None:
            insight_filters.append(MetaAdInsightDaily.campaign_external_id.in_(scoped_campaign_ids))
        totals = (await db.execute(select(
            func.coalesce(func.sum(MetaAdInsightDaily.spend), 0),
            func.coalesce(func.sum(MetaAdInsightDaily.impressions), 0),
            func.coalesce(func.sum(MetaAdInsightDaily.reach), 0),
            func.coalesce(func.sum(MetaAdInsightDaily.clicks), 0),
            func.coalesce(func.sum(MetaAdInsightDaily.conversations), 0),
            func.coalesce(func.sum(MetaAdInsightDaily.leads), 0),
        ).where(*insight_filters))).one()
        spend = Decimal(totals[0] or 0)
        trend_rows = (await db.execute(select(
            MetaAdInsightDaily.insight_date,
            func.coalesce(func.sum(MetaAdInsightDaily.spend), 0),
            func.coalesce(func.sum(MetaAdInsightDaily.leads), 0),
            func.coalesce(func.sum(MetaAdInsightDaily.conversations), 0),
        ).where(*insight_filters).group_by(MetaAdInsightDaily.insight_date).order_by(MetaAdInsightDaily.insight_date))).all()

        attr_filters = [MetaLeadAttribution.broker_id == broker_id, MetaLeadAttribution.touch_type == "last"]
        if campaign_external_id:
            attr_filters.append(MetaLeadAttribution.campaign_external_id == campaign_external_id)
        elif scoped_campaign_ids is not None:
            attr_filters.append(MetaLeadAttribution.campaign_external_id.in_(scoped_campaign_ids))
        if project_id:
            attr_filters.append(MetaLeadAttribution.project_id == project_id)
        lead_query = select(distinct(MetaLeadAttribution.lead_id)).where(*attr_filters)
        if executive_id:
            lead_query = lead_query.join(Lead, Lead.id == MetaLeadAttribution.lead_id).where(Lead.assigned_to == executive_id)
        lead_ids = list((await db.scalars(lead_query)).all())
        crm_leads = len(lead_ids)
        advised = meetings = reservations = sales = 0
        sales_uf = Decimal(0)
        sales_clp = Decimal(0)
        if lead_ids:
            advised = int(await db.scalar(select(func.count(distinct(LeadAdvisory.lead_id))).where(LeadAdvisory.broker_id == broker_id, LeadAdvisory.lead_id.in_(lead_ids))) or 0)
            meetings = int(await db.scalar(select(func.count(distinct(Appointment.lead_id))).where(Appointment.lead_id.in_(lead_ids), Appointment.status.in_(["completed", "confirmed"]))) or 0)
            reservations = int(await db.scalar(select(func.count(distinct(Deal.lead_id))).where(Deal.broker_id == broker_id, Deal.lead_id.in_(lead_ids), Deal.reserva_at.isnot(None))) or 0)
            sale_row = (await db.execute(select(
                func.count(distinct(Deal.lead_id)),
                func.coalesce(func.sum(func.coalesce(Property.offer_price_uf, Property.list_price_uf, Property.price_uf, 0)), 0),
                func.coalesce(func.sum(func.coalesce(Property.offer_price_clp, Property.list_price_clp, Property.price_clp, 0)), 0),
            ).select_from(Deal).join(Property, Property.id == Deal.property_id).where(
                Deal.broker_id == broker_id,
                Deal.lead_id.in_(lead_ids),
                Deal.stage == "escritura_firmada",
            ))).one()
            sales, sales_uf, sales_clp = int(sale_row[0] or 0), Decimal(sale_row[1] or 0), Decimal(sale_row[2] or 0)
        campaign_rows = (await db.execute(select(
            MetaAdInsightDaily.campaign_external_id,
            func.coalesce(func.sum(MetaAdInsightDaily.spend), 0).label("spend"),
            func.coalesce(func.sum(MetaAdInsightDaily.impressions), 0).label("impressions"),
            func.coalesce(func.sum(MetaAdInsightDaily.clicks), 0).label("clicks"),
            func.coalesce(func.sum(MetaAdInsightDaily.leads), 0).label("leads"),
        ).where(*insight_filters).group_by(MetaAdInsightDaily.campaign_external_id).order_by(func.sum(MetaAdInsightDaily.spend).desc()))).all()
        freshness = await db.scalar(select(func.max(MetaAdInsightDaily.updated_at)).where(MetaAdInsightDaily.broker_id == broker_id))
        failed_sync = await db.scalar(select(MetaSyncRun.id).where(MetaSyncRun.broker_id == broker_id, MetaSyncRun.sync_type == "insights", MetaSyncRun.status == "failed").order_by(MetaSyncRun.started_at.desc()).limit(1))
        return {
            "kpis": {
                "spend": spend,
                "impressions": int(totals[1] or 0),
                "reach": int(totals[2] or 0),
                "clicks": int(totals[3] or 0),
                "conversations": int(totals[4] or 0),
                "meta_leads": int(totals[5] or 0),
                "crm_leads": crm_leads,
                "advised": advised,
                "meetings": meetings,
                "reservations": reservations,
                "sales": sales,
                "sales_uf": sales_uf,
                "sales_clp": sales_clp,
                "cost_per_conversation": _cost(spend, int(totals[4] or 0)),
                "cost_per_lead": _cost(spend, crm_leads),
                "cost_per_advised": _cost(spend, advised),
                "cost_per_meeting": _cost(spend, meetings),
                "cost_per_reservation": _cost(spend, reservations),
                "cost_per_sale": _cost(spend, sales),
            },
            "trend": [{"date": row[0], "spend": row[1], "leads": int(row[2]), "conversations": int(row[3])} for row in trend_rows],
            "campaigns": [{"campaign_external_id": row[0], "spend": row[1], "impressions": int(row[2]), "clicks": int(row[3]), "leads": int(row[4])} for row in campaign_rows if row[0]],
            "freshness_at": freshness,
            "partial_sync": bool(failed_sync),
        }
