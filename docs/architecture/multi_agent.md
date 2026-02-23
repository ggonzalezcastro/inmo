# Multi-Agent Architecture (TASK-026)

## Overview

The multi-agent system replaces the monolithic `ChatOrchestratorService` with a set of
**specialist agents** that each own a slice of the lead lifecycle. An `AgentSupervisor`
routes every incoming message to the correct agent and orchestrates **handoffs** when
a lead transitions between stages.

```
Lead Message
     │
     ▼
AgentSupervisor
     │
     ├─ should_handle? ──► QualifierAgent   (entrada → perfilamiento)
     ├─ should_handle? ──► SchedulerAgent   (calificacion_financiera)
     └─ should_handle? ──► FollowUpAgent    (agendado → seguimiento)
```

---

## Agents

| Agent | Class | Stages Owned | Hands Off To |
|---|---|---|---|
| **QualifierAgent** | `app.services.agents.qualifier` | `entrada`, `perfilamiento` | SchedulerAgent |
| **SchedulerAgent** | `app.services.agents.scheduler` | `calificacion_financiera` | FollowUpAgent |
| **FollowUpAgent** | `app.services.agents.follow_up` | `agendado`, `seguimiento`, `referidos` | — |
| **AgentSupervisor** | `app.services.agents.supervisor` | (meta, stateless) | — |

### QualifierAgent

Responsible for collecting all required lead data:

- **name**, **phone**, **email**, **salary / budget**, **location**, **DICOM status**

Key logic:
1. Calls `LLMServiceFacade.analyze_lead_qualification()` to extract structured data from the free-text message.
2. Merges extracted fields into `AgentContext.lead_data`.
3. **DICOM rule (critical)**: if `dicom_status == "dirty"`, no handoff is emitted regardless of how complete the other fields are.
4. Emits `HandoffSignal(target=SCHEDULER)` when `AgentContext.is_appointment_ready()` returns `True` and DICOM is not dirty.

### SchedulerAgent

Responsible for converting a pre-qualified lead into a booked property visit.

Key logic:
1. Presents available projects and proposes time slots.
2. Detects appointment confirmation via `_is_appointment_confirmed(user_msg, agent_response)` — a bilingual heuristic that requires both the **user** and the **agent** to use confirmation language.
3. Emits `HandoffSignal(target=FOLLOW_UP)` on confirmation.

### FollowUpAgent

Handles post-visit engagement: satisfaction check, referral collection, final conversion nudge.
Does **not** emit further handoffs (terminal agent for the current pipeline).

---

## Handoff Protocol

```python
@dataclass
class HandoffSignal:
    target_agent: AgentType      # where to route next
    reason: str                  # human-readable log message
    context_updates: dict = {}   # data to merge into AgentContext before handoff
```

The `AgentSupervisor` calls `agent.should_handoff(response, context)` after every
`process()` call.  The default `BaseAgent.should_handoff()` simply returns
`response.handoff` — agents set it themselves.

**Loop guard**: `_MAX_HANDOFFS = 3` in `supervisor.py` ensures the supervisor terminates
even if agents keep emitting handoffs.

---

## AgentContext

`AgentContext` is an **immutable snapshot** passed to each agent. It carries:

| Field | Type | Description |
|---|---|---|
| `lead_id` | int | DB primary key |
| `broker_id` | int | Owning broker |
| `pipeline_stage` | str | CRM stage string |
| `conversation_state` | str | State machine position |
| `lead_data` | dict | All collected fields |
| `message_history` | list | Prior turns |
| `current_agent` | AgentType? | Last agent that processed a message |
| `handoff_count` | int | Hops taken this session |

Helper methods:

```python
ctx.is_qualified()           # All required fields present AND DICOM not dirty
ctx.is_appointment_ready()   # is_qualified() AND location present
ctx.missing_fields()         # Returns list of human-readable missing field names
```

---

## Routing Priority

```
get_priority_agents() → [FollowUpAgent, SchedulerAgent, QualifierAgent]
```

More specific agents (FollowUp, Scheduler) are polled first to prevent premature
downgrade to the general Qualifier.

**Sticky routing**: if `context.current_agent` is set, that agent gets first pick
via `should_handle()` before the full priority poll runs.

---

## Feature Flag

```
MULTI_AGENT_ENABLED=true   # env var — disabled by default
```

The flag is checked in the chat route before calling `AgentSupervisor.process()`.
When disabled, the existing `ChatOrchestratorService` is used unchanged, ensuring
full backward compatibility.

---

## File Map

```
backend/app/services/agents/
├── __init__.py              # Singleton instances, get_priority_agents(), build_context()
├── types.py                 # AgentContext, AgentResponse, HandoffSignal, AgentType
├── base.py                  # BaseAgent ABC + agent registry
├── supervisor.py            # AgentSupervisor (routing + handoff orchestration)
├── qualifier.py             # QualifierAgent
├── scheduler.py             # SchedulerAgent + _is_appointment_confirmed()
├── follow_up.py             # FollowUpAgent
└── prompts/
    ├── __init__.py
    ├── qualifier_prompt.py  # QUALIFIER_SYSTEM_PROMPT
    ├── scheduler_prompt.py  # SCHEDULER_SYSTEM_PROMPT
    └── follow_up_prompt.py  # FOLLOW_UP_SYSTEM_PROMPT

backend/tests/services/
└── test_multi_agent.py      # 27 unit tests (all mocked — no real LLM calls)
```

---

## Running the Tests

```bash
# From backend/
.venv/bin/python -m pytest tests/services/test_multi_agent.py -v --noconftest
# Expected: 27 passed
```

`--noconftest` skips the integration `tests/conftest.py` that requires a live database.
The multi-agent tests are fully self-contained with mocked LLM calls.

---

## Extension Points

| What | Where |
|---|---|
| Add a new agent | Subclass `BaseAgent`, call `register_agent(instance)` in `__init__.py` |
| Change routing priority | Edit `get_priority_agents()` list order |
| Per-broker agent config | Extend `AgentContext` with `broker_config` dict |
| Persist handoff decisions | Hook into `AgentSupervisor.process()` after response |
| Real appointment booking | Replace `_is_appointment_confirmed()` heuristic with Google Calendar call |
