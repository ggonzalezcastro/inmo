#!/usr/bin/env python3
"""Validate ordered Meta canary, cohort, fallback and secret-retirement gates."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs/specs/meta-ecosystem/rollout/manifest.json"
EXPECTED_STAGES = ["whatsapp", "instagram", "messenger", "ads", "lead_ads"]
RUN_STATES = {"pending_external", "running", "passed", "failed", "rolled_back"}
CHECK_STATES = {"pending_external", "passed", "failed"}


def parse_time(value: object, field: str, errors: list[str]) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(f"{field} must be an ISO-8601 string or null")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} is not a valid ISO-8601 timestamp")
        return None


def validate(
    *,
    require_canary: bool,
    require_cohorts: bool,
    require_retirement: bool,
    require_secrets_removed: bool,
) -> list[str]:
    errors: list[str] = []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("stage_order") != EXPECTED_STAGES:
        errors.append(f"stage_order must be {EXPECTED_STAGES!r}")

    canary = manifest.get("canary", {})
    if canary.get("status") not in RUN_STATES:
        errors.append("canary.status is invalid")
    stages = canary.get("stages")
    if not isinstance(stages, list) or [item.get("name") for item in stages if isinstance(item, dict)] != EXPECTED_STAGES:
        errors.append("canary.stages must contain the exact ordered stage list")
        stages = []
    enabled_times: list[datetime] = []
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            errors.append(f"canary.stages[{index}] must be an object")
            continue
        name = stage.get("name")
        if stage.get("status") not in RUN_STATES:
            errors.append(f"canary stage {name}: invalid status")
        enabled = parse_time(stage.get("enabled_at"), f"canary stage {name}.enabled_at", errors)
        validated = parse_time(stage.get("validated_at"), f"canary stage {name}.validated_at", errors)
        if enabled:
            enabled_times.append(enabled)
        if enabled and validated and validated < enabled:
            errors.append(f"canary stage {name}: validated_at precedes enabled_at")
        if require_canary and stage.get("status") != "passed":
            errors.append(f"canary stage {name} is not passed")
        if require_canary and (not enabled or not validated):
            errors.append(f"canary stage {name} lacks timestamps")
    if enabled_times != sorted(enabled_times):
        errors.append("canary stages were not enabled in manifest order")

    started = parse_time(canary.get("started_at"), "canary.started_at", errors)
    ended = parse_time(canary.get("ended_at"), "canary.ended_at", errors)
    if started and ended and ended < started:
        errors.append("canary.ended_at precedes canary.started_at")
    if require_canary:
        if canary.get("status") != "passed":
            errors.append("canary.status is not passed")
        if not str(canary.get("broker_reference") or "").strip():
            errors.append("canary.broker_reference is missing")
        if not started or not ended or ended - started < timedelta(days=7):
            errors.append("canary observation window is shorter than seven days")
        if canary.get("rollback_exercise") != "passed":
            errors.append("canary.rollback_exercise is not passed")
        outcomes = canary.get("outcomes", {})
        for key in ("message_loss", "duplicate_effects", "unexplained_spend_events"):
            if outcomes.get(key) != 0:
                errors.append(f"canary.outcomes.{key} must be zero")

    cohort_rollout = manifest.get("cohort_rollout", {})
    if cohort_rollout.get("status") not in RUN_STATES:
        errors.append("cohort_rollout.status is invalid")
    cohorts = cohort_rollout.get("cohorts")
    if not isinstance(cohorts, list):
        errors.append("cohort_rollout.cohorts must be a list")
        cohorts = []
    prior_validated: datetime | None = None
    references: set[str] = set()
    for index, cohort in enumerate(cohorts):
        if not isinstance(cohort, dict):
            errors.append(f"cohort_rollout.cohorts[{index}] must be an object")
            continue
        reference = str(cohort.get("reference") or "").strip()
        if not reference:
            errors.append(f"cohort {index}: reference is missing")
        elif reference in references:
            errors.append(f"duplicate cohort reference: {reference}")
        references.add(reference)
        if cohort.get("status") not in RUN_STATES:
            errors.append(f"cohort {reference or index}: invalid status")
        activated = parse_time(cohort.get("activated_at"), f"cohort {reference or index}.activated_at", errors)
        validated = parse_time(cohort.get("validated_at"), f"cohort {reference or index}.validated_at", errors)
        if prior_validated and activated and activated < prior_validated:
            errors.append(f"cohort {reference}: activated before prior cohort validation")
        if activated and validated and validated < activated:
            errors.append(f"cohort {reference}: validated_at precedes activated_at")
        if validated:
            prior_validated = validated
        if require_cohorts:
            if cohort.get("preflight") != "passed":
                errors.append(f"cohort {reference}: preflight is not passed")
            if cohort.get("status") != "passed":
                errors.append(f"cohort {reference}: status is not passed")
            if not str(cohort.get("operational_acceptance_reference") or "").strip():
                errors.append(f"cohort {reference}: operational acceptance is missing")
            if not activated or not validated:
                errors.append(f"cohort {reference}: timestamps are missing")
    if require_cohorts:
        if cohort_rollout.get("status") != "passed":
            errors.append("cohort_rollout.status is not passed")
        if not cohorts:
            errors.append("cohort_rollout has no cohorts")

    retirement = manifest.get("legacy_retirement", {})
    if retirement.get("status") not in RUN_STATES:
        errors.append("legacy_retirement.status is invalid")
    releases = retirement.get("stable_releases_before_disable")
    if not isinstance(releases, list):
        errors.append("stable_releases_before_disable must be a list")
        releases = []
    versions = [str(item.get("version") or "") for item in releases if isinstance(item, dict)]
    if len(versions) != len(set(versions)):
        errors.append("stable releases must have distinct versions")
    if require_retirement:
        if retirement.get("status") != "passed":
            errors.append("legacy_retirement.status is not passed")
        if len(releases) < 2 or any(item.get("status") != "stable" for item in releases if isinstance(item, dict)):
            errors.append("at least two stable releases are required before disabling fallback")
        observation = retirement.get("zero_read_observation", {})
        if observation.get("legacy_reads") != 0 or not str(observation.get("release") or "").strip():
            errors.append("zero_read_observation must identify a release with zero legacy reads")
        if retirement.get("fallback_disabled") is not True:
            errors.append("legacy fallback is not disabled")
        disabled_release = str(retirement.get("disabled_in_release") or "").strip()
        monitor_release = str(retirement.get("monitor_release") or "").strip()
        if not disabled_release or not monitor_release or disabled_release == monitor_release:
            errors.append("distinct disable and monitor releases are required")
        if retirement.get("monitor_release_complete") is not True:
            errors.append("fallback-disabled monitor release is incomplete")

    secrets = manifest.get("secret_retirement", {})
    if secrets.get("status") not in RUN_STATES:
        errors.append("secret_retirement.status is invalid")
    for key in ("database_verification", "secret_scan"):
        if secrets.get(key) not in CHECK_STATES:
            errors.append(f"secret_retirement.{key} is invalid")
    if require_secrets_removed:
        if secrets.get("status") != "passed":
            errors.append("secret_retirement.status is not passed")
        if not str(secrets.get("database_backup_reference") or "").strip():
            errors.append("secret retirement database backup reference is missing")
        if secrets.get("rollback_verified") is not True:
            errors.append("secret retirement rollback is not verified")
        if not str(secrets.get("migration_reference") or "").strip():
            errors.append("secret retirement migration reference is missing")
        if secrets.get("database_verification") != "passed":
            errors.append("secret retirement database verification is not passed")
        if secrets.get("secret_scan") != "passed":
            errors.append("secret retirement scan is not passed")
        if secrets.get("legacy_environment_variables_removed") is not True:
            errors.append("legacy environment variables are not removed")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--require-canary", action="store_true")
    group.add_argument("--require-cohorts", action="store_true")
    group.add_argument("--require-retirement", action="store_true")
    group.add_argument("--require-secrets-removed", action="store_true")
    args = parser.parse_args()
    require_secrets = args.require_secrets_removed
    require_retirement = args.require_retirement or require_secrets
    require_cohorts = args.require_cohorts or require_retirement
    require_canary = args.require_canary or require_cohorts
    errors = validate(
        require_canary=require_canary,
        require_cohorts=require_cohorts,
        require_retirement=require_retirement,
        require_secrets_removed=require_secrets,
    )
    if errors:
        print("Meta rollout check: FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    mode = (
        "secrets-removed" if require_secrets else
        "retirement" if require_retirement else
        "cohorts" if require_cohorts else
        "canary" if require_canary else
        "structural"
    )
    print(f"Meta rollout check: PASS ({mode})")
    if mode == "structural":
        print("- External rollout is not asserted; use a strict gate for tasks 12.7-12.10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
