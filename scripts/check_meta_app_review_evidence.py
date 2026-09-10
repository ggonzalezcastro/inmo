#!/usr/bin/env python3
"""Validate the Meta App Review evidence manifest against the OAuth source."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ONBOARDING_PATH = REPO_ROOT / "backend/app/services/meta/onboarding.py"
EVIDENCE_DIR = REPO_ROOT / "docs/specs/meta-ecosystem/app-review-evidence"
MANIFEST_PATH = EVIDENCE_DIR / "manifest.json"
SUBMISSION_PATH = EVIDENCE_DIR / "submission-log.json"
READY_STATES = {"ready"}
VIDEO_STATES = {"pending_recording", "ready"}
EXTERNAL_STATES = {"pending_external", "ready"}
REVIEW_STATES = {"pending_external", "passed"}
SUBMISSION_STATES = {
    "not_submitted",
    "submitted",
    "changes_requested",
    "approved",
    "rejected",
    "not_required",
}


def channel_config() -> dict[str, dict[str, object]]:
    tree = ast.parse(ONBOARDING_PATH.read_text(encoding="utf-8"), filename=str(ONBOARDING_PATH))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "CHANNEL_CONFIG" for target in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict):
                break
            return value
    raise ValueError(f"CHANNEL_CONFIG literal not found in {ONBOARDING_PATH}")


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate(require_complete: bool, require_approved: bool = False) -> list[str]:
    errors: list[str] = []
    config = channel_config()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    paths_text = (EVIDENCE_DIR / "permission-paths.md").read_text(encoding="utf-8")

    expected_flows: dict[str, set[str]] = {}
    for flow, settings in config.items():
        scopes = settings.get("scopes") if isinstance(settings, dict) else None
        if not isinstance(scopes, list):
            errors.append(f"CHANNEL_CONFIG[{flow!r}].scopes is not a list")
            continue
        for permission in scopes:
            if not isinstance(permission, str):
                errors.append(f"CHANNEL_CONFIG[{flow!r}] contains a non-string permission")
                continue
            expected_flows.setdefault(permission, set()).add(flow)

    entries = manifest.get("permissions")
    if not isinstance(entries, list):
        return ["manifest.permissions must be a list"]

    seen: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"permissions[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        permission = entry.get("permission")
        if not isinstance(permission, str) or not permission:
            errors.append(f"{label}.permission must be a non-empty string")
            continue
        if permission in seen:
            errors.append(f"duplicate permission: {permission}")
        seen.add(permission)

        flows = entry.get("oauth_flows")
        if not isinstance(flows, list) or set(flows) != expected_flows.get(permission, set()):
            errors.append(
                f"{permission}: oauth_flows {flows!r} do not match code "
                f"{sorted(expected_flows.get(permission, set()))!r}"
            )

        expected_written_path = f"permission-paths.md#{permission}"
        if entry.get("written_path") != expected_written_path:
            errors.append(f"{permission}: written_path must be {expected_written_path!r}")
        if f"## `{permission}`" not in paths_text:
            errors.append(f"{permission}: missing independent heading in permission-paths.md")

        video = entry.get("video")
        if not isinstance(video, dict):
            errors.append(f"{permission}: video must be an object")
            continue
        if video.get("filename") != f"{permission}.mp4":
            errors.append(f"{permission}: video filename must be {permission}.mp4")
        if video.get("status") not in VIDEO_STATES:
            errors.append(f"{permission}: invalid video status {video.get('status')!r}")
        if video.get("status") == "ready" and not is_sha256(video.get("sha256")):
            errors.append(f"{permission}: ready video requires a lowercase SHA-256 digest")
        if video.get("status") == "ready" and not isinstance(video.get("submission_reference"), str):
            errors.append(f"{permission}: ready video requires a non-secret submission_reference")
        if video.get("status") == "ready" and not str(video.get("submission_reference") or "").strip():
            errors.append(f"{permission}: ready video requires a non-empty submission_reference")
        if require_complete and video.get("status") not in READY_STATES:
            errors.append(f"{permission}: video is not ready")

    missing = set(expected_flows) - seen
    extra = seen - set(expected_flows)
    if missing:
        errors.append(f"permissions missing from manifest: {sorted(missing)}")
    if extra:
        errors.append(f"permissions not requested by code: {sorted(extra)}")

    submission = json.loads(SUBMISSION_PATH.read_text(encoding="utf-8"))
    submission_entries = submission.get("permissions")
    if not isinstance(submission_entries, list):
        errors.append("submission-log.permissions must be a list")
        submission_entries = []
    submitted_seen: set[str] = set()
    for index, entry in enumerate(submission_entries):
        label = f"submission-log.permissions[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        permission = entry.get("permission")
        if not isinstance(permission, str) or not permission:
            errors.append(f"{label}.permission must be a non-empty string")
            continue
        if permission in submitted_seen:
            errors.append(f"submission-log has duplicate permission: {permission}")
        submitted_seen.add(permission)
        status = entry.get("status")
        if status not in SUBMISSION_STATES:
            errors.append(f"{permission}: invalid submission status {status!r}")
        if not isinstance(entry.get("attempts"), list):
            errors.append(f"{permission}: attempts must be a list")
        if require_approved and status not in {"approved", "not_required"}:
            errors.append(f"{permission}: App Review is not approved")
    if submitted_seen != seen:
        errors.append(
            "submission-log permissions do not match manifest: "
            f"missing={sorted(seen - submitted_seen)}, extra={sorted(submitted_seen - seen)}"
        )

    portal = manifest.get("portal_reconciliation", {})
    if portal.get("status") not in EXTERNAL_STATES:
        errors.append("portal_reconciliation.status must be pending_external or ready")
    reviewer_access = manifest.get("reviewer_access", {})
    if reviewer_access.get("status") not in EXTERNAL_STATES:
        errors.append("reviewer_access.status must be pending_external or ready")
    demo_data = manifest.get("demo_data", {})
    if demo_data.get("status") not in EXTERNAL_STATES:
        errors.append("demo_data.status must be pending_external or ready")
    internal_review = manifest.get("internal_review", {})
    if internal_review.get("status") not in REVIEW_STATES:
        errors.append("internal_review.status must be pending_external or passed")

    if require_complete:
        for key, value in (
            ("portal_reconciliation", portal.get("status")),
            ("reviewer_access", reviewer_access.get("status")),
            ("demo_data", demo_data.get("status")),
        ):
            if value != "ready":
                errors.append(f"{key}.status is not ready")
        if internal_review.get("status") != "passed":
            errors.append("internal_review.status is not passed")

    if require_approved:
        if submission.get("business_verification") != "ready":
            errors.append("submission-log.business_verification is not ready")
        if submission.get("data_use_checkup") != "ready":
            errors.append("submission-log.data_use_checkup is not ready")
        if submission.get("app_mode") != "live":
            errors.append("submission-log.app_mode is not live")
        if not str(submission.get("app_review_request_reference") or "").strip():
            errors.append("submission-log.app_review_request_reference is missing")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="also require portal reconciliation, reviewer access, demo data, videos and internal review",
    )
    parser.add_argument(
        "--require-approved",
        action="store_true",
        help="require the 12.5 evidence gate plus approved permissions and Live app mode",
    )
    args = parser.parse_args()
    errors = validate(args.require_complete or args.require_approved, args.require_approved)
    if errors:
        print("Meta App Review evidence check: FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    mode = "approved" if args.require_approved else "complete" if args.require_complete else "structural"
    permission_count = len(json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["permissions"])
    print(f"Meta App Review evidence check: PASS ({mode})")
    print(
        f"- {permission_count} code permissions mapped to "
        f"{permission_count} independent written paths, video slots and submission records"
    )
    if not args.require_complete:
        print("- External completion is intentionally not asserted; use --require-complete for task 12.5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
