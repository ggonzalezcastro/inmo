"""Backward-compatible re-export of dependency-neutral stage constants."""

from app.shared.pipeline_stages import (
    PIPELINE_STAGE_ENTRY,
    PIPELINE_STAGE_WON,
    PIPELINE_STAGES,
)

__all__ = ["PIPELINE_STAGE_ENTRY", "PIPELINE_STAGE_WON", "PIPELINE_STAGES"]
