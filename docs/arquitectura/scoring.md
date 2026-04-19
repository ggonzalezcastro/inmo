# Lead Scoring System

**Document version:** 1.0  
**Last updated:** 2026-04-17  
**Status:** Confirmed (code-verified)

---

## Overview

Lead scores range from 0 to 100 and are calculated from four weighted components: financial health, key profile, engagement bonus, and penalties. The final score drives pipeline stage assignment (COLD / WARM / HOT) and determines lead qualification status.

---

## Score Structure

| Component | Range | Weight |
|---|---|---|
| Financial health | 0–60 pts | Primary |
| Key profile | 0–25 pts | Secondary |
| Engagement bonus | 0–15 pts | Tertiary |
| Penalties | −30–0 pts | Negative |

**Total possible:** 0–100 pts (penalties are subtractive)

---

## Component Calculations

### 1. Key Profile (0–25 pts)

Calculated from lead contact data. Stored contact fields are evaluated; placeholder values yield 0.

```python
def _calculate_key_profile(lead: Lead) -> int:
    pts = 0

    # Name (5 pts): real name present
    if lead.name and lead.name not in ["User", "Test User"]:
        pts += 5

    # Phone (10 pts): not a platform placeholder
    phone = lead.phone or ""
    if phone and not phone.startswith(("web_chat_", "whatsapp_", "+569999")):
        pts += 10

    # Income reported (10 pts)
    metadata = lead.lead_metadata or {}
    if metadata.get("monthly_income"):
        pts += 10

    return min(25, pts)
```

**Breakdown:**

| Field | Points | Condition |
|---|---|---|
| Name | 5 | `lead.name` is set and not `"User"` / `"Test User"` |
| Phone | 10 | `lead.phone` is set and does not start with `web_chat_`, `whatsapp_`, or `+569999` |
| Income reported | 10 | `lead.lead_metadata["monthly_income"]` is truthy |

---

### 2. Engagement Bonus (0–15 pts)

Tracks behavioral signals from message history and activity logs.

```python
def _calculate_engagement_bonus(messages: list, activities: list) -> int:
    pts = 0

    # 5+ messages (5 pts)
    if len(messages) >= 5:
        pts += 5

    # Quick response <5 min between first two messages (5 pts)
    sorted_msgs = sorted(messages, key=lambda m: m.created_at)
    if len(sorted_msgs) >= 2:
        m0, m1 = sorted_msgs[0], sorted_msgs[1]
        if m0.created_at and m1.created_at:
            diff = (m1.created_at - m0.created_at).total_seconds()
            if diff < 300:
                pts += 5

    # Active sessions 3+ activity log entries (5 pts)
    if len(activities) >= 3:
        pts += 5

    return min(15, pts)
```

**Breakdown:**

| Signal | Points | Condition |
|---|---|---|
| Message volume | 5 | 5 or more messages in conversation |
| Quick response | 5 | Time gap under 5 minutes (300 s) between the first two messages |
| Active sessions | 5 | 3 or more activity log entries |

---

### 3. Financial Health (0–60 pts)

Computed by `BrokerConfigService.calculate_financial_score()` using the broker's `BrokerLeadConfig.scoring_config`. The logic combines income tier brackets with DICOM credit status:

- Income tiers map to base points.
- DICOM status (`clean` / `dirty`) adjusts the final financial score.
- Configuration is per-broker; brokers can customize tier thresholds.

> **DICOM rule:** A lead with `dicom_status == "dirty"` must never be promised credit pre-approval or financing. The qualifier agent enforces this; no stage handoff is emitted when DICOM is dirty.

---

### 4. Penalties (−30 to 0 pts)

Subtracted from the gross score. Applied as a negative adjustment, capped at −30.

```python
def _calculate_penalties(lead: Lead, messages: list) -> int:
    penalties = 0

    # Blocklist (-30): "no llamar" or "bloqueado" in messages
    for msg in messages:
        if "no llamar" in text_lower or "bloqueado" in text_lower:
            return 30

    # Inactive >60 days (-5)
    if lead.last_contacted:
        days_since = (datetime.utcnow() - lead.last_contacted).days
        if days_since > 60:
            penalties += 5

    # Invalid phone (-10)
    metadata = lead.lead_metadata or {}
    if "invalid" in str(metadata.get("status", "")).lower():
        penalties += 10

    return penalties
```

**Breakdown:**

| Penalty | Deduction | Trigger |
|---|---|---|
| Blocklist | −30 | Any message contains `"no llamar"` or `"bloqueado"` (case-insensitive) |
| Inactive | −5 | More than 60 days since `last_contacted` |
| Bad phone | −10 | `lead.lead_metadata["status"]` contains `"invalid"` |

> Blocklist penalty returns immediately (highest priority). Penalties are not stacked; the function returns on first match.

---

## Score → Status Mapping

Thresholds are read from `BrokerLeadConfig`:

| Score range | Status | Constant |
|---|---|---|
| `0–20` | COLD | `cold_max_score = 20` |
| `21–50` | WARM | `warm_max_score = 50` |
| `51–100` | HOT | `hot_min_score = 50` |
| `75–100` | Qualified | `qualified_min_score = 75` |

```
0        20              50                    100
  |← COLD →|←──────── WARM ─────---|←──── HOT ──→|
                      75 ← qualified threshold
```

---

## Score Recalculation

### Triggers

| Trigger | Mechanism |
|---|---|
| Manual recalculation | `POST /leads/{id}/recalculate` endpoint |
| Post-qualification | After `QualifierAgent` completes analysis |
| Post-appointment | After appointment is successfully scheduled |

### Flow

1. Recalculation is requested (manual or event-driven).
2. Fresh data is fetched: messages, activities, DICOM status, broker config.
3. Each component is recomputed in isolation.
4. Scores are summed and clamped to `[0, 100]`.
5. `lead_score_components` is written back to the database.
6. Pipeline stage is updated if the status (COLD/WARM/HOT) changed.
7. WebSocket event `stage_changed` is broadcast to connected clients.

---

## Stored Components

Calculated scores are persisted on the `Lead` record as `lead_score_components`:

```python
lead_score_components = {
    "base": profile_score,      # 0-25  (key profile)
    "behavior": engagement,    # 0-15  (engagement bonus)
    "engagement": engagement,  # 0-15  (duplicate — kept for compat)
    "stage": 0,                # deprecated, always 0
    "financial": financial,    # 0-60  (financial health)
    "penalties": penalties     # -30 to 0
}
```

The `base` field is the gross key-profile score before penalties. The final `score` field on the lead is the sum of all components clamped to `[0, 100]`.

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-17 | Initial version. Document confirmed code behavior for score components, thresholds, and recalculation triggers. |
