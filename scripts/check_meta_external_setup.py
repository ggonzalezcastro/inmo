#!/usr/bin/env python3
"""Validate Meta external-task records and secret-safe environment contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = REPO_ROOT / ".env.example"
MANIFEST_PATH = REPO_ROOT / "docs/specs/meta-ecosystem/external-setup/manifest.json"
EXPECTED_TASKS = {"0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "5.6", "6.6", "12.2", "12.4"}
PHASE0_TASKS = {"0.1", "0.2", "0.3", "0.4", "0.5", "0.6"}
SANDBOX_TASKS = PHASE0_TASKS | {"5.6", "6.6"}
INFRASTRUCTURE_TASKS = SANDBOX_TASKS | {"12.2", "12.4"}
TASK_STATES = {"pending_external", "deferred", "running", "passed", "failed"}
REQUIRED_META_KEYS = {
    "META_APP_ID",
    "META_APP_SECRET",
    "META_GRAPH_API_VERSION",
    "META_WEBHOOK_VERIFY_TOKEN",
    "META_OAUTH_REDIRECT_BASE_URL",
    "META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID",
    "META_CREDENTIAL_ENCRYPTION_KEY",
    "META_FEATURE_ENABLED",
    "META_BROKER_DEFAULT_ENABLED",
    "META_WHATSAPP_ASSET_ROUTING_ENABLED",
    "META_WHATSAPP_LEGACY_FALLBACK_ENABLED",
    "META_INSTAGRAM_ENABLED",
    "META_MESSENGER_ENABLED",
    "META_ADS_ENABLED",
    "META_LEAD_ADS_ENABLED",
    "META_CONVERSIONS_API_ENABLED",
}
SHARED_SECRET_KEYS = {
    "META_APP_ID",
    "META_APP_SECRET",
    "META_GRAPH_API_VERSION",
    "META_WEBHOOK_VERIFY_TOKEN",
    "META_OAUTH_REDIRECT_BASE_URL",
    "META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID",
    "META_CREDENTIAL_ENCRYPTION_KEY",
}


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def validate_env(values: dict[str, str], *, target: str, label: str) -> list[str]:
    errors: list[str] = []
    missing = sorted(key for key in REQUIRED_META_KEYS if not values.get(key))
    if missing:
        errors.append(f"{label}: missing non-empty variables {missing}")
    if values.get("META_GRAPH_API_VERSION") != "v26.0":
        errors.append(f"{label}: META_GRAPH_API_VERSION must be v26.0")
    redirect = urlparse(values.get("META_OAUTH_REDIRECT_BASE_URL", ""))
    if not redirect.scheme or not redirect.netloc or not redirect.path.rstrip("/").endswith("/api/v1/meta"):
        errors.append(f"{label}: META_OAUTH_REDIRECT_BASE_URL must be an absolute /api/v1/meta URL")
    if target in {"staging", "production"} and redirect.scheme != "https":
        errors.append(f"{label}: Meta OAuth redirect must use HTTPS for {target}")
    encryption_key = values.get("META_CREDENTIAL_ENCRYPTION_KEY", "")
    if encryption_key and len(encryption_key) < 32:
        errors.append(f"{label}: META_CREDENTIAL_ENCRYPTION_KEY must have at least 32 characters")
    if encryption_key and encryption_key == values.get("SECRET_KEY"):
        errors.append(f"{label}: Meta encryption key must be distinct from SECRET_KEY")
    if target == "production" and values.get("META_BROKER_DEFAULT_ENABLED", "").lower() != "false":
        errors.append(f"{label}: production broker default must remain false")
    if target == "production" and values.get("META_CONVERSIONS_API_ENABLED", "").lower() != "false":
        errors.append(f"{label}: production Conversions API must remain off before its separate gate")
    return errors


def validate_tasks(required: set[str]) -> list[str]:
    errors: list[str] = []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    tasks = manifest.get("tasks")
    if not isinstance(tasks, dict):
        return ["external setup manifest tasks must be an object"]
    if set(tasks) != EXPECTED_TASKS:
        errors.append(
            f"external task set mismatch: missing={sorted(EXPECTED_TASKS - set(tasks))}, "
            f"extra={sorted(set(tasks) - EXPECTED_TASKS)}"
        )
    for task_id, entry in tasks.items():
        if not isinstance(entry, dict) or entry.get("status") not in TASK_STATES:
            errors.append(f"task {task_id}: invalid record/status")
            continue
        status = entry["status"]
        evidence_reference = str(entry.get("evidence_reference") or "").strip()
        if status == "passed" and not evidence_reference:
            errors.append(f"task {task_id}: passed status requires an evidence reference")
        if status in {"pending_external", "deferred", "failed"} and not str(
            entry.get("blocking_condition") or ""
        ).strip():
            errors.append(f"task {task_id}: open status requires a blocking condition")
        if task_id in required:
            if status != "passed":
                errors.append(f"task {task_id} is not passed")
            if not evidence_reference:
                errors.append(f"task {task_id} lacks a non-secret evidence reference")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--require-phase0", action="store_true")
    group.add_argument("--require-sandbox", action="store_true")
    group.add_argument("--require-infrastructure", action="store_true")
    parser.add_argument("--env-file", action="append", default=[])
    parser.add_argument("--target", choices=("development", "staging", "production"), default="development")
    args = parser.parse_args()

    required = (
        INFRASTRUCTURE_TASKS if args.require_infrastructure else
        SANDBOX_TASKS if args.require_sandbox else
        PHASE0_TASKS if args.require_phase0 else
        set()
    )
    errors = validate_tasks(required)
    example = parse_env(EXAMPLE_PATH)
    missing_contract = sorted(REQUIRED_META_KEYS - set(example))
    if missing_contract:
        errors.append(f".env.example lacks variables {missing_contract}")

    envs: list[tuple[str, dict[str, str]]] = []
    for raw_path in args.env_file:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            errors.append(f"environment file not found: {path}")
            continue
        values = parse_env(path)
        envs.append((path.name, values))
        errors.extend(validate_env(values, target=args.target, label=path.name))
    if required and not envs:
        errors.append("a strict external gate requires at least one --env-file")
    if len(envs) > 1:
        baseline_name, baseline = envs[0]
        for name, values in envs[1:]:
            for key in SHARED_SECRET_KEYS:
                if fingerprint(values.get(key, "")) != fingerprint(baseline.get(key, "")):
                    errors.append(f"{name}: {key} differs from {baseline_name}")

    if errors:
        print("Meta external setup check: FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    mode = "infrastructure" if args.require_infrastructure else "sandbox" if args.require_sandbox else "phase0" if args.require_phase0 else "structural"
    print(f"Meta external setup check: PASS ({mode})")
    if mode == "structural":
        print("- External ownership, assets, environments and evidence are not asserted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
