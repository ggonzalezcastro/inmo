"""
Tests for the MCP Server tools.

Tests run the MCP tool functions directly (without starting the server process)
to verify business logic.
"""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytz

from app.mcp.server import get_available_appointment_slots, create_appointment

CHILE_TZ = pytz.timezone("America/Santiago")


class TestGetAvailableSlots:
    """Test the get_available_appointment_slots MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_slots_with_defaults(self, db_session):
        """Should return available slots when called with default params."""
        mock_slots = [
            {"date": "2025-02-01", "time": "10:00", "duration": 60},
            {"date": "2025-02-01", "time": "11:00", "duration": 60},
        ]

        with patch("app.mcp.server._get_db_session", new_callable=AsyncMock, return_value=db_session), \
             patch("app.services.appointment_service.AppointmentService.get_available_slots",
                   new_callable=AsyncMock, return_value=mock_slots), \
             patch("app.services.appointment_service.AppointmentService.format_slots_for_llm",
                   return_value="Formatted slots"):

            result = await get_available_appointment_slots()

        assert result["success"] is True
        assert result["result"]["count"] == 2
        assert result["result"]["formatted"] == "Formatted slots"

    @pytest.mark.asyncio
    async def test_with_custom_start_date(self, db_session):
        """Should parse custom start_date correctly."""
        with patch("app.mcp.server._get_db_session", new_callable=AsyncMock, return_value=db_session), \
             patch("app.services.appointment_service.AppointmentService.get_available_slots",
                   new_callable=AsyncMock, return_value=[]) as mock_get, \
             patch("app.services.appointment_service.AppointmentService.format_slots_for_llm",
                   return_value=""):

            result = await get_available_appointment_slots(
                start_date="2025-03-01",
                days_ahead=7,
                duration_minutes=30,
            )

        assert result["success"] is True
        # Verify the start_date was parsed correctly
        call_args = mock_get.call_args
        assert call_args.kwargs["start_date"] == date(2025, 3, 1)
        assert call_args.kwargs["duration_minutes"] == 30

    @pytest.mark.asyncio
    async def test_handles_invalid_date_gracefully(self, db_session):
        """Should fallback to today when start_date is invalid."""
        with patch("app.mcp.server._get_db_session", new_callable=AsyncMock, return_value=db_session), \
             patch("app.services.appointment_service.AppointmentService.get_available_slots",
                   new_callable=AsyncMock, return_value=[]) as mock_get, \
             patch("app.services.appointment_service.AppointmentService.format_slots_for_llm",
                   return_value=""):

            result = await get_available_appointment_slots(start_date="not-a-date")

        assert result["success"] is True
        call_args = mock_get.call_args
        assert call_args.kwargs["start_date"] == date.today()

    @pytest.mark.asyncio
    async def test_handles_db_error(self, db_session):
        """Should return error on database failure."""
        with patch("app.mcp.server._get_db_session", new_callable=AsyncMock, return_value=db_session), \
             patch("app.services.appointment_service.AppointmentService.get_available_slots",
                   new_callable=AsyncMock, side_effect=Exception("DB connection failed")):

            result = await get_available_appointment_slots()

        assert result["success"] is False
        assert "DB connection failed" in result["error"]


class TestCreateAppointment:
    """Test the create_appointment MCP tool."""

    @pytest.mark.asyncio
    async def test_creates_appointment_successfully(self, db_session):
        """Should create appointment when lead has email."""
        from app.models.lead import Lead
        from app.models.user import User, UserRole
        from app.middleware.auth import hash_password

        # Create lead with email
        lead = Lead(phone="+56912345678", name="Test Lead", email="test@test.com",
                    status="cold", lead_score=0)
        db_session.add(lead)
        await db_session.commit()
        await db_session.refresh(lead)

        # Create agent
        user = User(email="agent@test.com", hashed_password=hash_password("pass"),
                    role=UserRole.ADMIN, name="Test Agent")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        mock_apt = MagicMock()
        mock_apt.id = 1
        mock_apt.start_time = CHILE_TZ.localize(datetime(2025, 2, 15, 14, 0))
        mock_apt.end_time = CHILE_TZ.localize(datetime(2025, 2, 15, 15, 0))
        mock_apt.meet_url = "https://meet.google.com/test"
        mock_apt.status = MagicMock(value="scheduled")

        with patch("app.mcp.server._get_db_session", new_callable=AsyncMock, return_value=db_session), \
             patch("app.services.appointment_service.AppointmentService.create_appointment",
                   new_callable=AsyncMock, return_value=mock_apt):

            result = await create_appointment(
                start_time="2025-02-15T14:00:00-03:00",
                lead_id=lead.id,
            )

        assert result["success"] is True
        assert result["result"]["appointment_id"] == 1
        assert result["result"]["meet_url"] == "https://meet.google.com/test"

    @pytest.mark.asyncio
    async def test_fails_when_lead_has_no_email(self, db_session):
        """Should fail when lead has no email."""
        from app.models.lead import Lead

        lead = Lead(phone="+56912345678", name="No Email Lead",
                    status="cold", lead_score=0)
        db_session.add(lead)
        await db_session.commit()
        await db_session.refresh(lead)

        with patch("app.mcp.server._get_db_session", new_callable=AsyncMock, return_value=db_session):
            result = await create_appointment(
                start_time="2025-02-15T14:00:00-03:00",
                lead_id=lead.id,
            )

        assert result["success"] is False
        assert "email" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fails_when_lead_not_found(self, db_session):
        """Should fail when lead does not exist."""
        with patch("app.mcp.server._get_db_session", new_callable=AsyncMock, return_value=db_session):
            result = await create_appointment(
                start_time="2025-02-15T14:00:00-03:00",
                lead_id=99999,
            )

        assert result["success"] is False
        assert "no encontrado" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fails_with_invalid_date_format(self, db_session):
        """Should fail with invalid date format."""
        from app.models.lead import Lead

        lead = Lead(phone="+56912345678", name="Test", email="t@t.com",
                    status="cold", lead_score=0)
        db_session.add(lead)
        await db_session.commit()
        await db_session.refresh(lead)

        from app.models.user import User, UserRole
        from app.middleware.auth import hash_password
        user = User(email="agent2@test.com", hashed_password=hash_password("pass"),
                    role=UserRole.ADMIN, name="Test Agent 2")
        db_session.add(user)
        await db_session.commit()

        with patch("app.mcp.server._get_db_session", new_callable=AsyncMock, return_value=db_session):
            result = await create_appointment(
                start_time="not-a-valid-datetime",
                lead_id=lead.id,
            )

        assert result["success"] is False
        assert "formato" in result["error"].lower() or "inválido" in result["error"].lower()
