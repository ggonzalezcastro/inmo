"""Lead Ads form sync, idempotent ingestion, and first/last attribution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.conversation import Conversation
from app.models.lead import Lead, LeadStatus
from app.models.meta import ChannelIdentity, MetaAsset
from app.models.meta_ads import MetaLeadAttribution, MetaLeadForm
from app.services.leads.assignment_service import LeadAssignmentService
from app.services.leads.lead_service import LeadService
from app.services.meta.client import MetaGraphClient
from app.services.meta.feature_flags import MetaFeatureFlagService
from app.services.meta.normalization import NormalizedLeadgen
from app.services.meta.resolver import MetaAssetResolver


STANDARD_FIELD_MAP = {
    "full_name": "name",
    "name": "name",
    "first_name": "first_name",
    "last_name": "last_name",
    "phone_number": "phone",
    "phone": "phone",
    "email": "email",
}

ALLOWED_LEAD_FIELD_TARGETS = {
    "name",
    "first_name",
    "last_name",
    "phone",
    "email",
    "budget",
    "commune",
    "message",
    "ignore",
}


def _values(field_data: list[dict[str, Any]]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for field in field_data:
        name = str(field.get("name") or "").lower()
        values = field.get("values") or []
        if name and values:
            mapped[name] = str(values[0]).strip()
    return mapped


def _validate_field_mapping(field_mapping: dict[str, str]) -> None:
    if any(target not in ALLOWED_LEAD_FIELD_TARGETS for target in field_mapping.values()):
        raise HTTPException(status_code=422, detail="El mapeo contiene un campo CRM no permitido")
    if "phone" not in field_mapping.values() and "email" not in field_mapping.values():
        raise HTTPException(status_code=422, detail="El formulario debe mapear teléfono o email")


def _normalize_lead_form_values(
    source_values: dict[str, str],
    field_mapping: dict[str, str],
    *,
    project_id: Optional[int],
) -> tuple[dict[str, Any], list[str]]:
    """Apply the production Lead Ads mapping to either preview or webhook data."""
    mapping = dict(STANDARD_FIELD_MAP)
    mapping.update(field_mapping)
    normalized: dict[str, str] = {}
    metadata_fields: dict[str, str] = {}
    warnings: list[str] = []

    for raw_source, raw_value in source_values.items():
        source = str(raw_source).strip().lower()
        value = str(raw_value or "").strip()
        if not source or not value:
            continue
        target = mapping.get(source, source)
        if target == "ignore":
            continue
        if target in {"name", "first_name", "last_name", "phone", "email"}:
            normalized[target] = value
        else:
            metadata_fields[target] = value

    if not normalized.get("name"):
        normalized["name"] = " ".join(filter(None, [
            normalized.get("first_name"),
            normalized.get("last_name"),
        ])).strip()

    phone: Optional[str] = normalized.get("phone") or None
    if phone:
        valid, normalized_phone = LeadService.validate_phone(phone)
        if valid:
            phone = normalized_phone
        else:
            warnings.append("El teléfono de ejemplo no tiene un formato válido y se omitirá.")
            phone = None

    email: Optional[str] = normalized.get("email") or None
    if email:
        email = email.strip().lower()
        if "@" not in email:
            warnings.append("El email de ejemplo no parece válido; revisa el valor antes de guardar.")

    if not phone and not email:
        warnings.append("El ejemplo no produce teléfono ni email para identificar al lead.")

    return {
        "phone": phone,
        "name": normalized.get("name") or None,
        "email": email,
        "tags": ["meta-lead-ad"],
        "metadata": {
            "source": "meta_lead_ads",
            "project_id": project_id,
            **metadata_fields,
        },
    }, warnings


class MetaLeadFormService:
    @staticmethod
    async def _form_and_project(
        db: AsyncSession,
        *,
        broker_id: int,
        form_id: int,
        project_id: Optional[int],
    ) -> MetaLeadForm:
        form = await db.scalar(select(MetaLeadForm).where(
            MetaLeadForm.id == form_id,
            MetaLeadForm.broker_id == broker_id,
        ))
        if not form:
            raise HTTPException(status_code=404, detail="Formulario Meta no encontrado")
        if project_id is not None:
            from app.models.project import Project
            if await db.scalar(select(Project.id).where(
                Project.id == project_id,
                Project.broker_id == broker_id,
            )) is None:
                raise HTTPException(status_code=422, detail="Proyecto inválido")
        return form

    @staticmethod
    async def list(db: AsyncSession, *, broker_id: int) -> list[MetaLeadForm]:
        return list((await db.scalars(select(MetaLeadForm).where(
            MetaLeadForm.broker_id == broker_id,
        ).order_by(MetaLeadForm.status, MetaLeadForm.name))).all())

    @staticmethod
    async def update_mapping(
        db: AsyncSession,
        *,
        broker_id: int,
        form_id: int,
        project_id: Optional[int],
        field_mapping: dict[str, str],
    ) -> MetaLeadForm:
        _validate_field_mapping(field_mapping)
        form = await MetaLeadFormService._form_and_project(
            db,
            broker_id=broker_id,
            form_id=form_id,
            project_id=project_id,
        )
        form.project_id = project_id
        form.field_mapping = field_mapping
        await db.commit()
        await db.refresh(form)
        return form

    @staticmethod
    async def preview_mapping(
        db: AsyncSession,
        *,
        broker_id: int,
        form_id: int,
        project_id: Optional[int],
        field_mapping: dict[str, str],
        sample_values: dict[str, str],
    ) -> dict[str, Any]:
        _validate_field_mapping(field_mapping)
        await MetaLeadFormService._form_and_project(
            db,
            broker_id=broker_id,
            form_id=form_id,
            project_id=project_id,
        )
        lead_payload, warnings = _normalize_lead_form_values(
            sample_values,
            field_mapping,
            project_id=project_id,
        )
        return {
            "lead_payload": lead_payload,
            "source_values": sample_values,
            "warnings": warnings,
        }

    @staticmethod
    async def sync_page(db: AsyncSession, *, page_asset: MetaAsset) -> int:
        resolved = await MetaAssetResolver.by_external_id(
            db,
            asset_type="facebook_page",
            external_id=page_asset.external_id,
            broker_id=page_asset.broker_id,
        )
        graph = MetaGraphClient(access_token=resolved.access_token)
        count = 0
        async for remote in graph.iterate(
            f"/{page_asset.external_id}/leadgen_forms",
            params={"fields": "id,name,status,questions,created_time"},
        ):
            external_id = str(remote.get("id") or "")
            if not external_id:
                continue
            statement = insert(MetaLeadForm).values(
                broker_id=page_asset.broker_id,
                page_asset_id=page_asset.id,
                external_id=external_id,
                name=str(remote.get("name") or f"Form {external_id}"),
                status=str(remote.get("status") or "active").lower(),
                questions=remote.get("questions") or [],
                field_mapping={},
                last_synced_at=datetime.now(timezone.utc),
            ).on_conflict_do_update(
                constraint="uq_meta_lead_form_external",
                set_={
                    "page_asset_id": page_asset.id,
                    "name": str(remote.get("name") or f"Form {external_id}"),
                    "status": str(remote.get("status") or "active").lower(),
                    "questions": remote.get("questions") or [],
                    "last_synced_at": datetime.now(timezone.utc),
                },
            )
            await db.execute(statement)
            count += 1
        await db.commit()
        return count


class MetaAttributionService:
    @staticmethod
    async def capture(
        db: AsyncSession,
        *,
        broker_id: int,
        lead_id: int,
        data: dict[str, Any],
        identity_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        lead = await db.scalar(select(Lead).where(
            Lead.id == lead_id,
            Lead.broker_id == broker_id,
        ))
        if not lead:
            return
        origin = {
            "source": "meta",
            "campaign_id": data.get("campaign_id"),
            "ad_set_id": data.get("ad_set_id") or data.get("adgroup_id"),
            "ad_id": data.get("ad_id"),
            "form_id": data.get("form_id"),
            "project_id": project_id,
            "captured_at": now.isoformat(),
        }
        lead_metadata = dict(lead.lead_metadata or {})
        lead_metadata.setdefault("meta_first_origin", origin)
        lead_metadata["meta_origin"] = origin
        lead.lead_metadata = lead_metadata
        common = {
            "broker_id": broker_id,
            "lead_id": lead_id,
            "identity_id": identity_id,
            "conversation_id": conversation_id,
            "source": "meta",
            "leadgen_id": data.get("leadgen_id"),
            "form_external_id": data.get("form_id"),
            "account_external_id": data.get("account_id"),
            "campaign_external_id": data.get("campaign_id"),
            "ad_set_external_id": data.get("ad_set_id") or data.get("adgroup_id"),
            "ad_external_id": data.get("ad_id"),
            "creative_external_id": data.get("creative_id"),
            "project_id": project_id,
            "utm": data.get("utm") or {},
            "attribution_metadata": data.get("metadata") or {},
            "captured_at": now,
        }
        first = await db.scalar(select(MetaLeadAttribution).where(
            MetaLeadAttribution.broker_id == broker_id,
            MetaLeadAttribution.lead_id == lead_id,
            MetaLeadAttribution.touch_type == "first",
        ))
        if first is None:
            db.add(MetaLeadAttribution(touch_type="first", **common))
        last = await db.scalar(select(MetaLeadAttribution).where(
            MetaLeadAttribution.broker_id == broker_id,
            MetaLeadAttribution.lead_id == lead_id,
            MetaLeadAttribution.touch_type == "last",
        ))
        if last is None:
            db.add(MetaLeadAttribution(touch_type="last", **common))
        else:
            for key, value in common.items():
                if key not in {"broker_id", "lead_id"}:
                    setattr(last, key, value)

    @staticmethod
    async def capture_message_referral(
        db: AsyncSession,
        *,
        lead: Lead,
        identity: ChannelIdentity,
        conversation: Conversation,
        referral: Optional[dict[str, Any]],
    ) -> None:
        if not referral:
            return
        await MetaAttributionService.capture(
            db,
            broker_id=lead.broker_id,
            lead_id=lead.id,
            identity_id=identity.id,
            conversation_id=conversation.id,
            data={
                "campaign_id": referral.get("campaign_id"),
                "ad_id": referral.get("ad_id") or referral.get("source_id"),
                "creative_id": referral.get("creative_id"),
                "metadata": {"referral": referral},
            },
        )


class MetaLeadgenService:
    @staticmethod
    async def process(db: AsyncSession, event: NormalizedLeadgen) -> Optional[Lead]:
        page = await db.scalar(select(MetaAsset).where(
            MetaAsset.asset_type == "facebook_page",
            MetaAsset.external_id == event.asset_external_id,
            MetaAsset.owner_type == "broker",
            MetaAsset.approval_status == "approved",
            MetaAsset.status == "active",
        ))
        if not page:
            return None
        feature = await MetaFeatureFlagService.effective(db, page.broker_id)
        if not feature["channels"].get("lead_ads", False):
            return None
        form = await db.scalar(select(MetaLeadForm).where(
            MetaLeadForm.broker_id == page.broker_id,
            MetaLeadForm.external_id == event.form_id,
        ))
        if not form:
            return None
        existing = await db.scalar(select(MetaLeadAttribution).where(
            MetaLeadAttribution.broker_id == page.broker_id,
            MetaLeadAttribution.form_external_id == event.form_id,
            MetaLeadAttribution.leadgen_id == event.leadgen_id,
            MetaLeadAttribution.touch_type == "first",
        ))
        if existing:
            return await db.scalar(select(Lead).where(
                Lead.id == existing.lead_id,
                Lead.broker_id == page.broker_id,
            ))

        resolved = await MetaAssetResolver.by_external_id(
            db,
            asset_type="facebook_page",
            external_id=page.external_id,
            broker_id=page.broker_id,
        )
        remote = await MetaGraphClient(access_token=resolved.access_token).get(
            f"/{event.leadgen_id}",
            params={"fields": "id,created_time,field_data,ad_id,adset_id,campaign_id,form_id,platform"},
        )
        raw_fields = _values(remote.get("field_data") or [])
        lead_payload, _ = _normalize_lead_form_values(
            raw_fields,
            form.field_mapping or {},
            project_id=form.project_id,
        )
        phone = lead_payload["phone"]
        email = lead_payload["email"]
        candidates = []
        candidate_filters = []
        if phone:
            candidate_filters.append(Lead.phone == phone)
        if email:
            candidate_filters.append(Lead.email.ilike(email))
        if candidate_filters:
            candidates = list((await db.scalars(select(Lead).where(
                Lead.broker_id == page.broker_id,
                or_(*candidate_filters),
            ).limit(3))).all())
        lead = candidates[0] if len(candidates) == 1 else None
        if lead is None:
            lead = Lead(
                broker_id=page.broker_id,
                phone=phone,
                name=lead_payload["name"],
                email=email or None,
                status=LeadStatus.COLD,
                pipeline_stage="entrada",
                stage_entered_at=datetime.now(timezone.utc),
                tags=lead_payload["tags"] + (["revision-identidad"] if len(candidates) > 1 else []),
                lead_metadata={
                    **lead_payload["metadata"],
                    "leadgen_id": event.leadgen_id,
                    "identity_review_candidate_ids": [item.id for item in candidates],
                },
            )
            db.add(lead)
            await db.flush()
            try:
                await LeadAssignmentService.assign_automatically(
                    db,
                    lead=lead,
                    reason="meta_lead_ads",
                )
            except Exception:
                lead.assigned_to = None
        await MetaAttributionService.capture(
            db,
            broker_id=page.broker_id,
            lead_id=lead.id,
            project_id=form.project_id,
            data={
                "leadgen_id": event.leadgen_id,
                "form_id": event.form_id,
                "campaign_id": remote.get("campaign_id"),
                "ad_set_id": remote.get("adset_id") or event.adgroup_id,
                "ad_id": remote.get("ad_id") or event.ad_id,
                "metadata": {"platform": remote.get("platform"), "created_time": remote.get("created_time")},
            },
        )
        db.add(ActivityLog(
            lead_id=lead.id,
            action_type="meta_lead_ad_received",
            details={"form_id": event.form_id, "leadgen_id": event.leadgen_id, "project_id": form.project_id},
        ))
        await db.commit()
        await db.refresh(lead)
        return lead
