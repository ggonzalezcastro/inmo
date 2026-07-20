"""
Tests for call_purpose validation on Pipecat call endpoints and route ordering.

Run with:
    python -m pytest tests/routes/test_pipecat_call_purpose.py -v --noconftest
"""
import pytest
from pydantic import ValidationError

from app.routes.voice import PipecatCallRequest, PipecatBatchRequest, router
from app.models.voice_call import CallPurpose

ALL_PURPOSES = [p.value for p in CallPurpose]


class TestPipecatCallRequestValidation:
    def test_accepts_all_six_purposes(self):
        for purpose in ALL_PURPOSES:
            req = PipecatCallRequest(lead_id=1, call_purpose=purpose)
            assert req.call_purpose == CallPurpose(purpose)

    def test_purpose_is_optional(self):
        req = PipecatCallRequest(lead_id=1)
        assert req.call_purpose is None

    def test_rejects_free_text_purpose(self):
        with pytest.raises(ValidationError):
            PipecatCallRequest(lead_id=1, call_purpose="llamar para saludar")

    def test_batch_accepts_purpose(self):
        req = PipecatBatchRequest(lead_ids=[1, 2], call_purpose="reactivacion")
        assert req.call_purpose == CallPurpose.REACTIVACION

    def test_batch_rejects_invalid_purpose(self):
        with pytest.raises(ValidationError):
            PipecatBatchRequest(lead_ids=[1], call_purpose="foo")


class TestRouteOrdering:
    """GET /metrics and GET '' must resolve before the catch-all GET /{call_id}."""

    def _get_paths(self):
        return [
            getattr(r, "path", "")
            for r in router.routes
            if "GET" in (getattr(r, "methods", None) or [])
        ]

    def test_metrics_not_shadowed_by_call_id(self):
        paths = self._get_paths()
        assert paths.index("/metrics") < paths.index("/{call_id}")

    def test_list_endpoint_registered_before_call_id(self):
        paths = self._get_paths()
        assert paths.index("") < paths.index("/{call_id}")
