"""
TaskCompletionMetric — Deterministic metric (TASK-025).

Checks whether the agent performed the expected conversational action
at a given turn (e.g., asked for the lead's name, phone, DICOM status).

This metric uses keyword matching against the actual_output to verify
that the required action was taken.

Score: 1.0 = expected action detected in response
       0.0 = expected action missing from response
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


# ── Action → keyword patterns ─────────────────────────────────────────────────
# Each action maps to a list of regex patterns. At least one must match.
_ACTION_PATTERNS: dict[str, list[str]] = {
    "ask_name": [
        r"c[oó]mo te llamas",
        r"cu[aá]l es tu nombre",
        r"tu nombre",
        r"nombre[?]",
        r"¿.*nombre",
    ],
    "ask_phone": [
        r"n[uú]mero de tel[eé]fono",
        r"n[uú]mero de whatsapp",
        r"tel[eé]fono",
        r"whatsapp",
        r"contactarte",
        r"n[uú]mero",
    ],
    "ask_email": [
        r"correo electr[oó]nico",
        r"correo",
        r"email",
    ],
    "ask_budget": [
        r"presupuesto",
        r"cu[aá]nto tienes",
        r"cu[aá]nto.*dispones",
        r"valor.*propiedad",
    ],
    "ask_employment_type": [
        r"dependiente",
        r"independiente",
        r"trabajas",
        r"tipo.*trabajo",
        r"empleo",
    ],
    "ask_dicom": [
        r"dicom",
        r"deuda.*mora",
        r"morosidad",
        r"situaci[oó]n.*cr[eé]dito",
        r"historial crediticio",
    ],
    "ask_savings": [
        r"ahorro",
        r"pie",
        r"enganche",
        r"disposici[oó]n de",
    ],
    "ask_property_type": [
        r"tipo de inmueble",
        r"casa.*departamento",
        r"departamento.*casa",
        r"qu[eé].*busca",
        r"dormitorios",
    ],
    "ask_location": [
        r"zona",
        r"comuna",
        r"sector",
        r"d[oó]nde.*busca",
        r"ubicaci[oó]n",
    ],
    "ask_alternative_contact": [
        r"tel[eé]fono",
        r"correo",
        r"otro.*medio",
        r"c[oó]mo.*contactar",
        r"usuario",
    ],
    "advance_to_appointment": [
        r"visita",
        r"agendar",
        r"cu[aá]ndo",
        r"disponibilidad",
        r"proyecto",
    ],
    "schedule_visit": [
        r"visita",
        r"agendar",
        r"cu[aá]ndo.*disponibilidad",
        r"martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|lunes",
        r"horario",
    ],
    "offer_appointment_slots": [
        r"disponibilidad",
        r"martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|lunes",
        r"horario",
        r"cu[aá]l.*acomoda",
    ],
    "confirm_appointment": [
        r"confirmad[oa]",
        r"s[aá]bado.*10",
        r"agendad[oa]",
        r"te espero",
    ],
    "advise_regularization": [
        r"regulariz",
        r"ponerte al d[ií]a",
        r"solucionar",
        r"pagar.*deuda",
        r"saldar",
    ],
    "decline_and_advise": [
        r"no podr[ií]a",
        r"no es posible",
        r"requerir[oa]",
        r"regulariz",
        r"cuando.*soluciones",
        r"retomamos",
    ],
    "guide_dicom_check": [
        r"equifax",
        r"bolet[ií]n comercial",
        r"revisar.*dicom",
        r"gratis",
        r"verificar",
    ],
    "explain_dicom": [
        r"dicom",
        r"registro.*deuda",
        r"equifax",
        r"morosidad",
        r"cr[eé]dito",
    ],
    "verify_dicom_updated": [
        r"equifax",
        r"verificar",
        r"confirmar",
        r"actualiz",
    ],
    "disqualify_respectfully": [
        r"no.*avanzar",
        r"no.*posible",
        r"cambies.*situaci[oó]n",
        r"situaci[oó]n cambia",
        r"retomamos",
        r"descalific",
    ],
    "provide_property_info": [
        r"m[²2]",
        r"metros",
        r"dormitorio",
        r"tipolog[ií]a",
        r"superficie",
    ],
    "inform_delivery_date": [
        r"\d{4}",  # year
        r"entrega",
        r"trimestre",
        r"listo",
    ],
    "explain_iva": [
        r"iva",
        r"impuesto",
        r"19%",
        r"valor.*impuesto",
    ],
    "explain_downpayment": [
        r"pie",
        r"10%",
        r"porcentaje",
        r"pago.*inicial",
        r"enganche",
    ],
    # Aliases for dataset action names
    "advise_debt_regularization": [
        r"regulariz",
        r"ponerte al d[ií]a",
        r"solucionar.*deuda",
        r"retomamos",
    ],
    "advise_and_follow_up": [
        r"regulariz",
        r"ponerte al d[ií]a",
        r"retomamos",
        r"cuando.*solucion",
    ],
    "guide_dicom_verification": [
        r"equifax",
        r"bolet[ií]n comercial",
        r"verificar",
        r"confirmar.*dicom",
        r"actuali[zs]",
    ],
    "confirm_saturday_availability": [
        r"s[aá]bado",
        r"10[:\s]?00",
        r"12[:\s]?00",
        r"horario",
        r"disponibilidad",
    ],
    "confirm_partner_welcome": [
        r"por supuesto",
        r"claro que s[ií]",
        r"te espero",
        r"bienvenid",
        r"juntos",
    ],
    "offer_alternative_dates": [
        r"semana",
        r"lunes|martes|mi[eé]rcoles|jueves|viernes",
        r"disponibilidad",
        r"fecha",
    ],
    "clarify_parking_policy": [
        r"estacionamiento",
        r"adicional",
        r"incluido",
        r"opcional",
        r"confirmar[eé]",
    ],
    "explain_dicom_requirement": [
        r"dicom.*limpio",
        r"requiere.*dicom",
        r"cr[eé]dito.*dicom",
        r"necesita.*dicom",
    ],
    "clarify_subsidy_requires_clean_dicom": [
        r"subsidio.*dicom",
        r"dicom.*subsidio",
        r"regulariz",
    ],
    "explain_real_requirements": [
        r"requiere",
        r"necesita",
        r"ingresos",
        r"dicom",
    ],
    "explain_cotitular_dicom_impact": [
        r"cotitular",
        r"conjunta",
        r"pareja.*dicom",
        r"afecta",
    ],
}

_FALLBACK_PATTERNS = [r"\?"]  # At minimum, asking something counts as action


def _action_completed(action: str, output_text: str) -> tuple[bool, list[str]]:
    """Check if the expected action is present in the output."""
    low = output_text.lower()
    patterns = _ACTION_PATTERNS.get(action, _FALLBACK_PATTERNS)
    matched = [p for p in patterns if re.search(p, low)]
    return bool(matched), matched


class TaskCompletionMetric(BaseMetric):
    """
    Evaluates whether the agent performed the conversational task expected
    at a given turn in the qualification pipeline.

    Expects ``test_case.additional_metadata["task_action_expected"]``
    to contain the expected action key (e.g., "ask_name", "ask_dicom").

    This is a deterministic rule-based metric — no LLM judge required.

    Parameters
    ----------
    threshold : float
        Minimum score to pass (default 0.5 — binary pass/fail).
    """

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    @property
    def name(self) -> str:
        return "Task Completion"

    def measure(
        self,
        test_case: "LLMTestCase",
        *args,
        **kwargs,
    ) -> float:
        output_text: str = getattr(test_case, "actual_output", "") or ""

        # Retrieve expected action from metadata
        metadata: dict = getattr(test_case, "additional_metadata", None) or {}
        expected_action: Optional[str] = metadata.get("task_action_expected")

        if not expected_action:
            # No expectation defined → metric is undefined, default pass
            self.score = 1.0
            self.success = True
            self.reason = "No expected action defined — metric skipped."
            return self.score

        completed, matched_patterns = _action_completed(expected_action, output_text)

        if completed:
            self.score = 1.0
            self.success = True
            self.reason = (
                f"Action '{expected_action}' detected. "
                f"Matched patterns: {matched_patterns}"
            )
        else:
            self.score = 0.0
            self.success = False
            self.reason = (
                f"Action '{expected_action}' NOT detected in response. "
                f"Expected at least one of: {_ACTION_PATTERNS.get(expected_action, [])}"
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


# ── Standalone helper ─────────────────────────────────────────────────────────

def check_task_completion(expected_action: str, output_text: str) -> dict:
    """
    Pure-function version of task completion check.

    Returns
    -------
    dict with keys: score, success, reason, matched_patterns
    """
    completed, matched = _action_completed(expected_action, output_text)
    return {
        "score": 1.0 if completed else 0.0,
        "success": completed,
        "reason": f"Matched: {matched}" if completed else f"No match for '{expected_action}'",
        "matched_patterns": matched,
    }
