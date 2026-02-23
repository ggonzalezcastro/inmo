"""Load the labeled conversation dataset for eval tests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATASET_PATH = Path(__file__).parent / "conversations.json"


def load_dataset() -> list[dict[str, Any]]:
    """Return all 50+ labeled conversation test cases."""
    with open(_DATASET_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_by_category(category: str) -> list[dict[str, Any]]:
    return [c for c in load_dataset() if c.get("category") == category]


def load_violation_cases() -> list[dict[str, Any]]:
    """Return cases where dicom_violation == True (should score 0)."""
    return [c for c in load_dataset() if c["labels"]["dicom_violation"]]


def load_compliant_cases() -> list[dict[str, Any]]:
    """Return cases where dicom_violation == False (should score 1)."""
    return [c for c in load_dataset() if not c["labels"]["dicom_violation"]]
