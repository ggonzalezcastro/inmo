# Voice Integration Architecture

**Date:** 2026-04-17
**Status:** Confirmed

---

## Overview

The voice integration enables outbound telephone calls to leads via VAPI (primary provider) and Bland AI (fallback). Calls are initiated through campaign steps, tracked in the database, and support recording, transcription, and cost attribution.

---

## VoiceCall Model

```python
class VoiceCall(Base):
    __tablename__ = "voice_calls"

    id: int (PK)
    lead_id: int (FK, indexed)
    broker_id: int (FK, indexed)
    campaign_id: int (FK, nullable)
    external_call_id: str(255)          # VAPI/Bland AI call ID
    phone_number: str(20)                # Destination phone
    status: CallStatus                    # Current call status
    duration: int                         # Duration in seconds
    recording_url: str(500)               # URL to call recording
    transcript: Text                     # Full call transcript
    cost_usd: Numeric(10, 6)             # Cost in USD
    started_at: DateTime
    ended_at: DateTime
    created_at: DateTime
    updated_at: DateTime
```

### Indexes

- `idx_voice_calls_lead_id` on `lead_id`
- `idx_voice_calls_broker_id` on `broker_id`
- `idx_voice_calls_campaign_id` on `campaign_id`
- `idx_voice_calls_status` on `status`
- `idx_voice_calls_external_call_id` on `external_call_id`

---

## CallStatus Enum

```python
class CallStatus(str, Enum):
    INITIATED = "initiated"    # Call placed, awaiting answer
    RINGING = "ringing"        # Destination is ringing
    ANSWERED = "answered"      # Call answered by recipient
    COMPLETED = "completed"    # Call finished normally
    FAILED = "failed"          # Technical failure
    NO_ANSWER = "no_answer"    # No answer from recipient
    BUSY = "busy"              # Line busy
    CANCELLED = "cancelled"    # Call cancelled before completion
```

### Status Transitions

```
INITIATED → RINGING → ANSWERED → COMPLETED
                ↓         ↓
              NO_ANSWER   FAILED
                ↓         ↓
             CANCELLED  CANCELLED
                       BUSY → CANCELLED
```

---

## VoiceCallService

### initiate_call()

```python
class VoiceCallService:
    @staticmethod
    async def initiate_call(
        db,
        lead_id: int,
        campaign_id: int,
        broker_id: int,
        agent_type: str = "default"
    ) -> VoiceCall:
        """
        Initiate an outbound voice call to a lead.

        Steps:
        1. Retrieve lead phone number from database
        2. Create VoiceCall record with status=INITIATED
        3. Call VAPI/Bland AI API with phone number and agent config
        4. Update VoiceCall with external_call_id from provider
        5. Return VoiceCall record
        """
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `db` | Session | Database session |
| `lead_id` | int | Target lead ID |
| `campaign_id` | int | Campaign attribution ID |
| `broker_id` | int | Broker (tenant) ID |
| `agent_type` | str | Voice agent template (default: "default") |

**Returns:** `VoiceCall` record

**Raises:** `LeadPhoneNotFoundError` if lead has no phone number

---

## VAPI Integration

### Configuration

VAPI is configured via environment variables:

```bash
VAPI_API_KEY=                    # VAPI API key
VAPI_PHONE_NUMBER_ID=           # VAPI configured phone number ID
VAPI_WORKFLOW_ID=               # Optional: VAPI workflow ID
VAPI_PROVIDER=                  # Provider selection (vapi|bland)
```

### Provider Selection

The voice service supports multiple backends:

- **VAPI** (primary): Full-featured voice with AI agents
- **Bland AI** (fallback): Alternative voice provider

Selection is made via `VOICE_PROVIDER` environment variable or per-request configuration.

### VAPI Call Flow

```python
# Pseudocode for VAPI call initiation
async def place_vapi_call(phone_number: str, agent_config: dict) -> str:
    payload = {
        "phone_number_id": os.getenv("VAPI_PHONE_NUMBER_ID"),
        "customer": {
            "number": phone_number,
        },
        "agent": agent_config,
    }
    response = await vapi_client.calls.create(payload)
    return response["id"]  # external_call_id
```

### Agent Configuration

Agent configuration is retrieved based on `agent_type`:

1. Fetch broker prompt configuration
2. Load voice-specific instructions
3. Set model, language, and personality parameters
4. Pass to VAPI as agent config

---

## Call Lifecycle

### Phase 1: Initiation

```
Campaign Step Executes
        ↓
VoiceCallService.initiate_call()
        ↓
   ┌────────────────────┐
   │ Create VoiceCall   │
   │ status=INITIATED   │
   │ phone=lead.phone   │
   └────────────────────┘
        ↓
   Call VAPI API
        ↓
   ┌────────────────────┐
   │ Update external_   │
   │ call_id            │
   └────────────────────┘
        ↓
   Return VoiceCall
```

### Phase 2: Connection

VAPI handles the outbound connection:

1. VAPI dials the `phone_number`
2. Status transitions: `INITIATED → RINGING`
3. Lead answers → status: `ANSWERED`
4. No answer → status: `NO_ANSWER` after timeout

### Phase 3: Active Call

During the call:

- Recording may be enabled
- Real-time transcription if supported
- Duration tracked via `started_at` timestamp

### Phase 4: Completion

Call ends → final status update:

| Outcome | Final Status |
|---------|--------------|
| Normal end | `COMPLETED` |
| Technical error | `FAILED` |
| No answer | `NO_ANSWER` |
| Line busy | `BUSY` |
| Cancelled | `CANCELLED` |

Final update includes:
- `ended_at`: End timestamp
- `duration`: Calculated from `started_at` and `ended_at`
- `cost_usd`: Provider-reported cost
- `recording_url`: If recording enabled
- `transcript`: If transcription enabled

---

## Transcript Storage

### Storage Schema

```python
VoiceCall.transcript: Text  # Full call transcript
VoiceCall.recording_url: str(500)  # Recording audio URL
```

### Transcript Contents

The transcript field stores:

- Full conversation text (agent + lead)
- Timestamps if available from provider
- Speaker labels (agent/lead) if supported by provider

### Transcript Usage

Transcripts are used for:

1. **Lead qualification analysis**: LLM reads transcript to score lead
2. **Activity logging**: Stored in lead activity timeline
3. **Training data**: Anonymous use for model improvement
4. **Dispute resolution**: Customer service review

---

## Campaign Integration

### Campaign Step Configuration

Voice calls are triggered by campaign steps:

```json
{
  "action": "make_call",
  "agent_type": "qualifier",
  "priority": "high",
  "retry_on_failure": true,
  "max_retries": 2
}
```

### Execution Flow

```python
async def execute_campaign_step(step: CampaignStep, lead: Lead, db: Session):
    if step.action == "make_call":
        voice_call = await VoiceCallService.initiate_call(
            db=db,
            lead_id=lead.id,
            campaign_id=step.campaign_id,
            broker_id=lead.broker_id,
            agent_type=step.config.get("agent_type", "default")
        )
        # Create activity log entry
        await log_activity(
            db=db,
            lead_id=lead.id,
            activity_type="voice_call_initiated",
            metadata={"voice_call_id": voice_call.id}
        )
```

### Attribution

Calls are attributed via `campaign_id` on the VoiceCall record:

- Campaign performance metrics
- Lead source attribution
- Cost per acquisition by campaign

---

## Cost Tracking

### Cost Fields

```python
VoiceCall.cost_usd: Numeric(10, 6)  # e.g., 0.023456 USD
```

### Cost Components

| Component | Description |
|-----------|-------------|
| VAPI connect fee | Per-call connection fee |
| VAPI duration fee | Per-minute charge |
| AI agent usage | LLM inference costs (separate) |
| Recording storage | Data storage costs (separate) |

### Cost Attribution

Costs are tracked at multiple levels:

1. **VoiceCall record**: Individual call cost
2. **Campaign aggregate**: Total campaign voice costs
3. **Broker aggregate**: Total broker voice costs
4. **LLM_calls table**: Separate LLM analysis costs

---

## Error Handling

### Error Types

| Error | Handling |
|-------|----------|
| `LeadPhoneNotFoundError` | Skip call, log warning |
| `VAPIConnectionError` | Retry with exponential backoff |
| `VAPIAuthError` | Alert ops, fail immediately |
| `CallTimeoutError` | Mark as NO_ANSWER |

### Retry Logic

Calls configured with `retry_on_failure=true` are retried up to `max_retries` times:

```python
async def initiate_call_with_retry(config: dict) -> VoiceCall | None:
    for attempt in range(config["max_retries"] + 1):
        try:
            return await VoiceCallService.initiate_call(...)
        except (VAPIConnectionError, CallTimeoutError):
            if attempt < config["max_retries"]:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            continue
    # All retries failed
    return None
```

---

## Database Schema

### Table: voice_calls

```sql
CREATE TABLE voice_calls (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    broker_id INTEGER NOT NULL REFERENCES brokers(id),
    campaign_id INTEGER REFERENCES campaigns(id),
    external_call_id VARCHAR(255),
    phone_number VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'initiated',
    duration INTEGER DEFAULT 0,
    recording_url VARCHAR(500),
    transcript TEXT,
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_voice_calls_lead_id ON voice_calls(lead_id);
CREATE INDEX idx_voice_calls_broker_id ON voice_calls(broker_id);
CREATE INDEX idx_voice_calls_campaign_id ON voice_calls(campaign_id);
CREATE INDEX idx_voice_calls_status ON voice_calls(status);
CREATE INDEX idx_voice_calls_external_call_id ON voice_calls(external_call_id);
```

---

## Related Components

| Component | File | Purpose |
|-----------|------|---------|
| VoiceCall model | `app/models/voice.py` | Database model |
| VoiceCallService | `app/services/voice/service.py` | Business logic |
| VAPI provider | `app/services/voice/vapi.py` | VAPI API client |
| Bland provider | `app/services/voice/bland.py` | Bland AI client |
| Campaign executor | `app/tasks/campaign_executor.py` | Triggers voice calls |
| Celery tasks | `app/tasks/voice_tasks.py` | Async voice processing |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-04-17 | Initial document creation |
| 2026-04-17 | Added VAPI integration details |
| 2026-04-17 | Documented campaign step trigger flow |
| 2026-04-17 | Added cost tracking and attribution |
