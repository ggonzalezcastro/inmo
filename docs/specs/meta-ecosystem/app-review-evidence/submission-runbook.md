# App Review submission and response runbook

This runbook controls task 12.6. It contains no Meta credentials, reviewer credentials, raw rejection messages or private evidence links.

## Submission gate

Do not submit until all of the following are true:

1. `python3 scripts/check_meta_app_review_evidence.py --require-complete` passes.
2. The Instagram and Messenger sandbox flows in tasks 5.6 and 6.6 have real captured evidence.
3. Public HTTPS privacy, terms, support and data-deletion pages have completed legal review.
4. Business verification, domain, 2FA, app owner and backup owner are confirmed.
5. Every permission in the current Meta portal matches `manifest.json`; declared dependencies have been reconciled with the OAuth code.
6. The supplied reviewer can enter staging and execute every path without live assistance.

## Initial submission

- Create one permission request entry for every permission in `submission-log.json`.
- Paste the matching section from `permission-paths.md`; replace bracketed values only in the private portal.
- Attach the video whose digest and submission reference are recorded in `manifest.json`.
- Use the same asset names and `AR-*` markers in the text, video and live reviewer environment.
- Request no permission that the runtime does not request and demonstrate no unrelated product.
- Set the permission status to `submitted`; record only a non-secret request reference and timestamps in `attempts`.

## Requested-change loop

For each response:

1. Preserve the original evidence and add an attempt entry with a concise, sanitized change summary.
2. Reproduce the reviewer's issue using the supplied reviewer account and clean baseline.
3. Change the smallest relevant path, UI evidence or implementation. Do not broaden scopes to avoid an evidence problem.
4. Rerun the directed code tests, the structural evidence validator and an unaided internal review for the affected permission.
5. Record a new video with a new SHA-256 digest and update the submission reference.
6. Resubmit only the affected permission unless Meta explicitly requires a dependency to be resubmitted.

Allowed permission states are `not_submitted`, `submitted`, `changes_requested`, `approved`, `rejected` and `not_required`.

## Approval gate

After Meta reports all required permissions approved and the app is Live, update the sanitized tracker and run:

```bash
python3 scripts/check_meta_app_review_evidence.py --require-approved
```

Only that strict command closes task 12.6. Approval does not enable a production broker; rollout starts with task 12.7.
