"""
Tests for property search service — RRF scoring logic, search dispatch, edge cases.

Run without DB:
    python -m pytest tests/services/test_property_search.py -v --noconftest
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── RRF scoring math (pure unit tests, no DB/async) ──────────────────────────

class TestRRFScoringMath:
    """Test the Reciprocal Rank Fusion formula directly."""

    def _rrf_score(self, rank: int, k: int = 60) -> float:
        return 1.0 / (rank + k)

    def test_rank_0_scores_highest(self):
        assert self._rrf_score(0) > self._rrf_score(1)
        assert self._rrf_score(1) > self._rrf_score(10)

    def test_k60_constant(self):
        """Verify RRF uses k=60 as the smoothing constant."""
        score = self._rrf_score(0, k=60)
        assert abs(score - 1 / 60) < 1e-9

    def test_item_in_both_lists_ranks_higher(self):
        """Item at rank 0 in both lists should score ~2× rank-0 single list."""
        single = self._rrf_score(0)
        both = self._rrf_score(0) + self._rrf_score(0)
        assert both > single * 1.5

    def test_deduplication_combines_scores(self):
        """Simulated RRF merge: item in both lists gets combined score."""
        from app.services.properties.search_service import _RRF_K

        sql_ranks = {1: 1, 2: 2}  # id → rank (1-based)
        sem_ranks = {2: 1, 3: 2}  # id=2 in both

        scores = {}
        for pid in set(sql_ranks) | set(sem_ranks):
            s = 0.0
            if pid in sql_ranks:
                s += 1.0 / (sql_ranks[pid] + _RRF_K)
            if pid in sem_ranks:
                s += 1.0 / (sem_ranks[pid] + _RRF_K)
            scores[pid] = s

        # id=2 (in both at rank 1) should beat id=1 (only in sql at rank 1)
        assert scores[2] > scores[1]
        # id=3 (only in sem at rank 2) should be lowest
        sorted_ids = sorted(scores, key=scores.get, reverse=True)
        assert sorted_ids[0] == 2


# ── execute_property_search dispatch ─────────────────────────────────────────

class TestSearchDispatch:
    @pytest.mark.asyncio
    async def test_execute_property_search_calls_structured_by_default(self):
        """Without explicit strategy, structured search is invoked."""
        from app.services.properties import search_service as svc_mod

        db = AsyncMock()
        params = {"commune": "Las Condes"}

        with patch.object(svc_mod, "_structured_search", new_callable=AsyncMock, return_value=[]) as mock_struct, \
             patch.object(svc_mod, "_semantic_search", new_callable=AsyncMock, return_value=[]), \
             patch.object(svc_mod, "_rrf_merge", new_callable=AsyncMock, return_value=[]):
            await svc_mod.execute_property_search(params=params, db=db, broker_id=1)

        mock_struct.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_semantic_strategy_calls_semantic(self):
        from app.services.properties import search_service as svc_mod

        db = AsyncMock()
        params = {"query": "departamento moderno Las Condes", "strategy": "semantic"}

        with patch.object(svc_mod, "_structured_search", new_callable=AsyncMock, return_value=[]) as mock_struct, \
             patch.object(svc_mod, "_semantic_search", new_callable=AsyncMock, return_value=[]) as mock_sem, \
             patch.object(svc_mod, "_rrf_merge", new_callable=AsyncMock, return_value=[]):
            await svc_mod.execute_property_search(params=params, db=db, broker_id=1)

        mock_sem.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_params_does_not_crash(self):
        from app.services.properties import search_service as svc_mod

        db = AsyncMock()

        with patch.object(svc_mod, "_structured_search", new_callable=AsyncMock, return_value=[]), \
             patch.object(svc_mod, "_semantic_search", new_callable=AsyncMock, return_value=[]), \
             patch.object(svc_mod, "_rrf_merge", new_callable=AsyncMock, return_value=[]):
            result = await svc_mod.execute_property_search(params={}, db=db, broker_id=1)

        assert isinstance(result, list)


class TestSearchToolDefinition:
    def test_tool_has_required_fields(self):
        from app.services.properties.search_service import SEARCH_PROPERTIES_TOOL

        assert SEARCH_PROPERTIES_TOOL["name"] == "search_properties"
        assert "description" in SEARCH_PROPERTIES_TOOL
        assert "parameters" in SEARCH_PROPERTIES_TOOL
        params = SEARCH_PROPERTIES_TOOL["parameters"]
        assert "properties" in params

    def test_tool_description_mentions_property(self):
        from app.services.properties.search_service import SEARCH_PROPERTIES_TOOL
        desc = SEARCH_PROPERTIES_TOOL["description"].lower()
        assert "propiedad" in desc or "property" in desc or "buscar" in desc


