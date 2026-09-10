# App Review operator and reviewer runbook

This runbook prepares the external evidence required by task 12.5. It is not a substitute for Meta's current permission-specific prompts. Reconcile those prompts in the App Dashboard before recording.

## 1. Credential handoff

Create a private handoff entry for the following values. Put them only in Meta App Review's secure reviewer fields or the approved password manager; never in Git, tickets, video captions or chat:

| Private value | Purpose | Preflight |
|---|---|---|
| Staging base URL | Opens the review environment | Public HTTPS; no VPN or IP allowlist |
| App Review Admin email/password | Signs in to Captame | Active; broker-scoped admin; no forced reset |
| Meta sandbox user access | Completes Meta/Facebook authorization | Can administer only the review business/assets |
| Instagram professional access | Completes direct Instagram Login | Business/Creator account; no personal content |
| External WA/IG/FB users | Initiate inbound conversations | Not the same identity as the business asset |
| MFA recovery procedure, if required | Prevents reviewer dead-end | Works without live staff intervention |

The CRM reviewer account must have the minimum application role that can execute every submitted path. In the current UI that is a broker `admin`; `superadmin` is intentionally excluded from the operational Meta screens.

## 2. Clean demo profile `AR-BASELINE-01`

Use a dedicated staging broker named **App Review Sandbox**. It must contain synthetic data only and be reset before each recording batch.

| Object | Required clean state |
|---|---|
| CRM users | One App Review Admin and one optional App Review Agent, both isolated to the staging broker |
| Project | `AR Parque Norte`, active and suitable for a housing campaign/form mapping |
| Leads | No prior `AR-*` marker leads before the batch |
| Conversations | No unread or conflicting conversations for the test external users |
| Campaigns | No existing `AR-ADS-MANAGE-001`; no active test campaign |
| Budget policy | Non-zero test limits sufficient to create the draft; actual spend remains disabled |
| Features | Global Meta enabled for staging; broker flags enabled only for permissions being recorded |
| Connections | Start disconnected for login/discovery videos; restore approved baseline for messaging videos |

Required Meta sandbox inventory:

- one verified review business portfolio;
- one WABA and one test business phone number;
- one direct-login Instagram Business/Creator account;
- one Facebook Page with a second professional Instagram account linked to it;
- one ad account with a historical, non-spending reporting campaign;
- one active Lead Ads test form connected to `AR Parque Norte`;
- one conversion dataset if dataset discovery is shown;
- independent external WhatsApp, Instagram and Facebook test identities.

Use marker values `AR-WA-001`, `AR-IG-DIRECT-001`, `AR-FB-ENGAGEMENT-001`, `AR-FB-WEBHOOK-001`, `AR-FB-MSG-001`, `AR-IG-LINKED-001`, `AR-ADS-MANAGE-001` and `AR-LEAD-001`. Use reserved/synthetic contact information and never a real prospect's PII.

## 3. Recording contract

Record one file for every permission in `manifest.json`.

- Use a clean browser profile at 1440×900 or higher and keep the address bar visible.
- Start from `/login` or from the clearly stated baseline in the permission path.
- Show the complete Meta/Instagram authorization when the permission's path requires it.
- Keep the mouse movement deliberate and show the relevant remote result, not only a success toast.
- Use the exact `AR-*` marker for that path so the event can be followed across Meta and Captame.
- Hide passwords, tokens, recovery codes, personal notifications and unrelated business assets.
- Do not demonstrate extra products or request broader permissions than the path needs.
- Record the final remote state: received message, discovered ID, synced metric, one deduplicated lead, or fully paused campaign.
- Use English narration or captions to translate the Spanish UI labels and state the permission being demonstrated.
- Preserve the source recording until task 12.6 is approved. Upload through the approved private channel; store only its SHA-256 digest and a non-secret attachment/request reference in `manifest.json`.

For `ads_management`, never activate delivery or incur spend. The evidence ends with campaign, ad set and ad in paused state in both Captame and Meta Ads Manager.

## 4. Per-batch preflight

Before recording, the operator verifies:

- callback URLs and the data-deletion/privacy URLs are public HTTPS;
- the app ID, Graph API version and products match the target Meta app;
- webhook verification and signed webhook delivery succeed;
- Worker, Beat and Redis are healthy and no relevant event is in the DLQ;
- each test asset is owned by or shared with the review business and not used by production;
- all expected feature flags are enabled only in the review broker;
- the browser and recording contain no production PII or secrets;
- every permission is still requested by the corresponding code flow and present in the current App Review portal.

If the portal declares an additional dependency for a permission (especially Lead Ads), stop the recording batch and reconcile code, requirements, manifest and justification together. Do not silently add a broader OAuth scope or submit evidence for a permission the runtime does not request.

## 5. Unaided internal review

The internal reviewer must not be the person who wrote the paths, prepared the data or recorded the videos.

1. Give the reviewer only the same private handoff and written paths that Meta will receive.
2. Do not answer questions while the run is in progress.
3. Require every path to reach its stated **Expected proof** with the correct `AR-*` marker.
4. Record pass/fail, date, permission, first blocking step and screenshot/video timestamp outside Git.
5. A failed or ambiguous path returns to preparation; do not explain around it in the submission.
6. Set `internal_review.status` to `passed` only when all 14 paths complete unaided in a single clean-data cycle.

The strict repository gate is:

```bash
python3 scripts/check_meta_app_review_evidence.py --require-complete
```

Passing the structural check without `--require-complete` means the package is internally consistent, not that task 12.5 is complete.
