# Eval Baseline — Agent Quality Metrics

> **Established:** 2026-02-22
> **Dataset:** `backend/tests/evals/dataset/conversations.json` — 51 labeled conversations
> **Scope:** Sofía (AI real-estate qualification agent, Chilean market)

---

## Baseline Scores

| Metric | Score | Method | Threshold (CI) |
|--------|-------|--------|----------------|
| `answer_relevancy` | 0.8510 | Label-proxy / LLM judge (opt) | ≥ 0.80 |
| `faithfulness` | 0.8039 | Label-proxy / LLM judge (opt) | ≥ 0.75 |
| `task_completion` | 0.8431 | Deterministic regex | ≥ 0.79 |
| `dicom_rule_adherence` | 0.8039 | Deterministic regex | ≥ 0.75 |

> **Regression tolerance:** 5% below baseline triggers a CI failure.
> Formula: `threshold = baseline - 0.05`

---

## Metrics Description

### 1. `answer_relevancy`
**Definition:** Does the agent's response address the current state of the conversation?

- **Implementation:** `deepeval.AnswerRelevancyMetric` (LLM judge, requires `OPENAI_API_KEY`)
- **Proxy (always runs):** Label from dataset (`labels.answer_relevance` ∈ [0.0, 1.0])
- **Baseline interpretation:** 85.1% of responses are directly relevant to the user's message and pipeline stage.
- **Common failure patterns:** Generic responses that don't advance the qualification, repeating the same question after it was already answered.

### 2. `faithfulness`
**Definition:** Does the agent avoid inventing financial data not present in the knowledge context?

- **Implementation:** `deepeval.FaithfulnessMetric` (LLM judge, requires `OPENAI_API_KEY`)
- **Proxy (always runs):** Label from dataset (`labels.is_faithful` boolean)
- **Baseline interpretation:** 80.4% of all responses (including the 10 intentional violation cases) are faithful. Among non-violation cases, faithfulness is 100%.
- **Common failure patterns:** Inventing specific interest rates, property prices, or financing terms not found in the KB.

### 3. `task_completion`
**Definition:** Does the agent perform the conversational action expected at each turn in the pipeline?

- **Implementation:** `TaskCompletionMetric` — deterministic keyword/regex matching
- **No LLM judge required — always runs**
- **Expected actions include:** `ask_name`, `ask_phone`, `ask_dicom`, `ask_budget`, `schedule_visit`, `advise_regularization`, `decline_and_advise`, etc.
- **Baseline interpretation:** 84.3% of turns execute the expected action. Remaining ~16% are violation cases (where the agent gave incorrect advice) or actions with limited regex coverage.
- **Common failure patterns:** Skipping DICOM question after budget discussion, scheduling appointment before DICOM confirmation.

### 4. `dicom_rule_adherence`
**Definition:** The agent must **never** promise pre-approval, credit access, or financing to a lead who explicitly has active DICOM entries or outstanding delinquencies.

- **Implementation:** `DicomRuleMetric` — deterministic pattern matching
- **No LLM judge required — always runs**
- **Zero-tolerance rule:** Any forbidden promise with active debt context = score 0.0
- **Baseline interpretation:** 80.4% of all responses (including 10 designed violations) pass. 100% of compliant responses pass. 100% of violation cases are detected.
- **Forbidden patterns detected:**
  - `"puedes acceder al..."` (crédito, subsidio, etc.)
  - `"calificas para..."`
  - `"pre-aprobado/a/s"`, `"pre-aprobación"`, `"pre-aprobar"`
  - `"aprobado/a/s"`, `"aprobación"` in debt context
  - `"te podemos financiar"`, `"te podemos aprobar"`
  - `"financiar igual"`, `"igual puedes"`, `"cartera propia"`

---

## Dataset Structure

```
backend/tests/evals/dataset/
└── conversations.json    # 51 labeled conversation entries
```

### Entry Format

```json
{
  "id": "conv_001",
  "category": "initial_greeting",
  "pipeline_stage": "NEW",
  "input": "Lead's message",
  "actual_output": "Sofia's response (mock or real)",
  "expected_output": "Ideal reference response",
  "context": ["KB chunks if applicable"],
  "conversation_history": [],
  "labels": {
    "answer_relevance": 0.9,
    "is_faithful": true,
    "task_action_expected": "ask_name",
    "task_action_completed": true,
    "dicom_violation": false
  }
}
```

### Category Distribution

| Category | Count | Purpose |
|----------|-------|---------|
| `initial_greeting` | 5 | First contact, name request |
| `name_collection` | 3 | Collecting lead name |
| `contact_collection` | 7 | Phone/email collection |
| `budget_inquiry` | 6 | Financial profiling |
| `dicom_inquiry` | 9 | DICOM status handling |
| `dicom_violation` | 10 | Bad responses (metric calibration) |
| `appointment_scheduling` | 5 | Booking visits |
| `property_questions` | 5 | Property-specific Q&A |
| `disqualification` | 1 | Lead doesn't qualify |
| **Total** | **51** | |

---

## Running the Eval Suite

```bash
# Deterministic tests only (no API key, always safe for CI)
pytest tests/evals/ -v

# With LLM-judge metrics (answer_relevancy + faithfulness via GPT-4)
EVAL_LLM_ENABLED=true OPENAI_API_KEY=sk-... pytest tests/evals/ -v

# Regenerate baseline scores
python3 -c "
import sys; sys.path.insert(0, '.')
from tests.evals.test_agent_quality import compute_deterministic_baseline
import json
print(json.dumps(compute_deterministic_baseline(), indent=2))
"
```

---

## Updating the Baseline

After prompt changes that intentionally improve quality:

1. Run the eval suite and note new scores
2. Update `BASELINE` dict in `backend/tests/evals/test_agent_quality.py`
3. Update this document with the new scores and date
4. Commit both files together so the threshold tracks the intent

> ⚠️ **Do not** update the baseline to hide regressions. Only update when the change is intentional and the new score represents a genuine improvement.

---

## CI Integration

> Note: CI/CD pipeline (TASK-019) was intentionally skipped for this project phase.
> To integrate into CI, add this step to your pipeline:

```yaml
- name: Run agent quality eval
  run: |
    cd backend
    pytest tests/evals/ -v --tb=short
  env:
    EVAL_LLM_ENABLED: "false"   # deterministic only in CI
```

The `EVAL_LLM_ENABLED=true` variant should be run manually or on scheduled nightly jobs to avoid LLM API costs on every commit.
