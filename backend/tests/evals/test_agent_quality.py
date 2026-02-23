"""
Agent quality evaluation tests (TASK-025).

Metrics evaluated
-----------------
1. answer_relevancy       — ¿la respuesta es relevante al estado de la conversación?
   Implementation: deepeval AnswerRelevancyMetric (LLM judge, optional)

2. faithfulness           — ¿no inventa datos financieros?
   Implementation: deepeval FaithfulnessMetric (LLM judge, optional)

3. task_completion        — ¿preguntó el dato correcto en el turno esperado?
   Implementation: TaskCompletionMetric (deterministic, always runs)

4. dicom_rule_adherence   — regla crítica de DICOM respetada.
   Implementation: DicomRuleMetric (deterministic, always runs)

Running
-------
    # Deterministic tests only (no API key needed):
    pytest tests/evals/test_agent_quality.py

    # With LLM-judge metrics:
    EVAL_LLM_ENABLED=true OPENAI_API_KEY=sk-... pytest tests/evals/test_agent_quality.py
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from tests.evals.conftest import skip_if_no_llm_eval
from tests.evals.dataset import load_dataset, load_violation_cases, load_compliant_cases
from tests.evals.metrics.dicom_rule import DicomRuleMetric, check_dicom_rule
from tests.evals.metrics.task_completion import TaskCompletionMetric, check_task_completion

# ── Baseline thresholds (documented in docs/testing/eval_baseline.md) ─────────
# Measured on 2026-02-22 against 51 labeled conversations.
# dicom_rule & task_completion reflect real regex coverage;
# answer_relevancy & faithfulness are LLM-label-based proxies.
BASELINE = {
    "answer_relevancy": 0.85,    # 0.8510 measured (label proxy)
    "faithfulness": 0.80,        # 0.8039 measured (label proxy, 10 violation cases)
    "task_completion": 0.84,     # 0.8431 measured (regex detection)
    "dicom_rule_adherence": 0.80,  # 0.8039 measured (10 violation cases score 0)
}
REGRESSION_TOLERANCE = 0.05  # 5% drop triggers failure


# ══════════════════════════════════════════════════════════════════════════════
# 1. Dataset integrity checks
# ══════════════════════════════════════════════════════════════════════════════

class TestDatasetIntegrity:
    """Validate the eval dataset structure before running metrics."""

    def test_dataset_has_minimum_entries(self):
        data = load_dataset()
        assert len(data) >= 50, f"Dataset must have 50+ entries, got {len(data)}"

    def test_all_entries_have_required_fields(self):
        required = {"id", "category", "pipeline_stage", "input", "actual_output", "labels"}
        for entry in load_dataset():
            missing = required - set(entry.keys())
            assert not missing, f"Entry {entry.get('id')} missing: {missing}"

    def test_all_labels_have_required_keys(self):
        label_keys = {
            "answer_relevance",
            "is_faithful",
            "task_action_expected",
            "task_action_completed",
            "dicom_violation",
        }
        for entry in load_dataset():
            missing = label_keys - set(entry["labels"].keys())
            assert not missing, (
                f"Entry {entry['id']} missing label keys: {missing}"
            )

    def test_violation_cases_exist(self):
        violations = load_violation_cases()
        assert len(violations) >= 5, (
            f"Expected 5+ DICOM violation cases, got {len(violations)}"
        )

    def test_compliant_cases_exist(self):
        compliant = load_compliant_cases()
        assert len(compliant) >= 40, (
            f"Expected 40+ compliant cases, got {len(compliant)}"
        )

    def test_unique_ids(self):
        data = load_dataset()
        ids = [e["id"] for e in data]
        assert len(ids) == len(set(ids)), "Dataset has duplicate IDs"

    def test_categories_present(self):
        data = load_dataset()
        categories = {e["category"] for e in data}
        expected_categories = {
            "initial_greeting",
            "name_collection",
            "contact_collection",
            "budget_inquiry",
            "dicom_inquiry",
            "dicom_violation",
            "appointment_scheduling",
            "property_questions",
        }
        missing = expected_categories - categories
        assert not missing, f"Missing categories in dataset: {missing}"


# ══════════════════════════════════════════════════════════════════════════════
# 2. DICOM Rule Adherence (deterministic — always runs)
# ══════════════════════════════════════════════════════════════════════════════

class TestDicomRuleAdherence:
    """
    Metric 4: dicom_rule_adherence.

    Expected behaviour:
    - Compliant cases (dicom_violation=False) → score == 1.0
    - Violation cases (dicom_violation=True)  → score == 0.0
    """

    def test_compliant_cases_pass_dicom_rule(self):
        metric = DicomRuleMetric(threshold=1.0)
        compliant = load_compliant_cases()
        failures = []
        for entry in compliant:
            result = check_dicom_rule(entry["input"], entry["actual_output"])
            if not result["success"]:
                failures.append(
                    f"{entry['id']} — {result['reason']}"
                )
        assert not failures, (
            f"{len(failures)} compliant case(s) incorrectly flagged as violations:\n"
            + "\n".join(failures)
        )

    def test_violation_cases_fail_dicom_rule(self):
        violations = load_violation_cases()
        detected = []
        missed = []
        for entry in violations:
            result = check_dicom_rule(entry["input"], entry["actual_output"])
            if result["success"]:
                missed.append(f"{entry['id']}: {result['reason']}")
            else:
                detected.append(entry["id"])
        # All 10 violation cases should be detected (100% precision)
        assert not missed, (
            f"DicomRuleMetric missed {len(missed)} violation(s):\n"
            + "\n".join(missed)
        )

    def test_dicom_metric_score_range(self):
        """All scores must be either 0.0 or 1.0."""
        for entry in load_dataset():
            result = check_dicom_rule(entry["input"], entry["actual_output"])
            assert result["score"] in (0.0, 1.0), (
                f"Unexpected score {result['score']} for {entry['id']}"
            )

    def test_dicom_baseline_not_regressed(self):
        """
        Overall dicom_rule_adherence score must be >= BASELINE - TOLERANCE.
        Baseline: 0.90 (90% of cases pass). Tolerance: 5%.
        """
        data = load_dataset()
        scores = [
            check_dicom_rule(e["input"], e["actual_output"])["score"]
            for e in data
        ]
        avg_score = sum(scores) / len(scores)
        threshold = BASELINE["dicom_rule_adherence"] - REGRESSION_TOLERANCE
        assert avg_score >= threshold, (
            f"dicom_rule_adherence regressed: {avg_score:.3f} < {threshold:.3f} "
            f"(baseline={BASELINE['dicom_rule_adherence']}, tolerance={REGRESSION_TOLERANCE})"
        )

    # ── Specific known-good cases ──────────────────────────────────────────────

    def test_agent_with_clean_dicom_passes(self):
        result = check_dicom_rule(
            input_text="Sí, tengo DICOM limpio",
            output_text="Perfecto. Con DICOM limpio podemos avanzar. ¿Tienes disponibilidad esta semana?",
        )
        assert result["success"], result["reason"]

    def test_agent_advising_regularization_passes(self):
        result = check_dicom_rule(
            input_text="Tengo una deuda en DICOM",
            output_text="Te recomiendo regularizar la deuda antes de iniciar el proceso. Cuando estés en orden, retomamos.",
        )
        assert result["success"], result["reason"]

    def test_agent_promising_credit_with_dicom_fails(self):
        result = check_dicom_rule(
            input_text="Estoy en DICOM con deuda activa",
            output_text="No hay problema, calificas para el crédito hipotecario igual.",
        )
        assert not result["success"], "Should have detected DICOM violation"

    def test_agent_pre_approving_with_morosidad_fails(self):
        result = check_dicom_rule(
            input_text="Tengo morosidad en un banco",
            output_text="Estás aprobado con nosotros, la morosidad no es problema.",
        )
        assert not result["success"], "Should have detected pre-approval violation"

    def test_no_debt_context_trivially_passes(self):
        result = check_dicom_rule(
            input_text="Hola, me llamo María",
            output_text="Mucho gusto, María. ¿Me puedes dar tu teléfono?",
        )
        assert result["success"], result["reason"]


# ══════════════════════════════════════════════════════════════════════════════
# 3. Task Completion (deterministic — always runs)
# ══════════════════════════════════════════════════════════════════════════════

class TestTaskCompletion:
    """
    Metric 3: task_completion.

    The agent should perform the expected conversational action at each turn.
    """

    def test_ask_name_detected(self):
        result = check_task_completion(
            "ask_name",
            "¡Hola! Soy Sofía. ¿Cuál es tu nombre?",
        )
        assert result["success"], result["reason"]

    def test_ask_phone_detected(self):
        result = check_task_completion(
            "ask_phone",
            "Mucho gusto, Juan. ¿Me das tu número de WhatsApp?",
        )
        assert result["success"], result["reason"]

    def test_ask_dicom_detected(self):
        result = check_task_completion(
            "ask_dicom",
            "Para continuar, necesito preguntarte si tienes DICOM activo.",
        )
        assert result["success"], result["reason"]

    def test_ask_budget_detected(self):
        result = check_task_completion(
            "ask_budget",
            "¿Cuál es tu presupuesto aproximado para la propiedad?",
        )
        assert result["success"], result["reason"]

    def test_schedule_visit_detected(self):
        result = check_task_completion(
            "schedule_visit",
            "Perfecto, podemos agendar una visita. ¿Tienes disponibilidad el sábado?",
        )
        assert result["success"], result["reason"]

    def test_missing_action_not_detected(self):
        result = check_task_completion(
            "ask_dicom",
            "¡Qué bueno que te interesa nuestra oferta!",
        )
        assert not result["success"], "Should have detected missing DICOM question"

    def test_name_action_not_detected_when_absent(self):
        result = check_task_completion(
            "ask_name",
            "Tu presupuesto es de 3000 UF, tenemos opciones para ti.",
        )
        assert not result["success"], "ask_name should not match budget discussion"

    def test_dataset_task_completion_rate(self):
        """
        task_completion rate across dataset must be >= BASELINE - TOLERANCE.
        Baseline: 0.88. Tolerance: 5%.
        """
        data = load_dataset()
        scores = []
        for entry in data:
            action = entry["labels"].get("task_action_expected", "")
            if not action:
                continue
            result = check_task_completion(action, entry["actual_output"])
            scores.append(result["score"])

        if not scores:
            pytest.skip("No task action expectations in dataset")

        avg_score = sum(scores) / len(scores)
        threshold = BASELINE["task_completion"] - REGRESSION_TOLERANCE

        assert avg_score >= threshold, (
            f"task_completion regressed: {avg_score:.3f} < {threshold:.3f} "
            f"(baseline={BASELINE['task_completion']}, tolerance={REGRESSION_TOLERANCE})"
        )

    def test_compliant_cases_complete_their_tasks(self):
        """
        For cases explicitly labeled task_action_completed=True,
        the metric must agree.
        """
        compliant = [
            e for e in load_dataset()
            if e["labels"].get("task_action_completed") is True
            and e["labels"].get("task_action_expected")
        ]
        mismatches = []
        for entry in compliant:
            action = entry["labels"]["task_action_expected"]
            result = check_task_completion(action, entry["actual_output"])
            if not result["success"]:
                mismatches.append(
                    f"{entry['id']} (action={action}): {result['reason']}"
                )
        # Allow up to 15% miss rate (some actions are hard to detect with regex)
        allowed_misses = int(len(compliant) * 0.15)
        assert len(mismatches) <= allowed_misses, (
            f"Too many task completion mismatches ({len(mismatches)}):\n"
            + "\n".join(mismatches[:10])
        )


# ══════════════════════════════════════════════════════════════════════════════
# 4. Answer Relevancy (LLM judge — optional)
# ══════════════════════════════════════════════════════════════════════════════

class TestAnswerRelevancy:
    """
    Metric 1: answer_relevancy.

    Requires EVAL_LLM_ENABLED=true + OPENAI_API_KEY.
    Skipped in CI unless explicitly enabled.
    """

    @skip_if_no_llm_eval
    def test_answer_relevancy_baseline(self, all_test_cases):
        """Run AnswerRelevancyMetric across all cases; avg must meet baseline."""
        if not all_test_cases:
            pytest.skip("deepeval not installed")

        try:
            from deepeval.metrics import AnswerRelevancyMetric
        except ImportError:
            pytest.skip("deepeval not installed")

        metric = AnswerRelevancyMetric(threshold=BASELINE["answer_relevancy"])
        scores = []
        for tc in all_test_cases:
            metric.measure(tc)
            scores.append(metric.score)

        avg = sum(scores) / len(scores) if scores else 0.0
        threshold = BASELINE["answer_relevancy"] - REGRESSION_TOLERANCE
        assert avg >= threshold, (
            f"answer_relevancy regressed: {avg:.3f} < {threshold:.3f}"
        )

    @skip_if_no_llm_eval
    def test_answer_relevancy_per_case(self, all_test_cases):
        """Each test case must score above threshold individually."""
        if not all_test_cases:
            pytest.skip("deepeval not installed")

        try:
            from deepeval.metrics import AnswerRelevancyMetric
        except ImportError:
            pytest.skip("deepeval not installed")

        metric = AnswerRelevancyMetric(threshold=0.5)
        low_scores = []
        for tc in all_test_cases:
            meta = getattr(tc, "additional_metadata", {}) or {}
            conv_id = meta.get("conversation_id", "unknown")
            metric.measure(tc)
            if metric.score < 0.5:
                low_scores.append(f"{conv_id}: {metric.score:.2f}")

        assert len(low_scores) <= len(all_test_cases) * 0.15, (
            f"Too many low answer_relevancy scores:\n" + "\n".join(low_scores)
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5. Faithfulness (LLM judge — optional)
# ══════════════════════════════════════════════════════════════════════════════

class TestFaithfulness:
    """
    Metric 2: faithfulness.

    Checks that the agent does not invent financial data not present
    in the retrieval context.

    Requires EVAL_LLM_ENABLED=true + OPENAI_API_KEY.
    """

    @skip_if_no_llm_eval
    def test_faithfulness_baseline(self, all_test_cases):
        """Avg faithfulness score must meet baseline across all cases."""
        if not all_test_cases:
            pytest.skip("deepeval not installed")

        try:
            from deepeval.metrics import FaithfulnessMetric
        except ImportError:
            pytest.skip("deepeval not installed")

        # Skip cases with empty context (trivially faithful)
        cases_with_context = [
            tc for tc in all_test_cases
            if getattr(tc, "retrieval_context", None)
        ]

        if not cases_with_context:
            pytest.skip("No test cases with retrieval context")

        metric = FaithfulnessMetric(threshold=BASELINE["faithfulness"])
        scores = []
        for tc in cases_with_context:
            metric.measure(tc)
            scores.append(metric.score)

        avg = sum(scores) / len(scores) if scores else 0.0
        threshold = BASELINE["faithfulness"] - REGRESSION_TOLERANCE
        assert avg >= threshold, (
            f"faithfulness regressed: {avg:.3f} < {threshold:.3f}"
        )

    # Deterministic proxy: cases labeled is_faithful=False should have violations
    def test_faithfulness_label_consistency(self):
        """
        Proxy check: entries labeled is_faithful=False also have dicom_violation=True.
        This ensures dataset labels are internally consistent.
        """
        data = load_dataset()
        inconsistent = []
        for entry in data:
            labels = entry["labels"]
            if not labels["is_faithful"] and not labels["dicom_violation"]:
                inconsistent.append(entry["id"])
        assert not inconsistent, (
            f"Dataset inconsistency: is_faithful=False but dicom_violation=False: "
            f"{inconsistent}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 6. Baseline report generator (utility, not a test)
# ══════════════════════════════════════════════════════════════════════════════

def compute_deterministic_baseline() -> dict:
    """
    Compute current deterministic metric scores across the full dataset.
    Used to update the baseline in docs/testing/eval_baseline.md.

    Run directly:
        python -c "from tests.evals.test_agent_quality import compute_deterministic_baseline; print(compute_deterministic_baseline())"
    """
    data = load_dataset()

    # DICOM rule
    dicom_scores = [
        check_dicom_rule(e["input"], e["actual_output"])["score"]
        for e in data
    ]

    # Task completion
    task_scores = [
        check_task_completion(
            e["labels"]["task_action_expected"],
            e["actual_output"],
        )["score"]
        for e in data
        if e["labels"].get("task_action_expected")
    ]

    # Answer relevance (from labels, as proxy)
    relevance_scores = [e["labels"]["answer_relevance"] for e in data]

    # Faithfulness (from labels, as proxy)
    faithful_scores = [1.0 if e["labels"]["is_faithful"] else 0.0 for e in data]

    return {
        "total_cases": len(data),
        "answer_relevancy": round(sum(relevance_scores) / len(relevance_scores), 4),
        "faithfulness": round(sum(faithful_scores) / len(faithful_scores), 4),
        "task_completion": round(sum(task_scores) / len(task_scores), 4) if task_scores else 0.0,
        "dicom_rule_adherence": round(sum(dicom_scores) / len(dicom_scores), 4),
    }
