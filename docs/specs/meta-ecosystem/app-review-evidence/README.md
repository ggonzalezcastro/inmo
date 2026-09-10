# Meta App Review evidence pack

**Task:** 12.5 — Produce App Review evidence

**Local pack status:** structurally ready

**Submission status:** blocked on external reviewer access, real sandbox assets, recordings and an unaided internal review

This directory is the operator package for producing and validating the evidence submitted to Meta. It intentionally contains no passwords, access tokens, personal data or recordings.

## What is ready locally

- The 14 unique OAuth permissions requested by `CHANNEL_CONFIG` are inventoried in [manifest.json](./manifest.json).
- Every permission has an independent, copy-ready written review path in [permission-paths.md](./permission-paths.md).
- Recording conventions, clean-data requirements, credential delivery and the unaided review protocol are defined in [reviewer-runbook.md](./reviewer-runbook.md).
- Submission attempts and approval are controlled by [submission-log.json](./submission-log.json) and [submission-runbook.md](./submission-runbook.md).
- `python3 scripts/check_meta_app_review_evidence.py` detects drift between the code, manifest and written paths.
- Meta asset identifiers are visible in **Canales Meta → Identidades y activos**, so recordings can prove which remote asset was discovered.

## External work still required

1. Reconcile the requested permissions with the current **App Review → Permissions and Features** screen. Meta can change dependencies and screencast prompts independently of this repository.
2. Provision an isolated staging broker, CRM reviewer login and the sandbox assets listed in the runbook.
3. Record one video per permission using the exact filename in `manifest.json`, upload it through the private App Review handoff and set its `status` to `ready`, its `sha256` to the local file digest and its `submission_reference` to a non-secret attachment/request reference.
4. Set `reviewer_access.status` and `demo_data.status` to `ready` only after their preflight checks pass.
5. Have a person who did not prepare the package execute all paths without assistance. Record their name/date outside the repository, then set `internal_review.status` to `passed`.
6. Run the strict gate:

   ```bash
   python3 scripts/check_meta_app_review_evidence.py --require-complete
   ```

Task 12.5 must remain open until the strict gate passes. Submission itself belongs to task 12.6.

## Official references to recheck before recording

- [Meta permissions reference](https://developers.facebook.com/docs/permissions/)
- [Meta official Instagram API collection](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login)
- [Meta official Messenger Platform collection](https://www.postman.com/meta/messenger-platform-api/documentation/iyp204x/messenger-platform-api)
- [Meta official WhatsApp Business Platform collection](https://www.postman.com/meta/whatsapp-business-platform/documentation/wl)
- [Meta official Marketing API collection](https://www.postman.com/meta/facebook-marketing-api/documentation/0zr4mes/facebook-marketing-api-mapi)

The code deliberately keeps two Instagram authorization families separate: direct Instagram Login requests `instagram_business_*`; Meta Business/Facebook Login requests `instagram_basic` and `instagram_manage_messages` for Page-linked professional accounts.
