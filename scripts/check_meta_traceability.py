#!/usr/bin/env python3
"""Generate and verify Meta requirement-to-task traceability."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = REPO_ROOT / "docs/specs/meta-ecosystem"
REQUIREMENTS_PATH = SPEC_DIR / "requirements.md"
TASKS_PATH = SPEC_DIR / "tasks.md"
TRACEABILITY_PATH = SPEC_DIR / "traceability.md"
REQUIREMENT_HEADING = re.compile(r"^### ((?:REQ|NFR)-\d{3}) — (.+)$")
PHASE_HEADING = re.compile(r"^## Phase (\d+) — (.+)$")
TASK_ITEM = re.compile(r"^- \[([ x])\] \*\*(\d+\.\d+) ([^*]+)\*\*")
DECLARED_REQUIREMENT = re.compile(
    r"\b(REQ|NFR)-(\d{3})(?:\s*[–—]\s*(\d{3}))?"
)


@dataclass
class Phase:
    number: str
    name: str
    declared: set[str] = field(default_factory=set)
    tasks: list[str] = field(default_factory=list)
    is_cross_cutting_gate: bool = False


def requirement_catalog() -> dict[str, str]:
    catalog: dict[str, str] = {}
    for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        match = REQUIREMENT_HEADING.match(line)
        if match:
            catalog[match.group(1)] = match.group(2).strip()
    return catalog


def expand_declaration(text: str, catalog: dict[str, str]) -> set[str]:
    if "all requirements and NFRs" in text:
        return set(catalog)
    identifiers: set[str] = set()
    for match in DECLARED_REQUIREMENT.finditer(text):
        prefix, start_raw, end_raw = match.groups()
        start = int(start_raw)
        end = int(end_raw or start_raw)
        if end < start:
            start, end = end, start
        identifiers.update(f"{prefix}-{value:03d}" for value in range(start, end + 1))
    return identifiers


def task_phases(catalog: dict[str, str]) -> tuple[list[Phase], list[str]]:
    phases: list[Phase] = []
    errors: list[str] = []
    current: Phase | None = None
    seen_tasks: set[str] = set()

    for line in TASKS_PATH.read_text(encoding="utf-8").splitlines():
        phase_match = PHASE_HEADING.match(line)
        if phase_match:
            current = Phase(number=phase_match.group(1), name=phase_match.group(2))
            phases.append(current)
            continue
        if current is None:
            continue
        if line.startswith("**Requirements:**"):
            current.is_cross_cutting_gate = "all requirements and NFRs" in line
            current.declared = expand_declaration(line, catalog)
            unknown = current.declared - set(catalog)
            if unknown:
                errors.append(
                    f"phase {current.number} declares unknown requirements {sorted(unknown)}"
                )
            continue
        task_match = TASK_ITEM.match(line)
        if not task_match:
            continue
        task_id = task_match.group(2)
        if task_id in seen_tasks:
            errors.append(f"duplicate task identifier {task_id}")
        seen_tasks.add(task_id)
        current.tasks.append(task_id)

    for phase in phases:
        if not phase.declared:
            errors.append(f"phase {phase.number} has no machine-readable requirements")
        if not phase.tasks:
            errors.append(f"phase {phase.number} has no implementation tasks")
    return phases, errors


def render_traceability(
    catalog: dict[str, str],
    phases: list[Phase],
) -> tuple[str, list[str]]:
    errors: list[str] = []
    coverage: dict[str, list[Phase]] = {identifier: [] for identifier in catalog}
    for phase in phases:
        for identifier in phase.declared:
            if identifier in coverage:
                coverage[identifier].append(phase)

    lines = [
        "# Automated traceability: Meta requirements → tasks",
        "",
        "This file is generated from requirement headings and each phase's `Requirements` declaration in `tasks.md`.",
        "Do not edit it manually. Run `python3 scripts/check_meta_traceability.py --write` after changing either source.",
        "",
        "| Requirement | Title | Primary phases | Primary tasks | Cross-cutting gates |",
        "|---|---|---|---|---|",
    ]
    for identifier, title in catalog.items():
        mapped_phases = coverage[identifier]
        if not mapped_phases:
            errors.append(f"{identifier} is not mapped to any task phase")
        primary_phases = [
            phase for phase in mapped_phases if not phase.is_cross_cutting_gate
        ]
        gate_phases = [phase for phase in mapped_phases if phase.is_cross_cutting_gate]
        phase_labels = ", ".join(f"{phase.number}" for phase in primary_phases) or "—"
        task_ids = sorted(
            {task_id for phase in primary_phases for task_id in phase.tasks},
            key=lambda value: tuple(int(part) for part in value.split(".")),
        )
        task_labels = ", ".join(task_ids) or "—"
        gate_labels = ", ".join(
            f"{phase.tasks[0]}–{phase.tasks[-1]}" for phase in gate_phases
        ) or "—"
        safe_title = title.replace("|", "\\|")
        lines.append(
            f"| `{identifier}` | {safe_title} | {phase_labels} | {task_labels} | {gate_labels} |"
        )
    lines.extend(
        [
            "",
            f"**Coverage:** {len(catalog) - len(errors)}/{len(catalog)} requirements mapped.",
            "",
        ]
    )
    return "\n".join(lines), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="regenerate traceability.md")
    mode.add_argument("--print", action="store_true", dest="print_output")
    args = parser.parse_args()

    catalog = requirement_catalog()
    phases, errors = task_phases(catalog)
    rendered, coverage_errors = render_traceability(catalog, phases)
    errors.extend(coverage_errors)
    if not catalog:
        errors.append("no requirement headings were found")

    if args.print_output:
        print(rendered, end="")
    elif args.write:
        TRACEABILITY_PATH.write_text(rendered, encoding="utf-8")
        print(f"Wrote {TRACEABILITY_PATH.relative_to(REPO_ROOT)}")
    elif not TRACEABILITY_PATH.is_file():
        errors.append("traceability.md is missing; run with --write")
    elif TRACEABILITY_PATH.read_text(encoding="utf-8") != rendered:
        errors.append("traceability.md is stale; run with --write")

    if errors:
        print("Meta traceability check: FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if not args.print_output:
        task_count = sum(len(phase.tasks) for phase in phases)
        print(
            "Meta traceability check: PASS "
            f"({len(catalog)} requirements, {task_count} tasks, {len(phases)} phases)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
