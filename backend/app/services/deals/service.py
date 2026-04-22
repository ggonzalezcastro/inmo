"""
DealService — business logic for creating and managing Deals.

Does NOT contain state machine transitions (see state_machine.py).
Handles: validation, creation, basic queries.
"""
import logging

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal, DEAL_STAGES, DELIVERY_TYPES
from app.models.lead import Lead
from app.models.property import Property
from app.services.deals.exceptions import DealConflictError, DealError, DealNotFoundError
from app.services.deals.metrics import record_deal_created

logger = logging.getLogger(__name__)


class DealService:

    @staticmethod
    async def create(
        db: AsyncSession,
        broker_id: int,
        lead_id: int,
        property_id: int,
        delivery_type: str,
        created_by_user_id: int | None = None,
    ) -> Deal:
        """
        Create a new Deal in 'draft' stage.

        Validates:
        - Lead and Property belong to same broker
        - Property is 'available' (not reserved/sold)
        - No existing active deal for this property (DB unique index also enforces this)

        Does NOT mark Property as reserved yet — that happens on transition to 'reserva'.
        Does NOT change lead.pipeline_stage yet — that happens on transition to 'reserva'.

        Raises: DealConflictError, DealError
        """
        lead = await db.get(Lead, lead_id)
        if not lead or lead.broker_id != broker_id:
            raise DealError(f"Lead {lead_id} no encontrado.", status_code=404)

        prop = await db.get(Property, property_id)
        if not prop or prop.broker_id != broker_id:
            raise DealError(f"Propiedad {property_id} no encontrada.", status_code=404)

        if prop.status not in ("available",):
            raise DealConflictError(property_id)

        # Belt-and-suspenders check; DB partial unique index also guards this
        existing = await db.execute(
            select(Deal).where(
                and_(
                    Deal.broker_id == broker_id,
                    Deal.property_id == property_id,
                    Deal.stage != "cancelado",
                )
            )
        )
        if existing.scalar_one_or_none():
            raise DealConflictError(property_id)

        deal = Deal(
            broker_id=broker_id,
            lead_id=lead_id,
            property_id=property_id,
            delivery_type=delivery_type if delivery_type in DELIVERY_TYPES else "desconocida",
            stage="draft",
            created_by_user_id=created_by_user_id,
            jefatura_review_required=(delivery_type == "futura"),
        )
        db.add(deal)

        # Mark property as reserved immediately — the unit is no longer available
        prop.status = "reserved"
        db.add(prop)

        await db.flush()  # get deal.id without committing
        record_deal_created(broker_id=broker_id, delivery_type=deal.delivery_type)
        return deal

    @staticmethod
    async def get(db: AsyncSession, deal_id: int, broker_id: int) -> Deal:
        """Get a deal by id, ensuring broker ownership."""
        deal = await db.get(Deal, deal_id)
        if not deal or deal.broker_id != broker_id:
            raise DealNotFoundError(deal_id)
        return deal

    @staticmethod
    async def list_deals(
        db: AsyncSession,
        broker_id: int,
        lead_id: int | None = None,
        property_id: int | None = None,
        stage: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Deal]:
        """List deals for a broker with optional filters."""
        filters = [Deal.broker_id == broker_id]
        if lead_id:
            filters.append(Deal.lead_id == lead_id)
        if property_id:
            filters.append(Deal.property_id == property_id)
        if stage:
            filters.append(Deal.stage == stage)

        result = await db.execute(
            select(Deal)
            .where(and_(*filters))
            .order_by(Deal.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
