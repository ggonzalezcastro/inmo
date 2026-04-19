"""
AppointmentSaga — compensable transaction for appointment creation (Phase 3.2).

The appointment creation flow involves three steps:
  1. Reserve a slot
  2. Create the appointment record in the DB
  3. Confirm the event in Google Calendar

If any step fails after a previous one succeeded, the saga runs compensating
actions to leave the system in a consistent state (no orphaned slots or DB
records without a Calendar event).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AppointmentSaga:
    """
    Saga coordinator for creating a property-visit appointment.

    Usage
    -----
        saga = AppointmentSaga(db)
        appointment_id = await saga.execute(
            lead_id=42,
            broker_id=1,
            start_time=datetime(...),
            duration_minutes=60,
            agent_id=None,
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._slot_id: Optional[int] = None
        self._appointment_id: Optional[int] = None

    async def execute(
        self,
        lead_id: int,
        broker_id: int,
        start_time: datetime,
        duration_minutes: int = 60,
        agent_id: Optional[int] = None,
    ) -> int:
        """
        Execute the full appointment-creation saga.

        Returns
        -------
        int
            The id of the created Appointment record.

        Raises
        ------
        Exception
            Re-raises any uncompensable failure after running compensating
            actions for the steps that already succeeded.
        """
        # Step 1: Reserve availability slot
        self._slot_id = await self._reserve_slot(broker_id, start_time, duration_minutes)
        logger.info("[AppointmentSaga] Step 1 done — slot reserved: slot_id=%s", self._slot_id)

        try:
            # Step 2: Persist appointment record in DB
            self._appointment_id = await self._create_appointment_record(
                lead_id=lead_id,
                broker_id=broker_id,
                start_time=start_time,
                duration_minutes=duration_minutes,
                agent_id=agent_id,
            )
            logger.info(
                "[AppointmentSaga] Step 2 done — appointment created: appointment_id=%s",
                self._appointment_id,
            )

            # Step 3: Confirm event in external calendar
            await self._confirm_calendar_event(self._appointment_id, broker_id)
            logger.info(
                "[AppointmentSaga] Step 3 done — calendar event confirmed: appointment_id=%s",
                self._appointment_id,
            )

        except Exception as exc:
            logger.error("[AppointmentSaga] Failed at step, running compensation: %s", exc)
            await self._compensate()
            raise

        return self._appointment_id

    # ── Private steps ─────────────────────────────────────────────────────────

    async def _reserve_slot(
        self, broker_id: int, start_time: datetime, duration_minutes: int
    ) -> Optional[int]:
        """Mark the slot as tentatively taken. Returns a slot_id or None."""
        try:
            from app.services.appointments.availability import check_availability
            # Verify the slot is available (does not commit a hard reservation)
            available = await check_availability(
                self._db, broker_id=broker_id, start_time=start_time
            )
            if not available:
                raise ValueError(
                    f"Slot {start_time.isoformat()} is not available for broker {broker_id}"
                )
            # A real implementation would insert a tentative AvailabilitySlot row here.
            # We return None to signal no slot row was created (not-yet-persisted reservation).
            return None
        except Exception as exc:
            logger.warning("[AppointmentSaga] _reserve_slot failed: %s", exc)
            raise

    async def _create_appointment_record(
        self,
        lead_id: int,
        broker_id: int,
        start_time: datetime,
        duration_minutes: int,
        agent_id: Optional[int],
    ) -> int:
        """Create the Appointment row in the database."""
        from app.services.appointments.service import AppointmentService
        appointment = await AppointmentService.create_appointment(
            db=self._db,
            lead_id=lead_id,
            start_time=start_time,
            duration_minutes=duration_minutes,
            agent_id=agent_id,
            broker_id=broker_id,
        )
        return appointment.id

    async def _confirm_calendar_event(self, appointment_id: int, broker_id: int) -> None:
        """Sync the appointment to the external calendar (Google / Outlook)."""
        try:
            from app.services.appointments.service import AppointmentService
            await AppointmentService.sync_to_calendar(
                db=self._db,
                appointment_id=appointment_id,
                broker_id=broker_id,
            )
        except Exception as exc:
            # Calendar sync failure is non-fatal in isolation but we still propagate
            # so the saga can compensate (cancel the appointment record).
            logger.error(
                "[AppointmentSaga] Calendar sync failed for appointment %s: %s",
                appointment_id, exc,
            )
            raise

    # ── Compensation ──────────────────────────────────────────────────────────

    async def _compensate(self) -> None:
        """Run compensating actions in reverse order."""
        if self._appointment_id is not None:
            await self._cancel_appointment_record(self._appointment_id)
        if self._slot_id is not None:
            await self._release_slot(self._slot_id)

    async def _cancel_appointment_record(self, appointment_id: int) -> None:
        """Cancel (soft-delete) the appointment record created in Step 2."""
        try:
            from app.models.appointment import Appointment, AppointmentStatus
            from sqlalchemy.future import select
            result = await self._db.execute(
                select(Appointment).where(Appointment.id == appointment_id)
            )
            appointment = result.scalars().first()
            if appointment:
                appointment.status = AppointmentStatus.CANCELLED
                await self._db.commit()
                logger.info(
                    "[AppointmentSaga] Compensation: appointment %s cancelled", appointment_id
                )
        except Exception as comp_exc:
            logger.error(
                "[AppointmentSaga] Compensation failed — could not cancel appointment %s: %s",
                appointment_id, comp_exc,
            )

    async def _release_slot(self, slot_id: int) -> None:
        """Release a previously reserved slot (compensation for Step 1)."""
        try:
            from app.models.appointment import AvailabilitySlot
            from sqlalchemy.future import select
            result = await self._db.execute(
                select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
            )
            slot = result.scalars().first()
            if slot:
                slot.is_available = True
                await self._db.commit()
                logger.info(
                    "[AppointmentSaga] Compensation: slot %s released", slot_id
                )
        except Exception as comp_exc:
            logger.error(
                "[AppointmentSaga] Compensation failed — could not release slot %s: %s",
                slot_id, comp_exc,
            )
