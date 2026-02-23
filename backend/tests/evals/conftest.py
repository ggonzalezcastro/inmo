"""
Shared fixtures for eval tests (TASK-025).

LLM-based metrics (AnswerRelevancyMetric, FaithfulnessMetric) require
an OpenAI or Confident AI key.  To enable them:

    EVAL_LLM_ENABLED=true OPENAI_API_KEY=sk-... pytest tests/evals/

Deterministic metrics (DicomRuleMetric, TaskCompletionMetric) always run.
"""
from __future__ import annotations

import os
import pytest
from typing import Any

from tests.evals.dataset import load_dataset, load_violation_cases, load_compliant_cases

# ── Markers ───────────────────────────────────────────────────────────────────

EVAL_LLM_ENABLED = os.getenv("EVAL_LLM_ENABLED", "false").lower() == "true"

skip_if_no_llm_eval = pytest.mark.skipif(
    not EVAL_LLM_ENABLED,
    reason=(
        "Set EVAL_LLM_ENABLED=true and OPENAI_API_KEY=... to run "
        "LLM-judge evaluation tests"
    ),
)


# ── deepeval LLMTestCase builder ──────────────────────────────────────────────

def make_test_case(entry: dict[str, Any]):
    """Convert a dataset entry to a deepeval LLMTestCase."""
    try:
        from deepeval.test_case import LLMTestCase
    except ImportError:
        return None

    labels = entry.get("labels", {})
    return LLMTestCase(
        input=entry["input"],
        actual_output=entry["actual_output"],
        expected_output=entry.get("expected_output", ""),
        context=entry.get("context") or [],
        retrieval_context=entry.get("context") or [],
        additional_metadata={
            "conversation_id": entry["id"],
            "category": entry["category"],
            "pipeline_stage": entry["pipeline_stage"],
            "task_action_expected": labels.get("task_action_expected", ""),
            "task_action_completed": labels.get("task_action_completed", True),
            "dicom_violation": labels.get("dicom_violation", False),
        },
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def all_conversations():
    """Full dataset (51 entries)."""
    return load_dataset()


@pytest.fixture(scope="session")
def compliant_conversations():
    """Dataset entries that should pass ALL metrics (dicom_violation=False)."""
    return load_compliant_cases()


@pytest.fixture(scope="session")
def violation_conversations():
    """Dataset entries that represent DICOM violations (dicom_violation=True)."""
    return load_violation_cases()


@pytest.fixture(scope="session")
def all_test_cases(all_conversations):
    """deepeval LLMTestCase objects for all 51 conversations."""
    try:
        return [tc for entry in all_conversations if (tc := make_test_case(entry))]
    except ImportError:
        return []


@pytest.fixture(scope="session")
def compliant_test_cases(compliant_conversations):
    """deepeval LLMTestCase objects for compliant conversations only."""
    try:
        return [tc for entry in compliant_conversations if (tc := make_test_case(entry))]
    except ImportError:
        return []


@pytest.fixture(scope="session")
def violation_test_cases(violation_conversations):
    """deepeval LLMTestCase objects for DICOM violation conversations."""
    try:
        return [tc for entry in violation_conversations if (tc := make_test_case(entry))]
    except ImportError:
        return []
