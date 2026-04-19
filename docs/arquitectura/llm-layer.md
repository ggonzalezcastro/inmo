# LLM Layer Architecture

**Last Updated:** April 17, 2026
**Version:** 1.0

---

## Overview

The LLM Layer provides a unified interface for all LLM interactions in the system. It abstracts away provider details (Gemini, Claude, OpenAI), handles failover, caches results, and exposes function-calling capabilities for the multi-agent system.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LLMServiceFacade                               │
│  (single entry point for all LLM calls)                                      │
│                                                                              │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────────┐ │
│  │ generate_response  │  │analyze_lead_quali- │  │ generate_response_with │ │
│  │                    │  │ fication           │  │   function_calling     │ │
│  └────────────────────┘  └────────────────────┘  └────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    build_llm_prompt                                  │    │
│  │  (assembles RAG + context + history into full prompt)               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │        LLMRouter             │
                     │   (circuit breaker +        │
                     │    failover logic)           │
                     └──────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             ┌────────────┐ ┌────────────┐ ┌────────────┐
             │   Gemini    │ │   Claude   │ │   OpenAI   │
             │  Provider  │ │  Provider  │ │  Provider  │
             │ (primary)  │ │ (fallback) │ │(2nd fallb.)│
             └────────────┘ └────────────┘ └────────────┘
```

---

## LLMServiceFacade

**Location:** `backend/app/services/llm/facade.py`

Single entry point for all LLM interactions. Never instantiate — use static methods directly.

### Constants

| Constant | Default | Description |
|---|---|---|
| `FALLBACK_RESPONSE` | `"Gracias por tu mensaje. Un agente estará contigo pronto para ayudarte."` | Safe fallback when all providers fail |

### Methods

#### `generate_response(prompt: str) -> str`

Simple text generation for basic LLM calls.

**Parameters:**
- `prompt` — The input prompt string

**Returns:** Generated text response

**Implementation:** Delegates to primary provider via `LLMRouter`

---

#### `analyze_lead_qualification(...)`

Fast lead qualification analysis. Uses lightweight model (`GEMMA_MODEL`) for quick extraction.

```python
@staticmethod
async def analyze_lead_qualification(
    message: str,
    lead_context: Dict = None,
    broker_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]
```

**Parameters:**
- `message` — The incoming message to analyze
- `lead_context` — Optional existing lead data dict
- `broker_id` — Broker ID for context
- `lead_id` — Lead ID for logging
- `db` — Database session

**Returns:**
```python
{
    "qualified": bool,           # Does lead meet minimum criteria?
    "interest_level": str,       # "high" | "medium" | "low"
    "budget": Optional[str],     # Extracted budget info
    "timeline": Optional[str],   # Extracted timeline
    "name": Optional[str],       # Extracted name
    "phone": Optional[str],      # Extracted phone
    "email": Optional[str],      # Extracted email
    "salary": Optional[float],   # Extracted salary
    "location": Optional[str],   # Extracted location
    "dicom_status": str,         # "clean" | "dirty" | "unknown"
    "morosidad_amount": Optional[float],  # Default amount if dirty
    "key_points": List[str],     # Important extracted facts
    "score_delta": int,          # Score adjustment (+/- points)
    "intent": str                # "buy" | "sell" | "rent" | "info" | "other"
}
```

**Fallback:** If LLM call fails, regex-based extraction is attempted before returning empty dict.

---

#### `generate_response_with_function_calling(...)`

Chat response with tool/function calling support. This is the primary method used by agent system.

```python
@staticmethod
async def generate_response_with_function_calling(
    system_prompt: str,
    contents: List[Any],
    tools: List[Any],
    tool_executor: Optional[Callable] = None,
    broker_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    static_system_prompt: Optional[str] = None,
    agent_type: Optional[str] = None,
    tool_mode_override: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> Tuple[str, List[Dict[str, Any]]]
```

**Parameters:**
- `system_prompt` — Dynamic system prompt (injected into full prompt)
- `contents` — List of message contents (user messages, prior LLM responses, tool results)
- `tools` — List of `LLMToolDefinition` objects defining available tools
- `tool_executor` — Async callback invoked when LLM calls a tool. Signature: `async def tool_executor(tool_name: str, tool_args: Dict) -> Any`
- `broker_id` — Broker ID for provider resolution and logging
- `lead_id` — Lead ID for logging
- `static_system_prompt` — Optional pre-built static prompt (skip build_llm_prompt)
- `agent_type` — Agent type for per-agent model selection (e.g., "qualifier", "scheduler")
- `tool_mode_override` — Override LLM's function calling mode (see below)
- `db` — Database session

**Returns:** `(text_response, list_of_function_calls)` tuple

**Tool Mode Override Values:**
| Value | Behavior |
|---|---|
| `"ANY"` | Force function calling — LLM must call a tool |
| `"AUTO"` | Let LLM decide whether to call tool or respond text |
| `None` | Defaults to `"ANY"` |

---

#### `build_llm_prompt(...)`

Assembles the complete prompt with RAG chunks, context, and conversation history.

```python
@staticmethod
async def build_llm_prompt(
    lead_context: Dict,
    new_message: str,
    db: Optional[AsyncSession] = None,
    broker_id: Optional[int] = None
) -> Tuple[str, List[LLMMessage], str]
```

**Parameters:**
- `lead_context` — Current lead data (from database or in-memory)
- `new_message` — The new user message to respond to
- `db` — Database session for RAG lookups
- `broker_id` — Broker ID for RAG and prompt config

**Returns:** `(full_system_prompt, messages, static_system_prompt)`

**Prompt Assembly Order:**
1. **Static system prompt** — from `BrokerPromptConfig` or default
2. **RAG chunks** — top-3 relevant entries from Knowledge Base
3. **Dynamic context** block:
   - Current datetime (America/Santiago timezone)
   - Lead ID (internal only, never mention to user)
   - Lead data summary (DATOS RECOPILADOS / DATOS PENDIENTES)
   - Prior session summary (from `conversation_summary` in metadata)
4. **Message history** — formatted as `LLMMessage` list

---

## LLMRouter

**Location:** `backend/app/services/llm/router.py`
**Inherits:** `BaseLLMProvider`

Circuit breaker and failover manager. Routes all LLM calls through primary provider, falls back to secondary on failure.

### Constructor

```python
def __init__(self, primary: BaseLLMProvider, fallback: BaseLLMProvider):
    self.primary = primary
    self.fallback = fallback
    self._failover_active = False
```

### Retry Logic

| Setting | Value |
|---|---|
| Max attempts | 3 |
| Backoff | Exponential (0.5s → 2s → 4s) |
| Jitter | Random 0–250ms added |

### Retriable Errors (retry with backoff)
- `503` — Service unavailable
- `429` — Rate limited
- `Timeout` — Request timeout
- `Connection error` — Network failures

### Non-Retriable Errors (fail fast)
- `401` — Authentication failed
- `400` — Bad request (invalid prompt)
- Any other non-5xx error

### Circuit Breaker

Uses `llm_breaker` (likely a `CircuitBreaker` instance) to track failure rate. When circuit is open, requests go directly to fallback without attempting primary.

---

## Providers

### GeminiProvider

**Default Configuration:**
| Setting | Default | Environment Variable |
|---|---|---|
| Model | `gemini-2.0-flash-lite` | `GEMINI_MODEL` |
| Max tokens | `2048` | `GEMINI_MAX_TOKENS` |
| Temperature | `0.7` | `GEMINI_TEMPERATURE` |
| Thinking budget | `1024` (if enabled) | `GEMINI_THINKING_BUDGET` |

**Supported Methods:**
- `generate_response(prompt)` — Simple text generation
- `generate_with_messages(messages)` — Chat-style with message list
- `generate_with_tools(contents, tools, tool_mode)` — Function calling
- `generate_json(system_prompt, contents, schema)` — Structured JSON output

**Thinking Config:** For Gemini 2.5+ models, thinking budget can be enabled to improve reasoning on complex tasks.

### ClaudeProvider

Fallback provider. Used when Gemini fails and circuit breaker is open.

**Model:** Configured via `CLAUDE_MODEL` env var (default varies by version)

### OpenAIProvider

Secondary fallback. Used when both Gemini and Claude fail.

**Model:** Configured via `OPENAI_MODEL` env var

### Per-Agent Provider Resolution

```python
async def resolve_provider_for_agent(
    agent_type: str,
    broker_id: int,
    db
) -> BaseLLMProvider
```

For agents that support custom model selection (configured per broker):

1. Check broker's `agent_model_config` for the given `agent_type`
2. If configured, use that model (create provider instance)
3. If not configured, fall back to global `LLM_PROVIDER`

Example `agent_model_config` structure:
```json
{
  "qualifier": {"provider": "gemini", "model": "gemini-2.0-flash"},
  "scheduler": {"provider": "claude", "model": "claude-3-5-sonnet"}
}
```

---

## Function Calling Loop

When `generate_with_tools` is called, the following loop executes:

```
┌─────────────────────────────────────────────────────────────────┐
│                    generate_with_tools Loop                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  Iteration 1..5      │
                    │  max_iterations=5    │
                    └─────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ Call LLM     │ │ Extract tools│ │ Executor     │
      │ (with tools) │ │ from resp    │ │ callback     │
      └──────────────┘ └──────────────┘ └──────────────┘
              │               │               │
              │               └───────┬───────┘
              │                       │
              ▼                       ▼
      ┌──────────────────────────────────┐
      │ Append tool results to contents  │
      │ Feed back to LLM (next iter)    │
      └──────────────────────────────────┘
              │
              ▼
      ┌──────────────┐
      │ text_response│ ◄── Exit loop when no
      └──────────────┘     more tool calls
```

**Tool Executor Callback Signature:**
```python
async def tool_executor(tool_name: str, tool_args: Dict[str, Any]) -> Any
```

- Receives tool name and arguments from LLM
- Executes the actual tool logic (e.g., schedule appointment, search database)
- Returns result that gets fed back to LLM for next iteration

---

## Caching Mechanisms

### Semantic Cache (Redis-backed)

**Location:** `backend/app/services/llm/semantic_cache.py`

Cosine-similarity based caching for LLM responses.

**Cache Key Format:**
```
llm:sem:{lead_id}:{message_hash}
```

**Configuration:**
| Setting | Value |
|---|---|
| TTL | Configurable (env var) |
| Similarity threshold | `cosine > 0.85` |
| Embedding model | `text-embedding-004` (same as RAG) |

**Skip Conditions (no cache lookup):**
- Message contains PII (phone numbers, email patterns)
- Cache miss on lookup
- Any error during cache operations (fail open)

**Cache Hit Flow:**
1. Hash incoming message
2. Compute embedding
3. Search Redis for similar keys (cosine > 0.85)
4. If found, return cached response
5. If not found, proceed with LLM call

### Prompt Cache (Gemini Context Cache)

**Location:** `backend/app/services/llm/prompt_cache.py`
**Feature:** TASK-028

Gemini Context Caching for static system prompts.

**Strategy:**
| Component | Caching |
|---|---|
| Static system prompt | Cached per broker |
| Dynamic context (lead data) | Injected at call time |
| RAG chunks | Fetched per-call |

**Cache Key:** `prompt_cache:{broker_id}`

**Flow:**
```
┌────────────────────────────────────────────────────────────┐
│ Cache Hit                                                 │
│ 1. Retrieve cached static prompt                          │
│ 2. Append dynamic context + RAG chunks                    │
│ 3. Append message history                                  │
│ 4. Call LLM with combined prompt                          │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Cache Miss                                                │
│ 1. Build new static prompt from BrokerPromptConfig        │
│ 2. Create context cache entry in Gemini                    │
│ 3. Store reference for future hits                         │
│ 4. Proceed with LLM call                                   │
└────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Faster subsequent calls (no re-processing static content)
- Lower cost (cache tokens billed at reduced rate)

---

## RAG Search Flow

**Location:** `backend/app/routes/knowledge_base.py`

Retrieval-Augmented Generation for domain-specific knowledge.

### Configuration

| Setting | Value |
|---|---|
| Embedding model | `text-embedding-004` |
| Vector dimensions | 768 |
| Index type | IVFFlat |
| IVFFlat lists | 100 |
| Similarity metric | Cosine |
| Minimum threshold | 0.60 |
| Top-K | 3 chunks |

### Search Flow

```
┌────────────────────────────────────────────────────────────────┐
│                       RAG Search Flow                          │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌──────────────────────────────┐
              │ 1. Embed query (lead message)│
              │    text-embedding-004        │
              └──────────────────────────────┘
                              │
                              ▼
              ┌──────────────────────────────┐
              │ 2. Vector similarity search  │
              │    in pgvector (IVFFlat)     │
              │    WHERE broker_id = ?       │
              └──────────────────────────────┘
                              │
                              ▼
              ┌──────────────────────────────┐
              │ 3. Filter by similarity > 0.6│
              │    Sort descending           │
              │    Limit 3                   │
              └──────────────────────────────┘
                              │
                              ▼
              ┌──────────────────────────────┐
              │ 4. Format chunks for prompt  │
              │    "### Knowledge Base:\n    │
              │     {chunk1}\n\n              │
              │     {chunk2}\n\n              │
              │     {chunk3}"                │
              └──────────────────────────────┘
```

### Prompt Injection Format

```markdown
### Knowledge Base:
{chunk_1_text}

{chunk_2_text}

{chunk_3_text}
```

---

## LLM Call Logging

**Location:** `backend/app/services/llm/` (logger decorator / helper)

All LLM calls are logged asynchronously to the `llm_calls` table.

### Logged Fields

| Field | Type | Description |
|---|---|---|
| `provider` | String | "gemini" / "claude" / "openai" |
| `model` | String | Model identifier used |
| `call_type` | String | "generate" / "analyze" / "function_calling" |
| `input_tokens` | Integer | Tokens in request |
| `output_tokens` | Integer | Tokens in response |
| `latency_ms` | Integer | Request duration |
| `broker_id` | Integer | Broker (nullable) |
| `lead_id` | Integer | Lead (nullable) |
| `used_fallback` | Boolean | Whether fallback was triggered |
| `error` | String | Error message if failed (nullable) |

**Implementation:** Async fire-and-forget. Never blocks the main pipeline.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | Primary provider |
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` | Gemini model |
| `GEMINI_MAX_TOKENS` | `2048` | Max response tokens |
| `GEMINI_TEMPERATURE` | `0.7` | Response creativity |
| `GEMINI_THINKING_BUDGET` | `1024` | Thinking budget (if enabled) |
| `GEMINI_API_KEY` | — | API key (required) |
| `CLAUDE_MODEL` | (varies) | Claude model |
| `CLAUDE_API_KEY` | — | API key (required) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `OPENAI_API_KEY` | — | API key (required) |
| `GEMMA_MODEL` | `gemma-3-4b-it` | Lightweight model for qualification |

---

## Changelog

| Date | Version | Changes |
|---|---|---|
| 2026-04-17 | 1.0 | Initial documentation |