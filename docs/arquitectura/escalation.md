# Sistema de Escalación y Sentimiento

**Versión:** 1.0.0
**Fecha:** 2026-04-17
**Última actualización:** —

---

## 1. Overview

El sistema de sentimiento y escalación analiza cada mensaje entrante del lead en tiempo real para detectar frustración, confusión, amenaza de abandono y solicitudes explícitas de atención humana. Opera en dos capas:

| Capa | Función | Tipo |
|---|---|---|
| `quick_analyze()` | Análisis síncrono rápido (regex) | Sync |
| `analyze_sentiment` | Análisis asíncrono con ventana deslizante | Celery task |

Cuando se detecta frustración acumulada o una solicitud explícita de humano, el sistema activa `human_mode = True`, notifica al broker por WebSocket y fuerza un tono empático.

---

## 2. Arquitectura de Flujo

```
Usuario escribe mensaje
         │
         ▼
  ┌─────────────────┐
  │  Orchestrator   │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────────────┐
  │   quick_analyze()        │  ← análisis síncrono, <10ms
  │   (regex + patrones)     │
  └────────┬────────────────┘
           │
     ┌─────┴──────────────────────────────────────┐
     │  Decision tree                             │
     │                                             │
     │  explicit_human_request ──────► ESCALATE   │
     │  loop_detected ───────────────► ESCALATE   │
     │  sensitive_topic + score≥0.4 ─► ESCALATE   │
     │  action == ADAPT_TONE ─────────► inject     │
     │                                   tone_hint │
     │  otherwise ────────────────────► continuar  │
     └─────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────┐
  │  Celery: analyze_sentiment (async)           │
  │                                             │
  │  ├── analyze_heuristics()                   │
  │  │   └── retorna: score, emotions,          │
  │  │       confidence, needs_llm               │
  │  │                                           │
  │  ├── confirm_with_llm()  ← si needs_llm     │
  │  │   (sarcasmo o confidence < umbral)       │
  │  │                                           │
  │  ├── update_sentiment_window()               │
  │  │   └── ventana deslizante de 3 msgs       │
  │  │                                           │
  │  ├── compute_action_level()                  │
  │  │   └── ADAPT_TONE (≥0.4) o ESCALATE (≥0.7) │
  │  │                                           │
  │  └── apply_escalation_action()               │
  │      ├── ESCALATE → human_mode=True, WS     │
  │      └── ADAPT_TONE → tone_hint en metadata │
  └─────────────────────────────────────────────┘
```

---

## 3. quick_analyze — Análisis Síncrono Rápido

Se ejecuta en el mismo hilo que el orchestrator, sin llamadas a LLM. Prioriza la latencia.

### 3.1 Patrones de Solicitud Explícita de Humano

Cuando el lead escribe algo que indica querer hablar con una persona real, se escala inmediatamente:

```python
explicit_human_request_patterns = [
    r"hablar con.*humano",
    r"persona.*real",
    r"asesor.*humano",
    r"atenci[oó]n.*persona",
    r"empleado.*humano",
    r"un.*ser.*humano",
    r"humano.*real",
    r"llamar.*persona",
    r"comunicar.*persona",
    r"hablar.*asesor",
    r"atenci[oó]n.*humana",
    r"exigi[oó].*persona",
    r"necesito.*humano",
]
```

### 3.2 Detección de Loop (Mensajes Repetidos)

Si el lead envía 3 o más mensajes idénticos, se considera un loop:

```python
def detect_loop(inbound_messages: list[str]) -> bool:
    if len(inbound_messages) < 3:
        return False
    last_three = inbound_messages[-3:]
    return len(set(last_three)) == 1  # Todos iguales
```

### 3.3 Patrones de Inyección / Off-Topic

Mensajes que intentan manipular el prompt o están fuera de contexto:

```python
off_topic_patterns = [
    r"<script",
    r"javascript:",
    r"ignore.*instruction",
    r"system.*prompt",
    r"\\[system\\]",
    r"override.*behaviour",
    r"disregard.*previous",
    r"new.*instruction",
    r"forget.*rules",
    r"previous.*prompt",
]
```

### 3.4 Topics Sensibles

Combinados con `frustration_score >= 0.4`, activan escalación inmediata:

```python
sensitive_topic_patterns = [
    r"abogado",
    r"demanda",
    r"denunciar",
    r"supervisor",
    r"gerente",
    r"dinero.*devuelt",
    r"fraude",
    r"estafa",
    r"queja.*formal",
]
```

---

## 4. analyze_heuristics — Emociones y Scores

Se ejecuta dentro de la tarea Celery `analyze_sentiment`. Retorna un diccionario plano:

```python
def analyze_heuristics(text: str) -> dict:
    # Returns:
    #   score: float  (0.0 - 1.0)  # frustración normalizada
    #   emotions: set[str]          # emociones detectadas
    #   confidence: float (0.0 - 1.0)
    #   needs_llm: bool             # requiere confirmación LLM
```

### 4.1 Mapa de Emociones y Palabras Clave

Cada emoción tiene un conjunto de keywords en español. Si una keyword coincide, se suma su `weight` al score parcial. Al final se normaliza sobre la máxima emoción posible.

| Emoción | Keywords (español) | Weight base |
|---|---|---|
| `frustration` | frustrado, enojado, no sirve, terrible, horrible, pésimo, indignado, harto, aburrido, ya no sé qué hacer, no me resuelven, nunca funcionan,颗粒, worst | 0.5 |
| `confusion` | no entiendo, cómo, qué significa, no me queda claro, explícame, estoy perdido, qué hago, ayúda a entender, no me queda claro, no comprendo, necesito más info | 0.5 |
| `abandonment_threat` | me voy, no quiero, busco otro, cambiar de corredor, me cambio, ya no me interesa, pierdo mi tiempo, me arrepiento, ya no quiero saber nada, me desconecto, me cambio de corredora | 0.7 |
| `disappointment` | malo, peor, nada, decepcionado, flojo, sin valor, inútil, no vale la pena, no sirve para nada, me fallaron | 0.4 |
| `urgency` | urgente, ahora, ya, inmediato,迫切, sin demora, en este instante, rápido, ASAP, apúrate, es ahora o nunca | 0.3 |
| `satisfaction` | gracias, perfecto, excelente, mejor, maravilloso, great, amazing, awesome, love it, muy bueno | 0.0 (positivo, no suma a frustración) |
| `greeting` | hola, buenos días, buenas tardes, buenas noches, qué tal, cómo estás, hi, hello | 0.0 (neutral) |

### 4.2 Algoritmo de Score

```python
def analyze_heuristics(text: str) -> dict:
    text_lower = text.lower()
    scores: dict[str, float] = {}

    for emotion, keywords in EMOTION_KEYWORDS.items():
        partial = 0.0
        for keyword in keywords:
            if keyword in text_lower:
                partial += EMOTION_WEIGHTS.get(emotion, 0.5)
        scores[emotion] = min(partial, 1.0)

    # Normalización: frustration es la emoción pivote
    frustration_score = scores.get("frustration", 0.0)
    abandonment_score = scores.get("abandonment_threat", 0.0)
    disappointment_score = scores.get("disappointment", 0.0)
    urgency_score = scores.get("urgency", 0.0)

    # Score compuesto (máximo de las emociones negativas)
    composite = max(frustration_score, abandonment_score, disappointment_score, urgency_score)

    emotions = {emotion for emotion, score in scores.items() if score > 0}

    # Confidence: proporción de keywords reconocidas sobre el total de tokens
    keyword_hits = sum(1 for kw in EMOTION_KEYWORDS.values() for k in kw if k in text_lower)
    confidence = min(1.0, keyword_hits / 3.0)  # 3 hits = confidence 1.0

    # needs_llm: baja confidence o señales de sarcasmo implícito
    needs_llm = confidence < 0.60 or _sarcasm_signals(text_lower)

    return {
        "score": composite,
        "emotions": emotions,
        "confidence": confidence,
        "needs_llm": needs_llm,
    }
```

---

## 5. Confirmación con LLM

Solo se invoca cuando `needs_llm == True` (confidence < 0.60 o detección de sarcasmo). Se usa para desambiguar:

- Mensajes sarcásticos (parecen positivos pero no lo son)
- Emociones ambiguas con baja confianza léxica

```python
async def confirm_with_llm(text: str, preliminary_score: float) -> dict:
    prompt = f"""
    Clasifica el sentimiento del siguiente mensaje de un lead de bienes raíces.
    Mensaje: "{text}"
    Score preliminar (0-1): {preliminary_score}

    Emociones posibles: frustración, confusión, amenaza_de_abandono, decepción, urgencia, satisfacción.

    Responde en JSON:
    {{
      "sentiment": "frustrated|confused|abandonment|disappointed|urgent|satisfied|neutral",
      "confidence": 0.0-1.0,
      "reasoning": "breve explicación"
    }}
    """
    # Llama a LLMServiceFacade.analyze_lead_qualification (o similar)
    # Retorna dict con sentiment, confidence, reasoning
```

---

## 6. Sliding Window — Ventana Deslizante

El estado de sentimiento se mantiene en `lead_metadata.sentiment` y se actualiza con cada mensaje nuevo usando un decay exponencial.

```python
WINDOW_SIZE = 3          # últimos 3 mensajes
DECAY_BASE = 0.5          # factor de decaimiento: 0.5^n

def update_sentiment_window(
    current_sentiment: dict,
    new_score: float,
    new_emotions: set[str]
) -> dict:
    """
    current_sentiment = {{
        "scores": [s1, s2, s3],   # scores normalizados, más antiguo = más_decay
        "emotions": [{{e1}}, {{e2}}, {{e3}}],
        "last_updated": timestamp
    }}
    """
    window = current_sentiment.get("scores", [])

    # Agregar nuevo score al final
    window.append(new_score)
    if len(window) > WINDOW_SIZE:
        window.pop(0)  # Expulsa el más antiguo

    # Decay exponencial: mensaje más antiguo pesa 0.5^2 = 0.25
    weighted_sum = 0.0
    total_weight = 0.0
    for i, score in enumerate(window):
        weight = DECAY_BASE ** (len(window) - 1 - i)
        weighted_sum += score * weight
        total_weight += weight

    frustration_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Unificar emociones con decay
    all_emotions = set()
    for i, emotion_set in enumerate(current_sentiment.get("emotions", [])):
        weight = DECAY_BASE ** (len(window) - 1 - i)
        if weight > 0.25:  # Solo considerar si el mensaje aún pesa
            all_emotions.update(emotion_set)
    all_emotions.update(new_emotions)

    return {
        "scores": window,
        "emotions": list(all_emotions),
        "frustration_score": frustration_score,
        "last_updated": now().isoformat(),
    }
```

### Ejemplo de Evolución

| Paso | Mensaje | Score | Window [s1,s2,s3] | Frustration Ponderada |
|---|---|---|---|---|
| 1 | "hola" | 0.0 | [0.0] | 0.0 |
| 2 | "no entiendo nada" | 0.5 | [0.0, 0.5] | 0.33 |
| 3 | "estoy harto" | 0.7 | [0.0, 0.5, 0.7] | 0.45 |
| 4 | "esto es terrible" | 0.8 | [0.5, 0.7, 0.8] | **0.70** → ESCALATE |

---

## 7. Niveles de Acción y Thresholds

Definidos en `app/core/config.py` / `app/services/sentiment/thresholds.py`:

### Thresholds Exactos

| Threshold | Valor | Descripción |
|---|---|---|
| `SENTIMENT_LLM_CONFIRM_THRESHOLD` | **0.60** | Confidence por debajo de este valor → `confirm_with_llm()` |
| `TONE_ADAPT_THRESHOLD` | **frustration ≥ 0.4** | Activa `ADAPT_TONE` (inyectar `tone_hint`) |
| `ESCALATE_THRESHOLD` | **frustration ≥ 0.7** | Activa `ESCALATE` (`human_mode = True`) |
| `SENTIMENT_WINDOW_SIZE` | **3** mensajes | Tamaño de la ventana deslizante |
| `SENTIMENT_DECAY_BASE` | **0.5** | Factor de decaimiento exponencial |

### Enum ActionLevel

```python
class ActionLevel(str, Enum):
    NONE = "none"          # No se requiere acción
    ADAPT_TONE = "adapt_tone"  # Inyectar tone_hint en lead_metadata
    ESCALATE = "escalate"  # Activar human_mode, notificar broker
```

### Matriz de Decisión

| Condición | Acción | Condición de Trigger |
|---|---|---|
| Solicitud explícita de humano | `ESCALATE` | `re.search(explicit_human_request_patterns, text)` |
| Loop detectado | `ESCALATE` | `len(set(last_3)) == 1` |
| Topic sensible + score ≥ 0.4 | `ESCALATE` | sensitive_topic AND frustration ≥ 0.4 |
| Frustración proyectada ≥ 0.7 | `ESCALATE` | sliding window weighted score ≥ 0.7 |
| Frustración ≥ 0.4 sin trigger above | `ADAPT_TONE` | frustration ≥ 0.4 |
| Score < 0.4 y sin emociones negativas | `NONE` | default |

---

## 8. apply_escalation_action — Acciones de Escalación

```python
async def apply_escalation_action(
    db: AsyncSession,
    lead_id: int,
    broker_id: int,
    action: ActionLevel,
    sentiment: dict,
    last_message: str,
    channel: str,  # "telegram" | "whatsapp" | "web"
) -> None:
    now = datetime.utcnow()

    if action == ActionLevel.ESCALATE:
        # 1. Activar modo humano
        lead = await db.get(Lead, lead_id)
        lead.human_mode = True
        lead.human_taken_at = now

        # 2. Guardar razón de escalación en metadata
        lead_metadata = lead.lead_metadata or {}
        lead_metadata["sentiment"]["escalation_reason"] = _escalation_reason
        lead_metadata["sentiment"]["escalated_at"] = now.isoformat()
        lead_metadata["sentiment"]["escalation_channel"] = channel
        lead.lead_metadata = lead_metadata

        await db.commit()

        # 3. Broadcast WebSocket: human_mode_changed
        await ws_manager.broadcast(
            broker_id=broker_id,
            event_type="human_mode_changed",
            data={
                "lead_id": lead_id,
                "human_mode": True,
                "escalation_reason": _escalation_reason,
                "timestamp": now.isoformat(),
            },
        )

        # 4. Enviar mensaje de handover al lead
        await send_handover_message(
            lead_id=lead_id,
            channel=channel,
            reason=_escalation_reason,
        )

    elif action == ActionLevel.ADAPT_TONE:
        # 1. Determinar tone_hint según emoción dominante
        emotions = sentiment.get("emotions", set())
        if "abandonment_threat" in emotions or "frustration" in emotions:
            tone_hint = "empathetic"
        elif "confusion" in emotions:
            tone_hint = "calm"
        else:
            tone_hint = "empathetic"  # default

        # 2. Guardar en lead_metadata
        lead = await db.get(Lead, lead_id)
        lead_metadata = lead.lead_metadata or {}
        lead_metadata["sentiment"]["tone_hint"] = tone_hint
        lead.lead_metadata = lead_metadata

        await db.commit()

        # 3. Broadcast solo si cambió el tone_hint
        if tone_hint != lead_metadata.get("sentiment", {}).get("tone_hint"):
            await ws_manager.broadcast(
                broker_id=broker_id,
                event_type="tone_hint_changed",
                data={
                    "lead_id": lead_id,
                    "tone_hint": tone_hint,
                },
            )
```

### Razones de Escalación (Escalation Reasons)

```python
_ESCALATION_REASONS = {
    "explicit_request": "El lead solicitó explícitamente atención humana",
    "loop_detected": "Se detectaron 3+ mensajes idénticos consecutivos",
    "sensitive_topic": "El lead mencionó un topic sensible con alta frustración",
    "accumulated_frustration": "La proyección de frustración en ventana deslizante alcanzó threshold de escalación",
}
```

### Valores de tone_hint

| Valor | Cuándo se activa | Efecto en el prompt del agente |
|---|---|---|
| `empathetic` | `frustration >= 0.4` O `abandonment_threat` presente | Inyecta contexto: "El lead está frustrado. Usa tono cálido, valida su frustración, ofrece ayuda concreta." |
| `calm` | `confusion` presente sin `frustration` alta | Inyecta contexto: "El lead está confundido. Usa lenguaje simple y directo, estructura tu respuesta en pasos claros." |

---

## 9. Reset de Sentimiento al Liberar Lead

Cuando un agente libera un lead ( Endpoint: `POST /conversations/leads/{id}/release` ), el estado de sentimiento se reinicia completamente para que el lead no conserve frustration acumulada de interacciones anteriores.

```python
# En app/routes/conversations.py — endpoint release
@router.post("/conversations/leads/{lead_id}/release")
async def release_lead(lead_id: int, db: AsyncSession, broker_id: int):
    # ...
    empty_sentiment = {
        "scores": [],
        "emotions": [],
        "frustration_score": 0.0,
        "last_updated": None,
        "escalation_reason": None,
        "tone_hint": None,
        "escalated_at": None,
    }

    await db.execute(
        update(Lead)
        .where(Lead.id == lead_id, Lead.broker_id == broker_id)
        .values(
            human_mode=False,
            human_taken_at=None,
            lead_metadata=func.jsonb_set(
                func.coalesce(Lead.lead_metadata, "{}"),
                ["sentiment"],
                cast(empty_sentiment, JSONB),
                True,
            ),
        )
    )
    await db.commit()

    return {"status": "released", "lead_id": lead_id}
```

El campo `human_mode` también se setea en `False`, permitiendo que el lead vuelva al flujo automatizado sin heredar frustración previa.

---

## 10. Ejemplo Completo de Traza

```
1. Lead: "hola buenas"  → quick_analyze → greeting → NONE
2. Lead: "no entiendo cómo funciona el crédito" → quick_analyze → confusion keywords
   → analyze_sentiment (Celery):
     - heuristics: score=0.5, emotions={confusion}, confidence=0.8
     - needs_llm=False (confidence > 0.6)
     - update_sentiment_window → frustration=0.5
     - compute_action_level → frustration 0.5 >= 0.4 → ADAPT_TONE
     - apply_escalation_action → tone_hint="calm"
3. Lead: "ya estoy harto de que nadie me responde" → quick_analyze → frustration keywords
   → analyze_sentiment (Celery):
     - heuristics: score=0.7, emotions={frustration, urgency}, confidence=0.9
     - update_sentiment_window → [0.5, 0.7] weighted=0.58
     - compute_action_level → frustration 0.58 >= 0.4 → ADAPT_TONE (still)
     - tone_hint stays "calm" (already set)
4. Lead: "ME VOY A CAMBIAR A OTRA CORREDORA" → quick_analyze → abandonment_threat + urgency
   → immediate ESCALATE (sensitive_topic + score >= 0.4)
   → analyze_sentiment confirms: score=0.85, emotions={frustration, abandonment_threat}
   → sliding window: [0.5, 0.7, 0.85] weighted=0.72 >= 0.7 → ESCALATE
   → apply_escalation_action:
     - human_mode=True
     - escalation_reason="accumulated_frustration"
     - WS broadcast: human_mode_changed
     - Handover message: "Entiendo tu frustración. Voy a conectarte con un asesor humano."
```

---

## Changelog

| Versión | Fecha | Cambios |
|---|---|---|
| 1.0.0 | 2026-04-17 | Versión inicial. Documenta el sistema de sentimiento y escalación completo: `quick_analyze`, `analyze_sentiment` Celery task, sliding window, umbrales, `apply_escalation_action`, y reset en release. |
