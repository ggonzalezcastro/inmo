"""
Unit tests for Deal and DealDocument models.
No DB required — run with: pytest tests/models/test_deal.py -v --noconftest
"""
import pytest
from app.models.deal import Deal, DEAL_STAGES, DELIVERY_TYPES
from app.models.deal_document import DealDocument, DOCUMENT_STATUSES
from app.services.deals.slots import (
    SLOT_DEFINITIONS,
    get_required_slots_for_stage,
    get_all_required_slots_for_promesa,
    is_slot_key_valid,
    SLOT_STAGE_ORDER,
)


class TestDealStages:
    def test_all_stages_defined(self):
        expected = ["draft", "reserva", "docs_pendientes", "en_aprobacion_bancaria",
                    "promesa_redaccion", "promesa_firmada", "escritura_firmada", "cancelado"]
        assert set(DEAL_STAGES) == set(expected)

    def test_delivery_types_defined(self):
        assert set(DELIVERY_TYPES) == {"inmediata", "futura", "desconocida"}

    def test_deal_has_required_columns(self):
        cols = {c.key for c in Deal.__table__.columns}
        for required in ["broker_id", "lead_id", "property_id", "stage", "delivery_type",
                         "bank_review_status", "jefatura_review_required", "cancelled_at",
                         "cancellation_reason", "escritura_planned_date"]:
            assert required in cols, f"Missing column: {required}"

    def test_deal_stage_default(self):
        col = Deal.__table__.c["stage"]
        assert col.default.arg == "draft"

    def test_deal_jefatura_default_false(self):
        col = Deal.__table__.c["jefatura_review_required"]
        assert col.default.arg == False

    def test_partial_unique_index_exists(self):
        index_names = {idx.name for idx in Deal.__table__.indexes}
        assert "uq_deal_active_property" in index_names

    def test_deal_relationships(self):
        rel_keys = {r.key for r in Deal.__mapper__.relationships}
        for rel in ["broker", "lead", "property", "created_by", "documents"]:
            assert rel in rel_keys


class TestDealDocumentModel:
    def test_document_statuses_defined(self):
        assert set(DOCUMENT_STATUSES) == {"pendiente", "recibido", "aprobado", "rechazado"}

    def test_deal_document_has_required_columns(self):
        cols = {c.key for c in DealDocument.__table__.columns}
        for required in ["deal_id", "slot", "slot_index", "co_titular_index", "status",
                         "storage_key", "sha256", "uploaded_by_ai", "review_notes"]:
            assert required in cols, f"Missing column: {required}"

    def test_uploaded_by_ai_default_false(self):
        col = DealDocument.__table__.c["uploaded_by_ai"]
        assert col.default.arg == False

    def test_status_default_pendiente(self):
        col = DealDocument.__table__.c["status"]
        assert col.default.arg == "pendiente"


class TestSlotDefinitions:
    def test_all_required_slot_keys_present(self):
        required_keys = [
            "comprobante_transferencia", "ci_anverso", "ci_reverso",
            "cmf_deuda", "liquidacion_sueldo", "afp_cotizaciones",
            "antiguedad_laboral", "cert_matrimonio",
            "pre_aprobacion_banco", "aprobacion_banco",
            "borrador_promesa", "promesa_firmada", "escritura",
        ]
        for key in required_keys:
            assert is_slot_key_valid(key), f"Missing slot: {key}"

    def test_cert_matrimonio_is_optional(self):
        assert SLOT_DEFINITIONS["cert_matrimonio"].optional is True

    def test_liquidacion_max_count_3(self):
        assert SLOT_DEFINITIONS["liquidacion_sueldo"].max_count == 3

    def test_reserva_stage_slots(self):
        slots = get_required_slots_for_stage("reserva")
        keys = {s.slot_key for s in slots}
        assert "comprobante_transferencia" in keys

    def test_promesa_inmediata_requires_aprobacion_banco(self):
        slots = get_all_required_slots_for_promesa("inmediata")
        keys = {s.slot_key for s in slots}
        assert "aprobacion_banco" in keys
        assert "pre_aprobacion_banco" not in keys

    def test_promesa_futura_requires_pre_aprobacion(self):
        slots = get_all_required_slots_for_promesa("futura")
        keys = {s.slot_key for s in slots}
        assert "pre_aprobacion_banco" in keys
        assert "aprobacion_banco" not in keys

    def test_desconocida_no_bancaria_slots(self):
        slots = get_all_required_slots_for_promesa("desconocida")
        keys = {s.slot_key for s in slots}
        assert "pre_aprobacion_banco" not in keys
        assert "aprobacion_banco" not in keys

    def test_invalid_slot_key(self):
        assert is_slot_key_valid("nonexistent_slot") is False

    def test_slot_stage_order_is_ordered(self):
        assert SLOT_STAGE_ORDER.index("draft") < SLOT_STAGE_ORDER.index("escritura_firmada")
