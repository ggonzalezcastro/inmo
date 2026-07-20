# Voice Module — Pipecat Stack

Reemplaza VAPI ($0.20/min) con Pipecat + Fish Audio S2 + Deepgram (~$0.035/min, 82% ahorro).

## Cuatro modos de operación

### Modo 1 — Autónomo
La IA llama al lead y conduce la conversación completa usando el multi-agent system.

```
Twilio → transport.input()
  → VAD (detección de voz)
  → Deepgram STT
  → TranscriptSaver (lead)
  → CRMLLMProcessor          ← llama a ChatOrchestratorService.process_for_voice()
  → EmotionTagger             ← inyecta tag Fish Audio según contexto
  → Fish Audio / ElevenLabs TTS
  → TranscriptSaver (AI)
  → transport.output() → Twilio
```

### Modo 2 — Copilot
El humano llama al lead. La IA escucha, transcribe y genera notas automáticas en el dashboard.
La IA no habla.

```
Twilio → transport.input()
  → VAD
  → Deepgram STT (con diarización)
  → TranscriptSaver (lead + human)
  → NoteTaker                 ← cada 4 turnos genera nota via LLM → WS "call_ai_note"
  [sin TTS, sin output de audio]
```

### Modo 3 — Handoff
Empieza como Autónomo. Al detectar lead caliente (score ≥ 50), petición explícita, o señal
del AgentSupervisor, transfiere la llamada al humano sin cortar. El lead no nota la transición.

```
[Autónomo pipeline]
  + HandoffMonitor            ← vigila señales de handoff en cada TranscriptionFrame
    → transition message TTS
    → Twilio SIP transfer
    → TTS muted
    → DB: handoff_occurred = True
    → WS: "call_handoff"
```

### Modo 4 — Coaching
El humano llama al lead. La IA escucha y envía sugerencias al agente en tiempo real vía
WebSocket. El lead nunca escucha a la IA.

```
Twilio → transport.input()
  → VAD
  → Deepgram STT
  → TranscriptSaver
  → CoachingAdvisor           ← cada 3 turnos genera sugerencia → WS "call_coaching_suggestion"
                                 (send_to_user, no broadcast)
  [sin TTS, sin output de audio]
```

## WebSocket events (frontend)

| Evento | Cuándo | Data |
|--------|--------|------|
| `call_started` | Al crear la llamada | `{voice_call_id, pipecat_mode, lead_id}` |
| `call_answered` | Twilio: in-progress | `{voice_call_id, lead_id}` |
| `call_transcript_line` | Cada utterance | `{voice_call_id, speaker, text, timestamp, emotion_tag_used}` |
| `call_ai_note` | Cada 4 turnos (copilot) | `{voice_call_id, note, turn_count}` |
| `call_coaching_suggestion` | Cada 3 turnos (coaching) | `{voice_call_id, suggestion, turn_count}` |
| `call_handoff` | Al transferir | `{voice_call_id, reason, handoff_at}` |
| `call_ended` | Al terminar | `{voice_call_id, status}` |

## Skills por canal

Los agentes tienen dos versiones de sus reglas conversacionales:

| Canal | Archivo | Características |
|-------|---------|----------------|
| Chat | `prompts/skills/qualifier_skill.py` | Emojis, markdown, listas, números numéricos |
| Voz | `prompts/skills/voice/qualifier_voice.py` | Sin emojis, sin markdown, números en palabras, max 3 oraciones |

`BaseAgent._get_skill_for_channel(context)` selecciona automáticamente según `context.channel`.
Si `VOICE_SKILL` está vacío, usa `CHAT_SKILL` con un warning.

Para agregar un nuevo skill de voz: crear `voice/mi_agente_voice.py` con una string
`MI_AGENTE_VOICE_SKILL`, exportarla en `voice/__init__.py`, y asignarla en el agente como
`VOICE_SKILL = MI_AGENTE_VOICE_SKILL`.

## TTS Provider

Controlado por `TTS_PROVIDER` en `.env`:

| Valor | Cuándo usar | Notas |
|-------|-------------|-------|
| `elevenlabs` | Dev local / testing | Plan gratis 10k chars/mes. Sin emotion tags. |
| `fish_audio` | Producción | Voice cloning chileno. Emotion tags activos. |

## Resumen post-llamada (CA-13)

Al terminar cada llamada Pipecat se encola automáticamente la Celery task
`generate_pipecat_call_summary`. Esta tarea:

1. Lee todas las líneas de `call_transcripts` y arma el transcript completo
2. Llama a `CallAgentService.generate_call_summary()` (LLM)
3. Guarda en `voice_calls`:
   - `transcript` — texto completo
   - `summary` — resumen 2-3 oraciones
   - `extracted_data` — sentiment, intereses, objeciones, compromisos, next_steps
   - `call_metrics` — lines por speaker, tts_provider
4. Actualiza `lead.lead_score` y mueve el pipeline stage si corresponde

## Clonar una voz chilena (CA-17)

1. Grabar 15-30 segundos de audio de una persona chilena hablando naturalmente
   (tono profesional, sin leer guion, mínimo ruido de fondo)
2. Llamar al endpoint:
   ```
   POST /api/v1/calls/voices/clone
   Content-Type: multipart/form-data
   audio: <archivo.wav>
   name: "sofia-chilena-v1"
   ```
3. Guardar el `voice_id` retornado en `.env` como `FISH_AUDIO_VOICE_ID`

## Variables de entorno requeridas

```
TTS_PROVIDER=elevenlabs           # o fish_audio para prod
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...           # opcional
DEEPGRAM_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+56...
WEBHOOK_BASE_URL=https://tu-ngrok.ngrok.io   # o dominio prod
```

## Estructura de archivos

```
services/voice/
├── pipecat/
│   ├── pipeline_manager.py          # Registry de pipelines activos por llamada
│   ├── voice_config.py              # VoiceConfig + build_tts_service()
│   ├── pipelines/
│   │   ├── autonomous.py
│   │   ├── copilot.py
│   │   ├── handoff.py
│   │   └── coaching.py
│   ├── processors/
│   │   ├── crm_llm_processor.py     # STT → AgentSupervisor → TextFrame
│   │   ├── emotion_tagger.py        # Inyecta Fish Audio emotion tags
│   │   ├── transcript_saver.py      # DB + WS broadcast por utterance
│   │   ├── note_taker.py            # Notas automáticas (copilot)
│   │   ├── coaching_advisor.py      # Sugerencias al agente (coaching)
│   │   └── handoff_monitor.py       # Detecta y ejecuta handoffs
│   ├── telephony/
│   │   └── twilio_handler.py        # Twilio REST: initiate, transfer, end
│   └── tools/
│       └── voice_tool_definitions.py
└── providers/
    ├── vapi/                        # Legacy — datos históricos
    └── bland/
```
