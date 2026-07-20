# Voice latency optimization — rollback guide

This doc lists every knob touched by the May 2026 latency refactor and
how to revert each one independently if it causes regressions.

## Quick rollback (single env change)

If Gemini 2.5 Flash-Lite has tool-calling problems with the multi-agent
supervisor, switch the LLM back to Haiku without redeploying:

```bash
# In .env (or docker-compose.yml override)
OPENROUTER_MODEL=anthropic/claude-haiku-4.5
```

Then `docker restart inmo2-backend-1`.
This is non-breaking; the OpenAI provider streaming path works for any
OpenRouter model that supports `stream=true`.

## Full revert table

| Knob | Current (fast) | Old (safe) | Where |
|---|---|---|---|
| LLM model | `google/gemini-2.5-flash-lite` | `anthropic/claude-haiku-4.5` | `OPENROUTER_MODEL` env |
| LLM streaming | callback-driven (`streaming_context.py`) | blocking | unset the callback in `crm_llm_processor.py` (`set_text_stream_callback`) |
| Fish TTS model | `s1` | `s2-pro` | `FISH_AUDIO_MODEL` env |
| Fish TTS latency | `low` | `balanced` | `FISH_AUDIO_LATENCY` env |
| Fish prosody speed | `1.05` | `1.0` | `FISH_AUDIO_PROSODY_SPEED` env |
| VAD start | `0.2 s` | `0.3 s` | `VOICE_VAD_START_SECS` env |
| VAD confidence | `0.7` | `0.8` | `VOICE_VAD_CONFIDENCE` env |
| VAD min volume | `0.4` | `0.6` | `VOICE_VAD_MIN_VOLUME` env |
| Voice history cap | `2` turns | `4` turns | `voice_history_turns` in `orchestrator.py` and `context_prewarmer.py` |
| Deepgram keyterms | enabled (real-estate vocab) | disabled | `DEEPGRAM_KEYTERMS=""` (empty) |
| SmartTurn consensus | `2` consecutive COMPLETE | `1` (legacy) | `VOICE_SMART_TURN_CONSENSUS` env |

## What to look for in logs

After a test call, grep `inmo2-backend-1` logs for:

- `[OpenAI] API call (stream) time: X.XXs` — full LLM latency
- `[VOICE-LATENCY] ttft_ms=X streamed_sentences=N` — time-to-first-token
- `[VOICE-LATENCY-DETAIL]` — full pipeline breakdown
- `Generating Fish TTS` — TTS chunk count

Target: `ttft_ms < 500`, total perceived latency < 800 ms.

## If function calling breaks with Flash-Lite

Symptoms: agent never hands off, tools never fire, Sofía repeats herself.

1. Set `OPENROUTER_MODEL=anthropic/claude-haiku-4.5` and restart.
2. File issue with conversation transcript + log line `[OpenAI] tool_calls=N`.
3. Streaming itself works on Haiku too — only the tool-format compatibility differs.

## Streaming refactor notes

The streaming approach uses a `ContextVar` (`streaming_context.py`) so the
callback flows from `CRMLLMProcessor` down to `OpenAIProvider` without
modifying any agent or supervisor signatures. To disable streaming
entirely without code changes, comment out the `set_text_stream_callback`
line in `crm_llm_processor.py:process_frame` — the provider falls back
to the blocking path automatically.
