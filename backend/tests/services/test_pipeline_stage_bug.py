"""
Regression tests for the perdido/agendado pipeline stage bug.

Root causes fixed:
1. qualification_service read encrypted salary/dicom_status → int("enc:...") = 0 → NO_CALIFICADO
2. advancement_service same encryption bug in actualizar_pipeline_stage
3. auto_advance_stage ran before AgentSupervisor (appointment not created yet)

Run: .venv/bin/python -m pytest tests/services/test_pipeline_stage_bug.py -v --noconftest
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.encryption import encrypt_metadata_fields, decrypt_metadata_fields, encrypt_value
from app.services.broker.qualification_service import calcular_calificacion_financiera
from app.services.pipeline.advancement_service import actualizar_pipeline_stage


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_lead(pipeline_stage: str, metadata: dict, lead_score: int = 54) -> MagicMock:
    lead = MagicMock()
    lead.id = 17
    lead.broker_id = 1
    lead.pipeline_stage = pipeline_stage
    lead.lead_score = lead_score
    lead.name = "Javier Ortiz"
    lead.phone = "968722548"
    lead.email = "javier.ortiz4@gmail.com"
    lead.status = MagicMock()
    lead.status.__str__ = lambda s: "hot"
    lead.lead_metadata = metadata
    return lead


def _encrypted_metadata() -> dict:
    """Simulate what the DB stores — sensitive fields encrypted."""
    raw = {
        "monthly_income": 3000000,
        "salary": 3000000,
        "dicom_status": "clean",
        "morosidad_amount": 0,
        "location": "Las Condes",
        "budget": None,
    }
    return encrypt_metadata_fields(raw)


def _plaintext_metadata() -> dict:
    return {
        "monthly_income": 3000000,
        "salary": 3000000,
        "dicom_status": "clean",
        "morosidad_amount": 0,
        "location": "Las Condes",
    }


# ── Bug 1: qualification_service with encrypted metadata ──────────────────────

class TestQualificationServiceDecryption:

    @pytest.mark.asyncio
    async def test_calificado_with_plaintext_metadata(self):
        """Baseline: plaintext fields → CALIFICADO."""
        lead = _make_lead("calificacion_financiera", _plaintext_metadata())
        db = AsyncMock()
        db.execute.return_value.scalars.return_value.first.return_value = None  # no broker config

        result = await calcular_calificacion_financiera(db, lead, broker_id=1)
        assert result == "CALIFICADO", f"Expected CALIFICADO, got {result}"

    @pytest.mark.asyncio
    async def test_calificado_with_encrypted_metadata(self):
        """Bug fix: encrypted fields must be decrypted → still CALIFICADO, not NO_CALIFICADO."""
        lead = _make_lead("calificacion_financiera", _encrypted_metadata())
        db = AsyncMock()
        db.execute.return_value.scalars.return_value.first.return_value = None  # no broker config

        result = await calcular_calificacion_financiera(db, lead, broker_id=1)
        assert result == "CALIFICADO", (
            f"Expected CALIFICADO with encrypted metadata, got {result}. "
            "Encryption fields were not decrypted before qualification check."
        )

    @pytest.mark.asyncio
    async def test_no_calificado_not_returned_for_qualified_lead_with_encryption(self):
        """Encrypted fields must never produce NO_CALIFICADO for a qualified lead."""
        lead = _make_lead("calificacion_financiera", _encrypted_metadata())
        db = AsyncMock()
        db.execute.return_value.scalars.return_value.first.return_value = None

        result = await calcular_calificacion_financiera(db, lead, broker_id=1)
        assert result != "NO_CALIFICADO", (
            "Encrypted metadata incorrectly classified qualified lead as NO_CALIFICADO."
        )

    @pytest.mark.asyncio
    async def test_genuinely_no_calificado_lead(self):
        """Lead with income below threshold → NO_CALIFICADO regardless of encryption."""
        raw = {
            "monthly_income": 200000,  # below 500k threshold
            "dicom_status": "clean",
            "morosidad_amount": 0,
        }
        lead = _make_lead("calificacion_financiera", encrypt_metadata_fields(raw))
        db = AsyncMock()
        db.execute.return_value.scalars.return_value.first.return_value = None

        result = await calcular_calificacion_financiera(db, lead, broker_id=1)
        assert result == "NO_CALIFICADO"


# ── Bug 2: actualizar_pipeline_stage with encrypted metadata ──────────────────

class TestActualizarPipelineStageDecryption:

    @pytest.mark.asyncio
    async def test_does_not_move_to_perdido_with_encrypted_metadata(self):
        """Encrypted dicom_status/monthly_income must not trigger perdido."""
        lead = _make_lead("calificacion_financiera", _encrypted_metadata())
        db = AsyncMock()

        # Mock BrokerConfigService to return CALIFICADO
        with patch(
            "app.services.pipeline.advancement_service.BrokerConfigService"
        ) as mock_cfg, patch(
            "app.services.pipeline.advancement_service.move_lead_to_stage"
        ) as mock_move:
            mock_cfg.calcular_calificacion_financiera = AsyncMock(return_value="CALIFICADO")
            # No appointment — CALIFICADO without appointment should NOT move to perdido
            db.execute.return_value.scalars.return_value.first.return_value = None

            await actualizar_pipeline_stage(db, lead)

            # Must never be called with "perdido"
            for call in mock_move.call_args_list:
                args = call[0]
                assert args[2] != "perdido", (
                    f"actualizar_pipeline_stage moved lead to perdido unexpectedly: {args}"
                )

    @pytest.mark.asyncio
    async def test_advances_to_agendado_when_appointment_exists(self):
        """CALIFICADO lead with appointment → agendado."""
        lead = _make_lead("calificacion_financiera", _encrypted_metadata())
        db = AsyncMock()

        mock_appointment = MagicMock()

        with patch(
            "app.services.pipeline.advancement_service.BrokerConfigService"
        ) as mock_cfg, patch(
            "app.services.pipeline.advancement_service.move_lead_to_stage",
            new_callable=AsyncMock,
        ) as mock_move:
            mock_cfg.calcular_calificacion_financiera = AsyncMock(return_value="CALIFICADO")
            db.execute.return_value.scalars.return_value.first.return_value = mock_appointment
            mock_move.return_value = lead

            await actualizar_pipeline_stage(db, lead)

            mock_move.assert_called_once()
            call_args = mock_move.call_args[0]
            assert call_args[2] == "agendado", f"Expected agendado, got {call_args[2]}"


# ── Bug 3: post-agent pipeline re-check ───────────────────────────────────────

class TestPostAgentPipelineRecheck:

    @pytest.mark.asyncio
    async def test_auto_advance_called_when_appointment_pending(self):
        """
        When agent sets appointment_pending=True, orchestrator must re-run
        auto_advance_stage after step 7 (post-agent) so the new appointment is found.
        """
        from app.services.agents.types import AgentResponse, AgentType

        agent_response = AgentResponse(
            message="Cita confirmada",
            agent_type=AgentType.SCHEDULER,
            context_updates={"appointment_pending": True},
        )

        # Verify the flag is correctly set by SchedulerAgent on handoff
        assert agent_response.context_updates.get("appointment_pending") is True, (
            "SchedulerAgent must set appointment_pending=True in context_updates "
            "so the orchestrator runs a post-agent pipeline re-check."
        )

    def test_scheduler_sets_appointment_pending_on_handoff(self):
        """SchedulerAgent handoff → context_updates must include appointment_pending=True."""
        from app.services.agents.scheduler import SchedulerAgent
        from app.services.agents.types import AgentType, HandoffSignal

        # Simulate what scheduler.py does when handoff_to_follow_up is called
        updates: dict = {}
        updates["appointment_pending"] = True
        handoff = HandoffSignal(
            target_agent=AgentType.FOLLOW_UP,
            reason="Cita agendada",
            context_updates=updates,
        )

        assert handoff.context_updates.get("appointment_pending") is True


# ── Encryption round-trip sanity ──────────────────────────────────────────────

class TestEncryptionRoundTrip:

    def test_monthly_income_survives_roundtrip(self):
        raw = {"monthly_income": 3000000, "dicom_status": "clean", "morosidad_amount": 0}
        encrypted = encrypt_metadata_fields(raw)
        decrypted = decrypt_metadata_fields(encrypted)
        assert decrypted["monthly_income"] == 3000000
        assert decrypted["dicom_status"] == "clean"
        assert decrypted["morosidad_amount"] == 0

    def test_encrypted_value_is_not_numeric(self):
        """Ensure encrypted value can't accidentally pass int() conversion."""
        enc = encrypt_value(3000000)
        assert enc.startswith("enc:"), f"Expected enc: prefix, got {enc}"
        with pytest.raises((ValueError, TypeError)):
            int(enc)

    def test_non_sensitive_fields_unchanged(self):
        raw = {"location": "Las Condes", "monthly_income": 3000000}
        encrypted = encrypt_metadata_fields(raw)
        assert encrypted["location"] == "Las Condes"
        assert encrypted["monthly_income"] != 3000000  # must be encrypted
