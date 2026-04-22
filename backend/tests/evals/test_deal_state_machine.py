"""
Eval tests for Deal state machine.
Validates correct pipeline transitions and business rules.
Run with: pytest tests/evals/test_deal_state_machine.py -v --noconftest
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.deals.exceptions import DealError
from app.services.deals.state_machine import ALLOWED_TRANSITIONS, transition


# ── Helpers ────────────────────────────────────────────────────────────────────

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
    # Explicitly set all timestamp attrs to None so _record_time_in_from_stage
    # doesn't mistake MagicMock auto-attributes for real datetime values.
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
    db.add = MagicMock()  # db.add is sync in SQLAlchemy
    return db


def _ordered_db(responses: list) -> AsyncMock:
    """DB whose execute() returns each response in sequence."""
    db = AsyncMock()
    db.add = MagicMock()  # db.add is sync in SQLAlchemy
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


def _run(coro):
    return asyncio.run(coro)


# ── 1. ALLOWED_TRANSITIONS structure ──────────────────────────────────────────

class TestAllowedTransitions:
    """Structural checks on the transition table."""

    def test_all_pipeline_stages_present(self):
        expected = {
            "draft", "reserva", "docs_pendientes", "en_aprobacion_bancaria",
            "promesa_redaccion", "promesa_firmada", "escritura_firmada", "cancelado",
        }
        assert expected == set(ALLOWED_TRANSITIONS.keys())

    def test_terminal_stages_have_no_outgoing_transitions(self):
        assert ALLOWED_TRANSITIONS["escritura_firmada"] == {}
        assert ALLOWED_TRANSITIONS["cancelado"] == {}

    def test_every_non_terminal_stage_can_cancel(self):
        non_terminal = [
            "draft", "reserva", "docs_pendientes", "en_aprobacion_bancaria",
            "promesa_redaccion", "promesa_firmada",
        ]
        for stage in non_terminal:
            assert "cancelado" in ALLOWED_TRANSITIONS[stage], (
                f"Stage '{stage}' is missing the 'cancelado' transition"
            )


# ── 2. Illegal transitions ─────────────────────────────────────────────────────

class TestIllegalTransitions:
    """Transitions that skip stages or go backwards must raise DealError."""

    def test_draft_to_promesa_redaccion_raises(self):
        deal = make_deal(stage="draft")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "promesa_redaccion", AsyncMock()))
        assert exc.value.status_code == 422

    def test_draft_to_escritura_firmada_raises(self):
        deal = make_deal(stage="draft")
        with pytest.raises(DealError):
            _run(transition(deal, "escritura_firmada", AsyncMock()))

    def test_reserva_to_draft_raises(self):
        deal = make_deal(stage="reserva")
        with pytest.raises(DealError):
            _run(transition(deal, "draft", AsyncMock()))

    def test_docs_pendientes_to_promesa_firmada_raises(self):
        deal = make_deal(stage="docs_pendientes")
        with pytest.raises(DealError):
            _run(transition(deal, "promesa_firmada", AsyncMock()))

    def test_escritura_firmada_is_terminal(self):
        deal = make_deal(stage="escritura_firmada")
        with pytest.raises(DealError):
            _run(transition(deal, "cancelado", AsyncMock(), cancellation_reason="test"))

    def test_cancelado_is_terminal(self):
        deal = make_deal(stage="cancelado")
        with pytest.raises(DealError):
            _run(transition(deal, "reserva", AsyncMock()))


# ── 3. Cancellation guard ──────────────────────────────────────────────────────

class TestCancellationGuard:

    def test_cancel_without_reason_raises_422(self):
        deal = make_deal(stage="reserva")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "cancelado", AsyncMock(), cancellation_reason=None))
        assert exc.value.status_code == 422
        assert "motivo" in exc.value.message.lower()

    def test_cancel_with_reason_updates_stage(self):
        deal = make_deal(stage="reserva")
        _run(transition(deal, "cancelado", AsyncMock(), cancellation_reason="Cliente desistió"))
        assert deal.stage == "cancelado"
        assert deal.cancellation_reason == "Cliente desistió"

    def test_cancel_from_docs_pendientes(self):
        deal = make_deal(stage="docs_pendientes")
        _run(transition(deal, "cancelado", AsyncMock(), cancellation_reason="Problema financiero"))
        assert deal.stage == "cancelado"

    def test_cancel_from_promesa_firmada(self):
        deal = make_deal(stage="promesa_firmada")
        _run(transition(deal, "cancelado", AsyncMock(), cancellation_reason="Acuerdo roto"))
        assert deal.stage == "cancelado"


# ── 4. Guard: draft → reserva ─────────────────────────────────────────────────

class TestGuardDraftToReserva:
    """comprobante_transferencia document required."""

    def test_missing_comprobante_raises_422(self):
        deal = make_deal(stage="draft")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "reserva", make_db(doc_found=False)))
        assert exc.value.status_code == 422

    def test_with_comprobante_advances(self):
        deal = make_deal(stage="draft")
        _run(transition(deal, "reserva", make_db(doc_found=True)))
        assert deal.stage == "reserva"

    def test_timestamps_set_on_reserva(self):
        deal = make_deal(stage="draft")
        _run(transition(deal, "reserva", make_db(doc_found=True)))
        assert deal.reserva_at is not None


# ── 5. Guard: docs_pendientes → en_aprobacion_bancaria ────────────────────────

class TestGuardDocsToAprobacion:
    """All required non-optional docs must be 'aprobado'."""

    def test_missing_required_doc_raises_422(self):
        deal = make_deal(stage="docs_pendientes", delivery_type="inmediata")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "en_aprobacion_bancaria", make_db(doc_found=False)))
        assert exc.value.status_code == 422

    def test_all_docs_approved_advances(self):
        deal = make_deal(stage="docs_pendientes", delivery_type="inmediata")
        _run(transition(deal, "en_aprobacion_bancaria", make_db(doc_found=True)))
        assert deal.stage == "en_aprobacion_bancaria"

    def test_missing_doc_futura_raises(self):
        deal = make_deal(stage="docs_pendientes", delivery_type="futura")
        with pytest.raises(DealError):
            _run(transition(deal, "en_aprobacion_bancaria", make_db(doc_found=False)))


# ── 6. Guard: en_aprobacion_bancaria → promesa_redaccion ──────────────────────

class TestGuardAprobacionToPromesa:
    """Bank must be approved; futura also needs jefatura approval."""

    def test_bank_pendiente_raises(self):
        deal = make_deal(stage="en_aprobacion_bancaria", bank_review_status="pendiente")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "promesa_redaccion", AsyncMock()))
        assert exc.value.status_code == 422

    def test_bank_none_raises(self):
        deal = make_deal(stage="en_aprobacion_bancaria", bank_review_status=None)
        with pytest.raises(DealError):
            _run(transition(deal, "promesa_redaccion", AsyncMock()))

    def test_bank_aprobado_inmediata_advances(self):
        deal = make_deal(
            stage="en_aprobacion_bancaria",
            bank_review_status="aprobado",
            delivery_type="inmediata",
        )
        _run(transition(deal, "promesa_redaccion", AsyncMock()))
        assert deal.stage == "promesa_redaccion"

    def test_futura_missing_jefatura_raises(self):
        deal = make_deal(
            stage="en_aprobacion_bancaria",
            bank_review_status="aprobado",
            delivery_type="futura",
            jefatura_review_status="pendiente",
        )
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "promesa_redaccion", AsyncMock()))
        assert exc.value.status_code == 422

    def test_futura_jefatura_none_raises(self):
        deal = make_deal(
            stage="en_aprobacion_bancaria",
            bank_review_status="aprobado",
            delivery_type="futura",
            jefatura_review_status=None,
        )
        with pytest.raises(DealError):
            _run(transition(deal, "promesa_redaccion", AsyncMock()))

    def test_futura_jefatura_aprobado_advances(self):
        deal = make_deal(
            stage="en_aprobacion_bancaria",
            bank_review_status="aprobado",
            delivery_type="futura",
            jefatura_review_status="aprobado",
        )
        _run(transition(deal, "promesa_redaccion", AsyncMock()))
        assert deal.stage == "promesa_redaccion"


# ── 7. Happy path — inmediata ──────────────────────────────────────────────────

class TestHappyPathInmediata:
    """Full pipeline draft → escritura_firmada for delivery_type=inmediata."""

    PIPELINE = [
        ("draft",                  "reserva",                  {}),
        ("reserva",                "docs_pendientes",          {}),
        ("docs_pendientes",        "en_aprobacion_bancaria",   {}),
        ("en_aprobacion_bancaria", "promesa_redaccion",        {"bank_review_status": "aprobado"}),
        ("promesa_redaccion",      "promesa_firmada",          {}),
        ("promesa_firmada",        "escritura_firmada",        {}),
    ]

    def test_each_stage_transition_succeeds(self):
        for from_stage, to_stage, extras in self.PIPELINE:
            deal = make_deal(stage=from_stage, delivery_type="inmediata", **extras)
            _run(transition(deal, to_stage, make_db(doc_found=True)))
            assert deal.stage == to_stage, (
                f"Stage after transition should be {to_stage}, got {deal.stage}"
            )

    def test_escritura_firmada_effects_lead_ganado_property_sold(self):
        """apply_transition_effects(escritura_firmada) → lead=ganado, prop=sold."""
        from app.services.deals.effects import apply_transition_effects

        deal = make_deal(stage="escritura_firmada")

        mock_lead = MagicMock()
        mock_lead.pipeline_stage = "seguimiento"
        mock_lead.closed_at = None

        mock_prop = MagicMock()
        mock_prop.status = "reserved"

        # Effects queries: 1st=Property, 2nd=Lead (ActivityLog uses db.add, not execute)
        db = _ordered_db([mock_prop, mock_lead])

        with patch("app.services.deals.effects.ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            _run(apply_transition_effects(deal, "promesa_firmada", "escritura_firmada", db))

        assert mock_lead.pipeline_stage == "ganado"
        assert mock_prop.status == "sold"


# ── 8. Happy path — futura ─────────────────────────────────────────────────────

class TestHappyPathFutura:
    """Futura pipeline requires jefatura_review_status='aprobado' before promesa."""

    def test_futura_pipeline_without_jefatura_is_blocked(self):
        deal = make_deal(
            stage="en_aprobacion_bancaria",
            bank_review_status="aprobado",
            delivery_type="futura",
            jefatura_review_status=None,
        )
        with pytest.raises(DealError):
            _run(transition(deal, "promesa_redaccion", AsyncMock()))

    def test_futura_pipeline_with_jefatura_aprobado_advances(self):
        deal = make_deal(
            stage="en_aprobacion_bancaria",
            bank_review_status="aprobado",
            delivery_type="futura",
            jefatura_review_status="aprobado",
        )
        _run(transition(deal, "promesa_redaccion", AsyncMock()))
        assert deal.stage == "promesa_redaccion"

    def test_futura_full_pipeline_except_aprobacion(self):
        """All stages except en_aprobacion→promesa_redaccion use same logic as inmediata."""
        stages_before = [
            ("draft",       "reserva",           {}),
            ("reserva",     "docs_pendientes",   {}),
            ("docs_pendientes", "en_aprobacion_bancaria", {}),
        ]
        stages_after = [
            ("promesa_redaccion", "promesa_firmada",    {}),
            ("promesa_firmada",   "escritura_firmada",  {}),
        ]
        for from_stage, to_stage, extras in stages_before + stages_after:
            deal = make_deal(stage=from_stage, delivery_type="futura", **extras)
            _run(transition(deal, to_stage, make_db(doc_found=True)))
            assert deal.stage == to_stage


# ── 9. Cancellation effects ────────────────────────────────────────────────────

class TestCancellationEffects:
    """Cancellation → property=available, lead=perdido."""

    def _cancel_effects(self, from_stage: str):
        from app.services.deals.effects import apply_transition_effects

        deal = make_deal(stage="cancelado")
        deal.cancellation_notes = "Test cancel"

        mock_prop = MagicMock()
        mock_prop.status = "reserved"

        mock_lead = MagicMock()
        mock_lead.pipeline_stage = "seguimiento"
        mock_lead.closed_at = None

        db = _ordered_db([mock_prop, mock_lead])

        with patch("app.services.deals.effects.ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            _run(apply_transition_effects(deal, from_stage, "cancelado", db))

        return mock_lead, mock_prop

    def test_cancel_from_reserva_resets_property(self):
        _, prop = self._cancel_effects("reserva")
        assert prop.status == "available"

    def test_cancel_from_reserva_marks_lead_perdido(self):
        lead, _ = self._cancel_effects("reserva")
        assert lead.pipeline_stage == "perdido"

    def test_cancel_from_promesa_firmada_resets_property(self):
        _, prop = self._cancel_effects("promesa_firmada")
        assert prop.status == "available"

    def test_cancel_from_promesa_firmada_marks_lead_perdido(self):
        lead, _ = self._cancel_effects("promesa_firmada")
        assert lead.pipeline_stage == "perdido"

    def test_cancel_without_reason_raises(self):
        deal = make_deal(stage="reserva")
        with pytest.raises(DealError) as exc:
            _run(transition(deal, "cancelado", AsyncMock(), cancellation_reason=None))
        assert exc.value.status_code == 422
