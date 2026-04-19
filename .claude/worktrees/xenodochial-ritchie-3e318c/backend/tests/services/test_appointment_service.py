"""
Tests for AppointmentService - availability and creation.
SQLite is used; advisory lock is skipped (non-PostgreSQL).
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytz

from app.services.appointments import AppointmentService
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.lead import Lead
from app.models.user import User
from app.models.base import Base


CHILE_TZ = pytz.timezone("America/Santiago")


@pytest.fixture
def sample_lead(db_session):
    """Create a sample lead for appointment tests."""
    async def _create():
        lead = Lead(
            phone="+56912345678",
            name="Test Lead",
            email="test@test.com",
            status="cold",
            lead_score=0,
            broker_id=None,
        )
        db_session.add(lead)
        await db_session.commit()
        await db_session.refresh(lead)
        return lead
    return _create


@pytest.fixture
def sample_user(db_session):
    """Create a sample user (agent) for appointment tests."""
    from app.middleware.auth import hash_password
    from app.models.user import UserRole

    async def _create():
        user = User(
            email="agent@test.com",
            hashed_password=hash_password("password123"),
            role=UserRole.ADMIN,
            broker_id=None,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user
    return _create


class TestAppointmentCheckAvailability:
    """Test check_availability"""

    @pytest.mark.asyncio
    async def test_empty_slot_is_available(self, db_session, sample_lead):
        lead = await sample_lead()
        start = CHILE_TZ.localize(datetime(2025, 2, 1, 10, 0, 0))
        end = CHILE_TZ.localize(datetime(2025, 2, 1, 11, 0, 0))
        is_avail = await AppointmentService.check_availability(
            db_session, start_time=start, end_time=end
        )
        assert is_avail is True

    @pytest.mark.asyncio
    async def test_slot_with_existing_appointment_not_available(self, db_session, sample_lead):
        lead = await sample_lead()
        start = CHILE_TZ.localize(datetime(2025, 2, 1, 10, 0, 0))
        end = CHILE_TZ.localize(datetime(2025, 2, 1, 11, 0, 0))
        apt = Appointment(
            lead_id=lead.id,
            agent_id=None,
            status=AppointmentStatus.SCHEDULED,
            start_time=start,
            end_time=end,
            duration_minutes=60,
        )
        db_session.add(apt)
        await db_session.commit()

        is_avail = await AppointmentService.check_availability(
            db_session, start_time=start, end_time=end
        )
        assert is_avail is False


class TestAppointmentCreate:
    """Test create_appointment (advisory lock skipped on SQLite)"""

    @pytest.mark.asyncio
    async def test_create_appointment_returns_appointment(self, db_session, sample_lead):
        lead = await sample_lead()
        start = CHILE_TZ.localize(datetime(2025, 2, 15, 14, 0, 0))
        with patch("app.services.appointments.get_google_calendar_service") as mock_cal:
            mock_svc = MagicMock()
            mock_svc.service = None
            mock_cal.return_value = mock_svc

            apt = await AppointmentService.create_appointment(
                db_session,
                lead_id=lead.id,
                start_time=start,
                duration_minutes=60,
                appointment_type=AppointmentType.VIRTUAL_MEETING,
            )
        assert apt is not None
        assert apt.lead_id == lead.id
        assert apt.status == AppointmentStatus.SCHEDULED
        assert apt.duration_minutes == 60
        assert apt.meet_url is not None
