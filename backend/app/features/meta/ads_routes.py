"""APIs for Meta advertising, separate from internal CRM campaigns."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.lead import Lead
from app.models.lead_follow_up import LeadAdvisory
from app.models.appointment import Appointment
from app.models.deal import Deal
from app.models.meta_ads import MetaConversionEvent, MetaLeadAttribution
from app.models.project import Project
from app.schemas.meta import MetaAssetResponse
from app.schemas.meta_ads import (
    MetaAdCampaignCreate,
    MetaAdCampaignResponse,
    MetaAdCampaignUpdate,
    MetaAdsAnalyticsResponse,
    MetaAdsPolicyResponse,
    MetaAdsPolicyUpdate,
    MetaCampaignActivation,
    MetaCampaignTransition,
    MetaLeadFormResponse,
    MetaLeadFormPreviewRequest,
    MetaLeadFormPreviewResponse,
    MetaLeadFormUpdate,
)
from app.services.meta.ads import (
    MetaAdsAnalyticsService,
    MetaAdsCatalogService,
    MetaAdsPolicyService,
    MetaCampaignDraftService,
    MetaCampaignPublisher,
    _identity,
)
from app.services.meta.feature_flags import MetaFeatureFlagService
from app.services.meta.lead_ads import MetaLeadFormService
from app.tasks.meta_tasks import reconcile_meta_lead_forms, synchronize_meta_ads_insights


router = APIRouter()


async def _ads_enabled(db: AsyncSession, current_user: dict) -> tuple[int, int, str]:
    broker_id, uid, role = _identity(current_user)
    await MetaFeatureFlagService.require(db, broker_id=broker_id, feature="ads")
    return broker_id, uid, role


@router.get("/ads/catalog/assets", response_model=list[MetaAssetResponse])
async def ads_asset_catalog(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await _ads_enabled(db, current_user)
    return await MetaAdsCatalogService.assets(db, current_user=current_user)


@router.get("/ads/catalog/projects")
async def ads_project_catalog(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    broker_id, _, _ = await _ads_enabled(db, current_user)
    projects = list((await db.scalars(
        select(Project)
        .where(Project.broker_id == broker_id)
        .order_by(Project.name.asc())
    )).all())
    return [{"id": project.id, "name": project.name, "status": project.status} for project in projects]


@router.get("/ads/policy", response_model=MetaAdsPolicyResponse)
async def get_ads_policy(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    broker_id, _, _ = await _ads_enabled(db, current_user)
    policy = await MetaAdsPolicyService.get_or_create(db, broker_id=broker_id)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.patch("/ads/policy", response_model=MetaAdsPolicyResponse)
async def update_ads_policy(body: MetaAdsPolicyUpdate, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await _ads_enabled(db, current_user)
    return await MetaAdsPolicyService.update(db, payload=body, current_user=current_user)


@router.get("/ads/campaigns", response_model=list[MetaAdCampaignResponse])
async def list_meta_ad_campaigns(status: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await _ads_enabled(db, current_user)
    return await MetaCampaignDraftService.list(db, current_user=current_user, status=status)


@router.post("/ads/campaigns", response_model=MetaAdCampaignResponse, status_code=201)
async def create_meta_ad_campaign(body: MetaAdCampaignCreate, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await _ads_enabled(db, current_user)
    return await MetaCampaignDraftService.create(db, payload=body, current_user=current_user)


@router.get("/ads/campaigns/{campaign_id}", response_model=MetaAdCampaignResponse)
async def get_meta_ad_campaign(campaign_id: int, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await _ads_enabled(db, current_user)
    return await MetaCampaignDraftService.get(db, campaign_id=campaign_id, current_user=current_user)


@router.put("/ads/campaigns/{campaign_id}", response_model=MetaAdCampaignResponse)
async def update_meta_ad_campaign(campaign_id: int, body: MetaAdCampaignUpdate, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await _ads_enabled(db, current_user)
    return await MetaCampaignDraftService.update(db, campaign_id=campaign_id, payload=body, current_user=current_user)


async def _transition(campaign_id: int, action: str, body: MetaCampaignTransition, db: AsyncSession, current_user: dict):
    await _ads_enabled(db, current_user)
    return await MetaCampaignDraftService.transition(db, campaign_id=campaign_id, action=action, payload=body, current_user=current_user)


@router.post("/ads/campaigns/{campaign_id}/submit", response_model=MetaAdCampaignResponse)
async def submit_meta_ad_campaign(campaign_id: int, body: MetaCampaignTransition, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return await _transition(campaign_id, "submit", body, db, current_user)


@router.post("/ads/campaigns/{campaign_id}/approve", response_model=MetaAdCampaignResponse)
async def approve_meta_ad_campaign(campaign_id: int, body: MetaCampaignTransition, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return await _transition(campaign_id, "approve", body, db, current_user)


@router.post("/ads/campaigns/{campaign_id}/reject", response_model=MetaAdCampaignResponse)
async def reject_meta_ad_campaign(campaign_id: int, body: MetaCampaignTransition, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return await _transition(campaign_id, "reject", body, db, current_user)


@router.post("/ads/campaigns/{campaign_id}/publish", response_model=MetaAdCampaignResponse)
async def publish_meta_ad_campaign(campaign_id: int, body: MetaCampaignTransition, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await _ads_enabled(db, current_user)
    return await MetaCampaignPublisher.publish(db, campaign_id=campaign_id, expected_version=body.expected_version, current_user=current_user)


@router.post("/ads/campaigns/{campaign_id}/activate", response_model=MetaAdCampaignResponse)
async def activate_meta_ad_campaign(campaign_id: int, body: MetaCampaignActivation, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await _ads_enabled(db, current_user)
    return await MetaCampaignPublisher.set_delivery(db, campaign_id=campaign_id, activate=True, payload=body, current_user=current_user)


@router.post("/ads/campaigns/{campaign_id}/pause", response_model=MetaAdCampaignResponse)
async def pause_meta_ad_campaign(campaign_id: int, body: MetaCampaignActivation, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    await _ads_enabled(db, current_user)
    return await MetaCampaignPublisher.set_delivery(db, campaign_id=campaign_id, activate=False, payload=body, current_user=current_user)


@router.get("/ads/forms", response_model=list[MetaLeadFormResponse])
async def list_meta_lead_forms(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    broker_id, _, _ = await _ads_enabled(db, current_user)
    return await MetaLeadFormService.list(db, broker_id=broker_id)


@router.patch("/ads/forms/{form_id}", response_model=MetaLeadFormResponse)
async def update_meta_lead_form(form_id: int, body: MetaLeadFormUpdate, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    broker_id, _, role = await _ads_enabled(db, current_user)
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Jefatura configura los formularios")
    return await MetaLeadFormService.update_mapping(db, broker_id=broker_id, form_id=form_id, project_id=body.project_id, field_mapping=body.field_mapping)


@router.post("/ads/forms/{form_id}/preview", response_model=MetaLeadFormPreviewResponse)
async def preview_meta_lead_form(form_id: int, body: MetaLeadFormPreviewRequest, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    broker_id, _, role = await _ads_enabled(db, current_user)
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Jefatura configura los formularios")
    return await MetaLeadFormService.preview_mapping(
        db,
        broker_id=broker_id,
        form_id=form_id,
        project_id=body.project_id,
        field_mapping=body.field_mapping,
        sample_values=body.sample_values,
    )


@router.post("/ads/forms/sync")
async def sync_meta_lead_forms(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _, _, role = await _ads_enabled(db, current_user)
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Jefatura debe iniciar la sincronización")
    reconcile_meta_lead_forms.delay()
    return {"ok": True, "queued": True}


@router.post("/ads/insights/sync")
async def sync_meta_ads_insights(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _, _, role = await _ads_enabled(db, current_user)
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Jefatura debe iniciar la sincronización")
    synchronize_meta_ads_insights.delay(3)
    return {"ok": True, "queued": True}


@router.get("/ads/analytics", response_model=MetaAdsAnalyticsResponse)
async def meta_ads_analytics(
    date_from: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    date_to: date = Query(default_factory=date.today),
    account_external_id: Optional[str] = None,
    campaign_external_id: Optional[str] = None,
    project_id: Optional[int] = None,
    executive_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _ads_enabled(db, current_user)
    if date_to < date_from or (date_to - date_from).days > 730:
        raise HTTPException(status_code=422, detail="Período inválido")
    return await MetaAdsAnalyticsService.summary(db, current_user=current_user, date_from=date_from, date_to=date_to, account_external_id=account_external_id, campaign_external_id=campaign_external_id, project_id=project_id, executive_id=executive_id)


@router.get("/ads/analytics/leads")
async def meta_ads_analytics_leads(
    campaign_external_id: Optional[str] = None,
    project_id: Optional[int] = None,
    executive_id: Optional[int] = None,
    outcome: str = Query("lead", pattern="^(lead|advised|meeting|reservation|sale)$"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    broker_id, uid, role = await _ads_enabled(db, current_user)
    if role == "AGENT":
        executive_id = uid
    query = select(Lead).join(MetaLeadAttribution, MetaLeadAttribution.lead_id == Lead.id).where(Lead.broker_id == broker_id, MetaLeadAttribution.broker_id == broker_id, MetaLeadAttribution.touch_type == "last")
    if campaign_external_id:
        query = query.where(MetaLeadAttribution.campaign_external_id == campaign_external_id)
    if project_id:
        query = query.where(MetaLeadAttribution.project_id == project_id)
    if executive_id:
        query = query.where(Lead.assigned_to == executive_id)
    if date_from:
        query = query.where(MetaLeadAttribution.captured_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        query = query.where(MetaLeadAttribution.captured_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    if outcome == "advised":
        query = query.where(exists(select(LeadAdvisory.id).where(
            LeadAdvisory.broker_id == broker_id,
            LeadAdvisory.lead_id == Lead.id,
        )))
    elif outcome == "meeting":
        query = query.where(exists(select(Appointment.id).where(
            Appointment.lead_id == Lead.id,
            Appointment.status.in_(["completed", "confirmed"]),
        )))
    elif outcome == "reservation":
        query = query.where(exists(select(Deal.id).where(
            Deal.broker_id == broker_id,
            Deal.lead_id == Lead.id,
            Deal.reserva_at.isnot(None),
        )))
    elif outcome == "sale":
        query = query.where(exists(select(Deal.id).where(
            Deal.broker_id == broker_id,
            Deal.lead_id == Lead.id,
            Deal.stage == "escritura_firmada",
        )))
    unique_query = query.distinct()
    total = int(await db.scalar(select(func.count()).select_from(unique_query.subquery())) or 0)
    rows = list((await db.scalars(unique_query.order_by(Lead.created_at.desc()).offset(offset).limit(limit))).all())
    return {"items": [{"id": lead.id, "name": lead.name, "phone": lead.phone, "pipeline_stage": lead.pipeline_stage, "assigned_to": lead.assigned_to} for lead in rows], "total": total, "offset": offset, "limit": limit}


@router.get("/ads/conversions/diagnostics")
async def meta_conversion_diagnostics(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    broker_id, _, role = await _ads_enabled(db, current_user)
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Jefatura consulta los diagnósticos de conversiones")
    rows = list((await db.scalars(
        select(MetaConversionEvent)
        .where(MetaConversionEvent.broker_id == broker_id)
        .order_by(MetaConversionEvent.created_at.desc())
        .limit(limit)
    )).all())
    return [{
        "id": row.id,
        "event_name": row.event_name,
        "status": row.status,
        "last_error_code": row.last_error_code,
        "sent_at": row.sent_at,
        "created_at": row.created_at,
    } for row in rows]
