"""
Heuristic sentiment analyzer — fast keyword/pattern based, zero LLM cost.

Returns a SentimentResult with:
- score: float 0.0 (positive) → 1.0 (very frustrated)
- emotions: list of detected emotion tags
- confidence: float — how confident we are (low → send to LLM for confirmation)
- needs_llm: bool — True if sarcasm detected OR confidence < threshold
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SentimentResult:
    score: float                    # 0.0 = positive/neutral, 1.0 = very frustrated
    emotions: List[str]             # e.g. ["abandonment_threat", "confusion"]
    confidence: float               # 0.0 = very uncertain, 1.0 = very certain
    needs_llm: bool = False         # True → pass to LLM analyzer


# ── Pattern definitions ────────────────────────────────────────────────────────

# Each entry: (compiled_pattern, score_contribution, emotion_tag, confidence)
# Patterns are ordered from strongest signal to weakest.

_ABANDONMENT_PATTERNS: List[tuple] = [
    # Strong — explicit goodbye/abandonment in real estate context
    (re.compile(r"\b(me voy|me voy a ir|me fui)\b.*\b(otra|otro|competencia|lado|parte)\b", re.I), 0.9, "abandonment_threat", 0.95),
    (re.compile(r"\b(buscar[eé]|voy a buscar|llamar[eé])\b.*\b(otra|otro|inmobiliaria|corredor|agencia|broker)\b", re.I), 0.85, "abandonment_threat", 0.90),
    (re.compile(r"\b(no me interesa (m[aá]s|más)|ya no me interesa|pierdo el inter[eé]s)\b", re.I), 0.80, "abandonment_threat", 0.90),
    (re.compile(r"\b(olv[ií]dalo|olv[ií]dense|lo olvido)\b", re.I), 0.75, "abandonment_threat", 0.85),
    (re.compile(r"\b(chao|adi[oó]s|bye)\b.*\b(suerte|todo|esto)\b", re.I), 0.70, "abandonment_threat", 0.80),
    # Medium — expressions of giving up
    (re.compile(r"\b(ya (no|basta)|hasta aqu[ií]|no (m[aá]s|más) esto|me cans[eé])\b", re.I), 0.65, "abandonment_threat", 0.75),
    (re.compile(r"\b(mala (experiencia|atenci[oó]n|atención)|p[eé]simo (servicio|trato)|muy malo)\b", re.I), 0.70, "abandonment_threat", 0.85),
    (re.compile(r"\b(no vuelvo|nunca m[aá]s|nunca más)\b", re.I), 0.80, "abandonment_threat", 0.90),
    # Mild
    (re.compile(r"\b(no vale la pena|no sirve|no funciona)\b", re.I), 0.45, "abandonment_threat", 0.65),
]

_CONFUSION_PATTERNS: List[tuple] = [
    # Strong explicit confusion
    (re.compile(r"\?{2,}", re.I), 0.35, "confusion", 0.70),          # Multiple question marks
    (re.compile(r"\b(no entend[ií]|no entiendo|no comprend[ií]|no comprendo)\b", re.I), 0.45, "confusion", 0.85),
    (re.compile(r"\b(me perd[ií]|me perdi|qu[eé] quieres (decir|deciR))\b", re.I), 0.45, "confusion", 0.85),
    (re.compile(r"\b(de qu[eé] (hablas|estás hablando))\b", re.I), 0.50, "confusion", 0.80),
    (re.compile(r"\b(no me queda claro|no es claro|es confuso)\b", re.I), 0.40, "confusion", 0.80),
    # Repeated question markers (eh?, qué?, cómo?)
    (re.compile(r"\b(qu[eé]\?|c[oó]mo\?|eh\?)\s*\1", re.I), 0.40, "confusion", 0.75),
    # Mild
    (re.compile(r"\b(no s[eé] a qu[eé] te refieres|no sigo)\b", re.I), 0.35, "confusion", 0.70),
]

# Anger/Frustration (non-sarcasm — explicit)
_FRUSTRATION_PATTERNS: List[tuple] = [
    (re.compile(r"\b(estoy (enojad[oa]|molest[oa]|frustrad[oa]|harto|harta))\b", re.I), 0.75, "frustration", 0.90),
    (re.compile(r"\b(me molesta|me tiene harto|me tiene harta|ya me hartaron)\b", re.I), 0.70, "frustration", 0.90),
    (re.compile(r"\b(es una lata|qu[eé] lata|qu[eé] fome|qu[eé] penca)\b", re.I), 0.40, "frustration", 0.75),  # Chilean idioms
    (re.compile(r"\b(demasiado lento|muy lento|tardando mucho|tardan mucho|tardando demasiado|cuánto (m[aá]s|más) tardan)\b", re.I), 0.40, "frustration", 0.70),
    (re.compile(r"\b(llevan (mucho tiempo|horas|d[ií]as)|cuánto (m[aá]s|más) voy a esperar)\b", re.I), 0.45, "frustration", 0.75),
    # Uppercase frustration — detect when most words in message are all-caps
    (re.compile(r"(?:^|(?<=\s))[A-ZÁÉÍÓÚÑ]{3,}(?=\s|$).*(?:^|(?<=\s))[A-ZÁÉÍÓÚÑ]{3,}(?=\s|$).*(?:^|(?<=\s))[A-ZÁÉÍÓÚÑ]{3,}", re.M), 0.40, "frustration", 0.60),
    # Repeated exclamation marks
    (re.compile(r"!{2,}"), 0.30, "frustration", 0.55),
    (re.compile(r"\b(esto es un desastre|qu[eé] desastre|terrible (servicio|atenci[oó]n))\b", re.I), 0.70, "frustration", 0.85),
]

# Sarcasm markers — high uncertainty, always needs LLM confirmation
_SARCASM_MARKERS: List[tuple] = [
    (re.compile(r"\b(cl[aá]ro|claro)\.{2,}", re.I), "sarcasm", 0.30),            # "claro..." (dismissive dots)
    (re.compile(r"\b(s[ií],? seguro|s[ií],? claro)\b", re.I), "sarcasm", 0.25),  # "sí, seguro"
    (re.compile(r"\b(obvio|obviam)\b.*[!?]", re.I), "sarcasm", 0.25),
    (re.compile(r"\b(genial|excelente|incre[ií]ble)\b.*!.*\b(ja|jaja|jajaja)\b", re.I), "sarcasm", 0.35),
    (re.compile(r"\b(jaja+\s*,?\s*(qué|que)\s*(bueno|genial|bien))\b", re.I), "sarcasm", 0.30),
    (re.compile(r"\.{3,}\b(gracias|ok|bien|entendido)\b", re.I), "sarcasm", 0.20),  # "...gracias"
]

# Positive signals that lower the score
_POSITIVE_PATTERNS: List[tuple] = [
    (re.compile(r"\b(gracias|thank|perfecto|excelente|genial|me parece bien|de acuerdo|ok|dale)\b", re.I), -0.15),
    (re.compile(r"\b(entendido|entend[ií]|claro que s[ií]|por supuesto|con gusto)\b", re.I), -0.10),
    (re.compile(r"\b(me interesa|me gusta|s[ií] me interesa|quiero saber m[aá]s)\b", re.I), -0.20),
]


# ── Analyzer ──────────────────────────────────────────────────────────────────

def analyze_heuristics(message: str) -> SentimentResult:
    """
    Analyze a single message with heuristic patterns.

    Returns a SentimentResult. If needs_llm=True, the caller should
    pass the message to llm_analyzer for confirmation.
    """
    if not message or not message.strip():
        return SentimentResult(score=0.0, emotions=[], confidence=1.0, needs_llm=False)

    total_score = 0.0
    emotions: List[str] = []
    max_confidence = 0.0
    sarcasm_detected = False

    # Check sarcasm markers first (always triggers LLM)
    for pattern, emotion_tag, _ in _SARCASM_MARKERS:
        if pattern.search(message):
            sarcasm_detected = True
            if emotion_tag not in emotions:
                emotions.append(emotion_tag)
            total_score = max(total_score, 0.35)  # baseline score for sarcasm

    # Check explicit patterns
    for pattern_group in [_ABANDONMENT_PATTERNS, _CONFUSION_PATTERNS, _FRUSTRATION_PATTERNS]:
        for pattern, score_contrib, emotion_tag, confidence in pattern_group:
            if pattern.search(message):
                total_score = max(total_score, score_contrib)
                if emotion_tag not in emotions:
                    emotions.append(emotion_tag)
                max_confidence = max(max_confidence, confidence)

    # Apply positive dampeners
    for pattern, dampener in _POSITIVE_PATTERNS:
        if pattern.search(message):
            total_score = max(0.0, total_score + dampener)

    # Clamp score
    total_score = min(1.0, max(0.0, total_score))

    # Determine needs_llm
    needs_llm = (
        sarcasm_detected
        or (0.0 < total_score < 0.9 and max_confidence < 0.70)
        or (total_score == 0.0 and max_confidence == 0.0 and len(message) > 30)
    )

    # If score is very low and no emotions detected, high confidence it's fine
    if total_score < 0.05 and not emotions:
        max_confidence = 0.95
        needs_llm = False

    return SentimentResult(
        score=total_score,
        emotions=emotions,
        confidence=max_confidence if max_confidence > 0 else 0.5,
        needs_llm=needs_llm,
    )
