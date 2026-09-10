# External Meta and infrastructure setup runbook

This runbook covers the remaining external setup gates: 0.1–0.6, 5.6, 6.6, 12.2 and the remote portion of 12.4. Evidence references must be non-secret identifiers pointing to the approved operations system. Never commit asset inventories, credentials, screenshots containing tokens or private dashboard URLs.

Local preflight on 2026-09-09 found no complete Meta configuration in `.env` and the Railway CLI reported an unauthenticated session. These are recorded as blocking conditions in the manifest; no secret values were read or printed.

## Repository contract

```bash
python3 scripts/check_meta_external_setup.py
```

This validates the expected task set and `.env.example` variable contract. It does not claim that an external environment exists.

Strict cumulative gates:

```bash
python3 scripts/check_meta_external_setup.py --require-phase0 --env-file /secure/path/staging.env --target staging
python3 scripts/check_meta_external_setup.py --require-sandbox --env-file /secure/path/staging.env --target staging
python3 scripts/check_meta_external_setup.py --require-infrastructure --env-file /secure/path/production.env --target production
```

Multiple `--env-file` arguments compare Backend, Worker and Beat Meta settings without printing their values.

## 0.1 Ownership and access

Operations records outside Git:

- verified Meta business portfolio and domain;
- primary application owner and a separate backup owner;
- 2FA enabled for every administrator;
- least-privilege administrator/tester assignments;
- escalation contact and recovery procedure;
- product and operations sign-off.

Set task `0.1` to `passed` only after the signed checklist is stored and represented by a non-secret evidence reference.

## 0.2 Public legal and support pages

After legal approval, verify these unauthenticated HTTPS routes on the deployed frontend:

- `/privacy`
- `/terms`
- `/support`
- `/data-deletion`

The Meta data-deletion callback is the backend route `POST /webhooks/meta/data-deletion`; its response points to the public `/data-deletion?code=…` status page. Legal approval must cover the actual production text and retention behavior.

## 0.3 Meta Business app

The target app must contain WhatsApp, Webhooks, Facebook Login for Business, Instagram, Messenger, Marketing API and Lead Ads. Reconcile the current portal's product names and permission dependencies before taking evidence. The specification pins Graph API `v26.0`; changing it requires code, contract and regression review together.

## 0.4 Domains, redirects and callbacks

For each environment register the exact deployed host and these paths:

| Purpose | Path |
|---|---|
| OAuth base | `/api/v1/meta` |
| WhatsApp callback | `/api/v1/meta/connections/whatsapp/callback` |
| Instagram callback | `/api/v1/meta/connections/instagram/callback` |
| Messenger callback | `/api/v1/meta/connections/messenger/callback` |
| Business callback | `/api/v1/meta/connections/business/callback` |
| Webhook verification/events | `/webhooks/meta` |
| Deauthorization | `/webhooks/meta/deauthorize` |
| Data deletion | `/webhooks/meta/data-deletion` |

Staging and production must use HTTPS. Capture a real webhook challenge and a complete cancel/success OAuth redirect without placing state, code or tokens in the evidence tracker.

## 0.5 Sandbox assets

Store the inventory outside Git with asset ID, owner, environment and intended test. Required assets are one WABA, two phone numbers, one Facebook Page, corporate and executive professional Instagram accounts, one ad account, one Lead Ads form, one paused test campaign and one conversion dataset. Confirm none belongs to or contains data from a production customer.

## 0.6 Secrets and shared services

Backend, Worker and Beat must receive identical Meta app/version/encryption settings and the correct shared database/Redis topology. `/api/v1/meta/health` reports only presence booleans plus the legacy fallback state; it never returns values.

Required Meta variables:

- `META_APP_ID`
- `META_APP_SECRET`
- `META_GRAPH_API_VERSION`
- `META_WEBHOOK_VERIFY_TOKEN`
- `META_OAUTH_REDIRECT_BASE_URL`
- `META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID`
- `META_CREDENTIAL_ENCRYPTION_KEY`
- all Meta feature flags, including `META_WHATSAPP_LEGACY_FALLBACK_ENABLED`

## 5.6 and 6.6 sandbox evidence

Use `AR-IG-DIRECT-001` and `AR-FB-MSG-001` from the App Review runbook. Each real external user must initiate the conversation, Captame must create/link and assign one lead, an authorized human must reply through the same asset, and delivery/read events must update without duplicates. The recording and written path can then be referenced by both the sandbox task and its App Review permission.

## 12.2 and 12.4

Performance remains deferred until representative volume and peak-load profiles exist. Do not replace that gate with local timings. For Railway, execute every remote check in `railway-topology-review.md` against the linked environment and store a sanitized evidence reference.
