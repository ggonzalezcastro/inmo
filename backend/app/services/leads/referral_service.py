"""Referral capture for leads that have already been won."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.schemas.lead import LeadCreate
from app.services.leads.lead_service import LeadService
from app.shared.pipeline_stages import PIPELINE_STAGE_ENTRY, PIPELINE_STAGE_WON
from app.services.shared import ActivityService


class ReferralService:
    """Create and link referred leads without overwriting the winning client."""

    @staticmethod
    async def _source_lead(
        db: AsyncSession,
        source_lead_id: int,
        broker_id: int,
    ) -> Lead:
        result = await db.execute(
            select(Lead).where(
                Lead.id == source_lead_id,
                Lead.broker_id == broker_id,
            )
        )
        lead = result.scalars().first()
        if not lead:
            raise ValueError("Lead de origen no encontrado")
        if lead.pipeline_stage != PIPELINE_STAGE_WON:
            raise ValueError("Los referidos solo se registran desde un lead ganado")
        return lead

    @staticmethod
    async def register(
        db: AsyncSession,
        *,
        source_lead_id: int,
        broker_id: int,
        name: str,
        phone: str,
    ) -> dict:
        clean_name = (name or "").strip()
        if not clean_name or len(clean_name) > 100:
            raise ValueError("El nombre del referido debe tener entre 1 y 100 caracteres")

        is_valid, normalized_phone = LeadService.validate_phone((phone or "").strip())
        if not is_valid:
            raise ValueError(normalized_phone)

        source = await ReferralService._source_lead(db, source_lead_id, broker_id)
        if normalized_phone == source.phone:
            raise ValueError("El teléfono del referido debe ser distinto al del cliente")

        existing_result = await db.execute(
            select(Lead)
            .where(
                Lead.broker_id == broker_id,
                Lead.phone == normalized_phone,
                Lead.id != source_lead_id,
            )
            .order_by(Lead.created_at.asc())
            .limit(1)
        )
        referred_lead = existing_result.scalars().first()
        created = referred_lead is None

        if referred_lead is None:
            referred_lead = await LeadService.create_lead(
                db,
                LeadCreate(
                    name=clean_name,
                    phone=normalized_phone,
                    tags=["referido"],
                    metadata={
                        "source": "referral",
                        "referred_by_lead_id": source.id,
                        "referral_collected_by": "referral_agent",
                    },
                ),
                broker_id=broker_id,
            )
            referred_lead.assigned_to = source.assigned_to
            referred_lead.pipeline_stage = PIPELINE_STAGE_ENTRY
            referred_lead.stage_entered_at = datetime.now(timezone.utc)
        else:
            referred_meta = dict(referred_lead.lead_metadata or {})
            sources = list(referred_meta.get("referral_source_lead_ids") or [])
            if source.id not in sources:
                sources.append(source.id)
            referred_meta["referral_source_lead_ids"] = sources
            referred_lead.lead_metadata = referred_meta
            tags = list(referred_lead.tags or [])
            if "referido" not in tags:
                tags.append("referido")
                referred_lead.tags = tags

        source_meta = dict(source.lead_metadata or {})
        referral_ids = list(source_meta.get("referral_lead_ids") or [])
        if referred_lead.id not in referral_ids:
            referral_ids.append(referred_lead.id)
        source_meta.update({
            "referral_lead_ids": referral_ids,
            "referral_status": "collected",
            "referral_last_collected_at": datetime.now(timezone.utc).isoformat(),
            "current_agent": "referral",
        })
        source.lead_metadata = source_meta

        db.add(referred_lead)
        db.add(source)
        await db.commit()
        await db.refresh(referred_lead)

        await ActivityService.log_activity(
            db,
            lead_id=source.id,
            action_type="referral_collected",
            details={
                "referred_lead_id": referred_lead.id,
                "created_new_lead": created,
                "assigned_to": referred_lead.assigned_to,
            },
        )
        return {
            "lead_id": referred_lead.id,
            "created": created,
            "name": referred_lead.name or clean_name,
        }

    @staticmethod
    async def decline(
        db: AsyncSession,
        *,
        source_lead_id: int,
        broker_id: int,
    ) -> None:
        source = await ReferralService._source_lead(db, source_lead_id, broker_id)
        metadata = dict(source.lead_metadata or {})
        metadata.update({
            "referral_status": "declined",
            "referral_declined_at": datetime.now(timezone.utc).isoformat(),
            "current_agent": "referral",
        })
        source.lead_metadata = metadata
        db.add(source)
        await db.commit()
        await ActivityService.log_activity(
            db,
            lead_id=source.id,
            action_type="referral_declined",
            details={"source": "referral_agent"},
        )
