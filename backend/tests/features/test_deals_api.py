"""
Deal feature tests — service layer and state machine.
No DB required. Run with: pytest tests/features/test_deals_api.py -v --noconftest
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.deals.exceptions import DealConflictError, DealError
from app.services.deals.service import DealService
from app.services.deals.state_machine import transition
from app.services.deals.effects import apply_transition_effects
from app.services.deals.documents import DealDocumentService
from app.schemas.deal import DealDocumentRejectRequest


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


def make_deal(stage="draft", delivery_type="inmediata", **kwargs):
    deal = MagicMock()
    deal.id = 1
    deal.broker_id = 1
    deal.lead_id = 1
    deal.property_id = 1
    deal.stage = stage
    deal.delivery_type = delivery_type
    deal.bank_review_status = kwargs.get("bank_review_status", None)
    deal.jefatura_review_required = kwargs.get("jefatura_review_required", False)
    deal.jefatura_review_status = kwargs.get("jefatura_review_status", None)
    deal.cancellation_notes = kwargs.get("cancellation_notes", None)
    for ts_attr in ("created_at", "reserva_at", "bank_decision_at",
                    "promesa_signed_at", "escritura_signed_at", "cancelled_at"):
        setattr(deal, ts_attr, None)
    return deal


def make_db(doc_found: bool = True) -> AsyncMock:
    """DB where every document query returns found/not-found."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = MagicMock() if doc_found else None
    db.execute.return_value = result
    db.add = MagicMock()
    return db


def _ordered_db(responses: list) -> AsyncMock:
    """DB whose execute() returns each response in sequence."""
    db = AsyncMock()
    db.add = MagicMock()
    call_idx = [0]

    def _side_effect(_query):
        idx = call_idx[0]
        val = responses[idx] if idx < len(responses) else None
        call_idx[0] += 1
        result = MagicMock()
        result.scalar_one_or_none.return_value = val
        return result

    db.execute.side_effect = _side_effect
    return db


def _make_service_db(lead, prop, existing_deal=None) -> AsyncMock:
    """DB suitable for DealService.create: get() returns lead then prop,
    execute() returns existing_deal check result."""
    db = AsyncMock()
    db.get.side_effect = [lead, prop]
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_deal
    db.execute.return_value = result
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _make_lead(broker_id=1) -> MagicMock:
    lead = MagicMock()
    lead.broker_id = broker_id
    lead.id = 10
    return lead


def _make_property(broker_id=1, status="available") -> MagicMock:
    prop = MagicMock()
    prop.broker_id = broker_id
    prop.status = status
    prop.id = 20
    return prop


# ── TestDealServiceCreate ──────────────────────────────────────────────────────

class TestDealServiceCreate:

    def test_create_success(self):
        lead = _make_lead(broker_id=1)
        prop = _make_property(broker_id=1, status="available")
        db = _make_service_db(lead, prop, existing_deal=None)

        deal = _run(DealService.create(
            db, broker_id=1, lead_id=10, property_id=20,
            delivery_type="inmediata",
        ))

        assert deal.stage == "draft"
        assert deal.broker_id == 1
        assert deal.lead_id == 10
        assert deal.property_id == 20
        assert deal.delivery_type == "inmediata"
        assert deal.jefatura_review_required is False
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    def test_create_property_not_available(self):
        lead = _make_lead(broker_id=1)
        prop = _make_property(broker_id=1, status="reserved")
        db = _make_service_db(lead, prop)

        with pytest.raises(DealConflictError) as exc:
            _run(DealService.create(
                db, broker_id=1, lead_id=10, property_id=20,
                delivery_type="inmediata",
            ))
        assert exc.value.status_code == 409

    def test_create_lead_wrong_broker(self):
        lead = _make_lead(broker_id=99)  # wrong broker
        prop = _make_property(broker_id=1, status="available")
        db = AsyncMock()
        db.get.side_effect = [lead, prop]

        with pytest.raises(DealError) as exc:
            _run(DealService.create(
                db, broker_id=1, lead_id=10, property_id=20,
                delivery_type="inmediata",
            ))
        assert exc.value.status_code == 404

    def test_create_property_wrong_broker(self):
        lead = _make_lead(broker_id=1)
        prop = _make_property(broker_id=99, status="available")  # wrong broker
        db = AsyncMock()
        db.get.side_effect = [lead, prop]

        with pytest.raises(DealError) as exc:
            _run(DealService.create(
                db, broker_id=1, lead_id=10, property_id=20,
                delivery_type="inmediata",
            ))
        assert exc.value.status_code == 404

    def test_create_active_deal_conflict(self):
        lead = _make_lead(broker_id=1)
        prop = _make_property(broker_id=1, status="available")
        existing_deal_mock = MagicMock()  # simulate an active deal already exists
        db = _make_service_db(lead, prop, existing_deal=existing_deal_mock)

        with pytest.raises(DealConflictError) as exc:
            _run(DealService.create(
                db, broker_id=1, lead_id=10, property_id=20,
                delivery_type="inmediata",
            ))
        assert exc.value.status_code == 409

    def test_create_futura_sets_jefatura_required(self):
        lead = _make_lead(broker_id=1)
        prop = _make_property(broker_id=1, status="available")
        db = _make_service_db(lead, prop, existing_deal=None)

        deal = _run(DealService.create(
            db, broker_id=1, lead_id=10, property_id=20,
            delivery_type="futura",
        ))

        assert deal.jefatura_review_required is True
        assert deal.delivery_type == "futura"


# ── TestDealStateMachine ───────────────────────────────────────────────────────

class TestDealStateMachine:

    def test_draft_to_reserva_with_comprobante(self):
        deal = make_deal(stage="draft")
        _run(transition(deal, "reserva", make_db(doc_found=True)))
        assert deal.stage == "reserva"
        assert deal.reserva_at is not None

    def test_draft_to_reserva_missing_comprobante(self):
        deal = make_deal(stage="draft")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "reserva", make_db(doc_found=False)))
        assert exc.value.status_code == 422
        assert "comprobante" in exc.value.message.lower()

    def test_illegal_transition_raises(self):
        deal = make_deal(stage="draft")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "promesa_redaccion", AsyncMock()))
        assert exc.value.status_code == 422
        assert "draft" in exc.value.message

    def test_cancel_requires_reason(self):
        deal = make_deal(stage="reserva")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "cancelado", AsyncMock(), cancellation_reason=None))
        assert exc.value.status_code == 422

    def test_cancel_sets_timestamps(self):
        deal = make_deal(stage="reserva")
        _run(transition(deal, "cancelado", AsyncMock(), cancellation_reason="Sin fondos"))
        assert deal.stage == "cancelado"
        assert deal.cancelled_at is not None
        assert deal.cancellation_reason == "Sin fondos"

    def test_aprobacion_to_promesa_needs_bank_approval(self):
        deal = make_deal(stage="en_aprobacion_bancaria", bank_review_status="pendiente")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "promesa_redaccion", AsyncMock()))
        assert exc.value.status_code == 422
        assert "bancaria" in exc.value.message.lower()

    def test_aprobacion_to_promesa_futura_needs_jefatura(self):
        deal = make_deal(
            stage="en_aprobacion_bancaria",
            delivery_type="futura",
            bank_review_status="aprobado",
            jefatura_review_status=None,  # not approved yet
        )
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "promesa_redaccion", AsyncMock()))
        assert exc.value.status_code == 422
        assert "jefatura" in exc.value.message.lower()

    def test_terminal_stages_no_transitions(self):
        for terminal in ("escritura_firmada", "cancelado"):
            deal = make_deal(stage=terminal)
            with pytest.raises(DealError) as exc:
                _run(transition(deal, "reserva", AsyncMock()))
            assert exc.value.status_code == 422


# ── TestDealEffects ────────────────────────────────────────────────────────────

class TestDealEffects:

    def _run_effects(self, deal, from_stage, to_stage, responses):
        db = _ordered_db(responses)
        with patch("app.services.deals.effects.ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            _run(apply_transition_effects(deal, from_stage, to_stage, db))
        return db

    def test_reserva_effect_marks_property_reserved(self):
        deal = make_deal(stage="reserva")
        mock_prop = MagicMock()
        mock_prop.status = "available"
        mock_lead = MagicMock()
        mock_lead.pipeline_stage = "entrada"

        self._run_effects(deal, "draft", "reserva", [mock_prop, mock_lead])

        assert mock_prop.status == "reserved"

    def test_escritura_effect_marks_property_sold(self):
        deal = make_deal(stage="escritura_firmada")
        mock_prop = MagicMock()
        mock_prop.status = "reserved"
        mock_lead = MagicMock()
        mock_lead.pipeline_stage = "seguimiento"
        mock_lead.closed_at = None

        self._run_effects(deal, "promesa_firmada", "escritura_firmada", [mock_prop, mock_lead])

        assert mock_prop.status == "sold"
        assert mock_lead.pipeline_stage == "ganado"

    def test_cancelado_effect_marks_property_available(self):
        deal = make_deal(stage="cancelado")
        deal.cancellation_notes = "Test"
        mock_prop = MagicMock()
        mock_prop.status = "reserved"
        mock_lead = MagicMock()
        mock_lead.pipeline_stage = "seguimiento"
        mock_lead.closed_at = None

        self._run_effects(deal, "reserva", "cancelado", [mock_prop, mock_lead])

        assert mock_prop.status == "available"
        assert mock_lead.pipeline_stage == "perdido"

    def test_effects_idempotent(self):
        """Calling reserva effects twice: property ends up reserved, no error."""
        deal = make_deal(stage="reserva")
        mock_prop = MagicMock()
        mock_prop.status = "available"
        mock_lead = MagicMock()
        mock_lead.pipeline_stage = "entrada"

        # First call — sets property to reserved
        self._run_effects(deal, "draft", "reserva", [mock_prop, mock_lead])
        assert mock_prop.status == "reserved"

        # Second call — property already reserved; guard `prop.status != "reserved"` skips update
        self._run_effects(deal, "draft", "reserva", [mock_prop, mock_lead])
        assert mock_prop.status == "reserved"  # unchanged, no error


# ── TestDealDocumentService ────────────────────────────────────────────────────

class TestDealDocumentService:

    def test_upload_invalid_slot(self):
        db = AsyncMock()
        deal = make_deal()
        file = MagicMock()

        with pytest.raises(DealError) as exc:
            _run(DealDocumentService.upload(
                db, deal, slot="nonexistent", file=file,
            ))
        assert exc.value.status_code == 400
        assert "nonexistent" in exc.value.message

    def test_upload_ai_blocked_without_flag(self):
        """When uploaded_by_ai=True and config.ai_can_upload_deal_files=False, raise 403."""
        config_mock = MagicMock()
        config_mock.ai_can_upload_deal_files = False

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = config_mock

        db = AsyncMock()
        db.execute.return_value = result_mock

        deal = make_deal()
        file = MagicMock()

        with pytest.raises(DealError) as exc:
            _run(DealDocumentService.upload(
                db, deal, slot="comprobante_transferencia", file=file,
                uploaded_by_ai=True,
            ))
        assert exc.value.status_code == 403
        assert "IA" in exc.value.message

    def test_upload_ai_blocked_when_config_missing(self):
        """When uploaded_by_ai=True and BrokerLeadConfig doesn't exist, raise 403."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None  # no config row

        db = AsyncMock()
        db.execute.return_value = result_mock

        deal = make_deal()
        file = MagicMock()

        with pytest.raises(DealError) as exc:
            _run(DealDocumentService.upload(
                db, deal, slot="comprobante_transferencia", file=file,
                uploaded_by_ai=True,
            ))
        assert exc.value.status_code == 403

    def test_approve_idempotent(self):
        """Approving an already-approved document returns the same doc without error."""
        db = AsyncMock()
        deal = make_deal()
        doc = MagicMock()
        doc.status = "aprobado"

        result = _run(DealDocumentService.approve(
            db, doc, deal, reviewer_user_id=1,
        ))

        assert result is doc
        # Should not have modified status or called db.add
        db.add.assert_not_called()

    def test_reject_requires_notes(self):
        """DealDocumentRejectRequest.notes is required (non-Optional str)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DealDocumentRejectRequest()  # missing required `notes` field

    def test_reject_requires_notes_empty_string_allowed(self):
        """Empty string is technically valid for notes (str type, not min_length constrained)."""
        req = DealDocumentRejectRequest(notes="")
        assert req.notes == ""

    def test_reject_requires_notes_with_value(self):
        req = DealDocumentRejectRequest(notes="Documento ilegible")
        assert req.notes == "Documento ilegible"
