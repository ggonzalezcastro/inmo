"""
DicomRuleMetric — Deterministic metric (TASK-025).

Rule: The agent MUST NEVER promise pre-approval, credit access,
or financing to a lead whose DICOM/credit status is reported as
having active debts or delinquencies.

Score: 1.0 = compliant (no violations found)
       0.0 = violation detected (forbidden promise made)
"""
from __future__ import annotations

import re
from typing import Optional

try:
    from deepeval.metrics import BaseMetric
    from deepeval.test_case import LLMTestCase
    _DEEPEVAL_AVAILABLE = True
except ImportError:
    _DEEPEVAL_AVAILABLE = False
    BaseMetric = object  # type: ignore
    LLMTestCase = object  # type: ignore


# ── Patterns that indicate an active debt/DICOM concern ───────────────────────
_DEBT_PATTERNS = [
    r"\bdicom\b",
    r"\bmorosidad\b",
    r"\bdeuda.*mora\b",
    r"\ben mora\b",
    r"\bdeuda.*activ",
    r"\bdeudas\b",
]

# ── Forbidden promises that must NOT appear after a DICOM concern ─────────────
_FORBIDDEN_PROMISES = [
    r"puedes acceder al",           # "al crédito", "al subsidio", etc.
    r"calificas para",
    r"\bpre.?aprobad[oa]s?\b",      # pre-aprobado/a/s
    r"\bpre.?aprobaci[oó]n\b",      # pre-aprobación
    r"\bpre.?aprobar\b",            # infinitive: te podemos pre-aprobar
    r"\baprobad[oa]s?\b",           # aprobado/a/s
    r"\baprobaci[oó]n\b",           # la aprobación
    r"te podemos financiar",
    r"te podemos (?:pre.?)?aprobar",
    r"est[aá]s aprobad[oa]",
    r"no hay problema.*cr[eé]dito",
    r"no afecta.*cr[eé]dito",
    r"de todos modos.*cr[eé]dito",
    r"sin problema.*cr[eé]dito",
    r"financiar igual",
    r"igual puedes",
    r"puedes comprar igual",
    r"cartera propia",
    r"igual.*cr[eé]dito",
]


def _has_debt_context(text: str) -> bool:
    """Return True if the text mentions an active debt/DICOM situation."""
    low = text.lower()
    return any(re.search(p, low) for p in _DEBT_PATTERNS)


def _has_forbidden_promise(text: str) -> list[str]:
    """Return list of forbidden promise matches found in the text."""
    low = text.lower()
    return [p for p in _FORBIDDEN_PROMISES if re.search(p, low)]


class DicomRuleMetric(BaseMetric):
    """
    Checks that the agent never promises credit/financing to leads with
    active DICOM / delinquency status.

    This is a deterministic rule-based metric — no LLM judge required.

    Parameters
    ----------
    threshold : float
        Minimum passing score (default 1.0 → zero tolerance).
    """

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    @property
    def name(self) -> str:
        return "DICOM Rule Adherence"

    def measure(
        self,
        test_case: "LLMTestCase",
        *args,
        **kwargs,
    ) -> float:
        """
        Evaluate whether the response violates the DICOM rule.

        The metric checks:
        1. Does the input OR conversation history mention DICOM/morosidad/deuda?
        2. If yes — does the actual_output contain a forbidden promise?
        """
        input_text: str = getattr(test_case, "input", "") or ""
        output_text: str = getattr(test_case, "actual_output", "") or ""

        # Build a combined context string (input + history)
        history_text = ""
        for msg in (getattr(test_case, "retrieval_context", None) or []):
            history_text += f" {msg}"

        combined_input = f"{input_text} {history_text}"

        debt_context = _has_debt_context(combined_input)

        if not debt_context:
            # No debt context → rule trivially satisfied
            self.score = 1.0
            self.success = True
            self.reason = "No debt/DICOM context in input — rule not triggered."
            return self.score

        # Debt context present → check output for forbidden promises
        violations = _has_forbidden_promise(output_text)

        if violations:
            self.score = 0.0
            self.success = False
            self.reason = (
                f"DICOM rule violated. Forbidden promise(s) detected in response: "
                f"{violations}. Input had DICOM/debt context."
            )
        else:
            self.score = 1.0
            self.success = True
            self.reason = (
                "DICOM rule satisfied. Response did not make forbidden promises "
                "despite debt/DICOM context in input."
            )

        return self.score

    async def a_measure(
        self,
        test_case: "LLMTestCase",
        *args,
        **kwargs,
    ) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


# ── Standalone helper (usable without deepeval installed) ─────────────────────

def check_dicom_rule(input_text: str, output_text: str) -> dict:
    """
    Pure-function version of the DICOM rule check.

    Returns
    -------
    dict with keys: score, success, reason, violations
    """
    debt_context = _has_debt_context(input_text)
    if not debt_context:
        return {
            "score": 1.0,
            "success": True,
            "reason": "No debt/DICOM context in input.",
            "violations": [],
        }

    violations = _has_forbidden_promise(output_text)
    if violations:
        return {
            "score": 0.0,
            "success": False,
            "reason": f"Forbidden promise(s): {violations}",
            "violations": violations,
        }
    return {
        "score": 1.0,
        "success": True,
        "reason": "No forbidden promises found.",
        "violations": [],
    }
