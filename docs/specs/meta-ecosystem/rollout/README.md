# Meta rollout, rollback and retirement runbook

This directory controls tasks 12.7–12.10. The manifest contains sanitized status and non-secret references only. Production credentials, broker names, customer data and dashboard links stay in the approved operations system.

## Structural check

```bash
python3 scripts/check_meta_rollout.py
```

The default command validates stage order and manifest shape. Strict gates are cumulative:

```bash
python3 scripts/check_meta_rollout.py --require-canary
python3 scripts/check_meta_rollout.py --require-cohorts
python3 scripts/check_meta_rollout.py --require-retirement
python3 scripts/check_meta_rollout.py --require-secrets-removed
```

## 12.7 Canary

Global product switches may be enabled only after App Review, but broker overrides keep every non-canary broker disabled. Start with `META_WHATSAPP_LEGACY_FALLBACK_ENABLED=true` so rollback remains available.

Activate one internal broker in this order:

1. `whatsapp`
2. `instagram`
3. `messenger`
4. `ads`
5. `lead_ads`

For each stage, pass the asset/permission preflight, enable only that broker override, execute the real sandbox/production path, inspect queues/DLQ/audit/remote state, and set `validated_at` before starting the next stage. The entire canary window must span at least seven days.

Required zero outcomes are message loss, duplicate effects and unexplained spend. `ads` evidence ends with a remotely paused campaign unless a separately approved spend test exists.

Rollback exercise:

- disable the affected broker override;
- for WhatsApp, keep the explicit legacy fallback enabled during canary;
- verify queued events become visible/recoverable and no event is silently duplicated;
- restore only after the incident owner signs the result.

## 12.8 Cohorts

Create a manifest entry for every planned broker cohort. Each entry requires:

- a non-secret cohort reference;
- passed asset/permission/connection-health preflight;
- activation and validation timestamps;
- zero message loss, duplicate effects and unexplained spend;
- signed operational acceptance stored outside Git and represented by a non-secret reference.

Do not start a cohort until the prior cohort is validated. A failed cohort stops later cohorts and uses the exercised rollback.

## 12.9 Legacy fallback retirement

The runtime now exposes `META_WHATSAPP_LEGACY_FALLBACK_ENABLED` separately from asset-aware routing. It increments `meta_legacy_fallback_total{direction,reason,result}` and emits the same low-cardinality decision to application logs whenever the legacy path is entered or blocked. Neither signal includes tenant, recipient, message or credential data.

Retirement order:

1. Complete all cohorts.
2. Record two distinct stable releases with the fallback still available.
3. Observe zero legacy reads for the designated release.
4. Set `META_WHATSAPP_LEGACY_FALLBACK_ENABLED=false` in Backend, Worker and Beat together.
5. Deploy a new release and monitor it to completion. A blocked legacy attempt is an incident, not evidence of zero reads.

The public application must not expose credential values. `/api/v1/meta/health` reports only configuration-presence booleans and the legacy fallback state.

## 12.10 Legacy secret removal

Secret deletion is intentionally last and is not executed by this repository preparation. Before creating or applying the destructive migration:

1. Pass `--require-retirement`.
2. Create and verify a recoverable database backup.
3. Run the read-only inventory and confirm every legacy access token has an encrypted asset mapping:

   ```bash
   cd backend
   python -m scripts.audit_meta_legacy_secrets
   python -m scripts.audit_meta_legacy_secrets --require-migrated
   ```

4. Remove legacy secret fields from `broker_chat_configs.provider_configs.whatsapp` while preserving non-secret asset identifiers needed for audit.
5. Remove global legacy WhatsApp secrets from all runtime services.
6. Run `python -m scripts.audit_meta_legacy_secrets --require-retired`, the database verification and repository/runtime secret scans.
7. Keep the rollback procedure until the monitored release is accepted.

Only after the migration has actually run and the final strict gate passes may tasks 12.9 and 12.10 be checked off.
