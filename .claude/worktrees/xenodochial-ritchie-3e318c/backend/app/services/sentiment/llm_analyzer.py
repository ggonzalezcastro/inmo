"""
LLM-based sentiment confirmation.

Only called when heuristics are uncertain (needs_llm=True).
Always called for sarcasm/irony detection.

Uses LLMServiceFacade.generate_response() with a structured prompt.
Falls back gracefully if LLM call fails.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional

from app.services.sentiment.heuristics import SentimentResult

logger = logging.getLogger(__name__)

# ── Prompt template ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """Eres un analizador de sentimientos especializado en conversaciones de ventas inmobiliarias en Chile. Tu tarea es analizar el mensaje de un cliente potencial y detectar si expresa frustración, enojo, confusión, sarcasmo/ironía, o amenaza de abandono.

Responde SIEMPRE con un JSON válido con esta estructura exacta:
{
  "score": <float entre 0.0 y 1.0>,
  "emotions": [<lista de strings: "abandonment_threat", "confusion", "frustration", "sarcasm", "anger">],
  "reasoning": "<explicación breve en español>"
}

Escala de score:
- 0.0 - 0.2: Neutral o positivo
- 0.2 - 0.4: Leve insatisfacción o confusión
- 0.4 - 0.7: Frustración moderada o confusión clara
- 0.7 - 1.0: Enojo fuerte, sarcasmo evidente, o amenaza real de abandono

Contexto chileno: "fome", "penca", "lata", "chancho" son expresiones negativas pero leves (score 0.3-0.4). "Chao no más", "me olvido de esto", "busco en otro lado" son señales fuertes de abandono (score 0.7+).

El sarcasmo en Chile se expresa con "claro...", "sí, seguro", "obvio pues", "genial jaja", puntos suspensivos después de confirmaciones, mayúsculas en palabras sueltas.

SOLO devuelve el JSON, sin texto adicional."""

_FEW_SHOTS = [
    {
        "message": "ok perfecto, gracias!",
        "context": [],
        "expected": {"score": 0.05, "emotions": [], "reasoning": "Mensaje positivo y agradecido"},
    },
    {
        "message": "sí, seguro que van a llamar... como siempre",
        "context": ["Agente: Te llamamos mañana sin falta"],
        "expected": {"score": 0.65, "emotions": ["sarcasm"], "reasoning": "Sarcasmo claro: duda de que cumplan la promesa"},
    },
    {
        "message": "no entiendo nada de lo que me están diciendo, qué significa eso de DICOM??",
        "context": [],
        "expected": {"score": 0.45, "emotions": ["confusion"], "reasoning": "Confusión legítima con terminología técnica"},
    },
    {
        "message": "ya me cansé, voy a buscar en otra inmobiliaria",
        "context": ["Agente: Podemos agendar para la semana que viene", "Cliente: cuándo me van a atender??"],
        "expected": {"score": 0.90, "emotions": ["abandonment_threat", "frustration"], "reasoning": "Amenaza explícita de abandono tras espera prolongada"},
    },
    {
        "message": "qué lata este proceso, súper lento",
        "context": [],
        "expected": {"score": 0.38, "emotions": ["frustration"], "reasoning": "Frustración leve con modismo chileno 'qué lata'"},
    },
]


def _build_prompt(message: str, context_messages: List[str]) -> str:
    context_str = ""
    if context_messages:
        context_str = "\nContexto previo (últimos mensajes):\n" + "\n".join(
            f"  - {m}" for m in context_messages[-3:]
        )

    examples = "\n".join(
        f'Ejemplo {i+1}:\nMensaje: "{ex["message"]}"\nContexto: {ex["context"]}\nRespuesta esperada: {json.dumps(ex["expected"], ensure_ascii=False)}'
        for i, ex in enumerate(_FEW_SHOTS[:3])
    )

    return f"""{examples}

---
Ahora analiza este mensaje:
Mensaje: "{message}"{context_str}

Responde solo con el JSON:"""


# ── LLM call ──────────────────────────────────────────────────────────────────

async def confirm_with_llm(
    message: str,
    context_messages: Optional[List[str]] = None,
    heuristic_result: Optional[SentimentResult] = None,
    broker_id: Optional[int] = None,
    lead_id: Optional[int] = None,
) -> SentimentResult:
    """
    Confirm / refine sentiment analysis using LLM.

    Falls back to the heuristic result if LLM fails.
    """
    try:
        from app.services.llm.facade import LLMServiceFacade

        prompt = _build_prompt(message, context_messages or [])
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{prompt}"

        raw_response = await LLMServiceFacade.generate_response(
            prompt=full_prompt,
        )

        parsed = _parse_llm_response(raw_response)
        if parsed:
            logger.info(
                "sentiment_llm_confirmed",
                extra={
                    "lead_id": lead_id,
                    "broker_id": broker_id,
                    "score": parsed["score"],
                    "emotions": parsed["emotions"],
                },
            )
            return SentimentResult(
                score=float(parsed["score"]),
                emotions=list(parsed.get("emotions", [])),
                confidence=0.85,  # LLM result gets high confidence
                needs_llm=False,
            )
    except Exception as exc:
        logger.warning(
            "sentiment_llm_failed: %s — falling back to heuristics",
            exc,
            extra={"lead_id": lead_id},
        )

    # Fallback to heuristic result or neutral
    if heuristic_result:
        return SentimentResult(
            score=heuristic_result.score,
            emotions=heuristic_result.emotions,
            confidence=max(heuristic_result.confidence, 0.50),
            needs_llm=False,
        )
    return SentimentResult(score=0.0, emotions=[], confidence=0.50, needs_llm=False)


def _parse_llm_response(raw: str) -> Optional[Dict]:
    """Extract JSON from LLM response, handling markdown fences."""
    try:
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        data = json.loads(cleaned)

        # Validate required fields
        score = float(data.get("score", 0.0))
        emotions = [str(e) for e in data.get("emotions", [])]

        return {"score": max(0.0, min(1.0, score)), "emotions": emotions}
    except Exception:
        # Fallback: find the largest JSON object in the response (greedy match)
        # using re.DOTALL so it spans newlines and captures nested arrays.
        match = re.search(r'\{.+\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return {
                    "score": max(0.0, min(1.0, float(data.get("score", 0.0)))),
                    "emotions": list(data.get("emotions", [])),
                }
            except Exception:
                pass
        return None
