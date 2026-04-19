"""
Custom Celery Task base class with Dead Letter Queue support (TASK-029).

Usage
-----
    @shared_task(base=DLQTask, bind=True, max_retries=3)
    def my_task(self, ...):
        ...

When a task exhausts its ``max_retries``, ``on_failure`` is called and the
task metadata is pushed to the DLQ automatically.
"""
from __future__ import annotations

import asyncio
import logging
import traceback as tb_module
from typing import Any

from celery import Task

from app.tasks.dlq import DLQManager

logger = logging.getLogger(__name__)


class DLQTask(Task):
    """Task base class that routes final failures to the DLQ."""

    abstract = True

    def on_failure(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        """Called by Celery when a task fails after all retries are exhausted."""
        retries: int = self.request.retries if self.request else 0
        exc_str = repr(exc)
        trace_str = tb_module.format_exc()

        logger.error(
            "[DLQ] Task %s (id=%s) failed after %d retries: %s",
            self.name, task_id, retries, exc_str,
        )

        # Push to DLQ in a fire-and-forget fashion
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    DLQManager.push(
                        task_name=self.name,
                        args=list(args) if args else [],
                        kwargs=dict(kwargs) if kwargs else {},
                        exception=exc_str,
                        traceback=trace_str,
                        retries=retries,
                    )
                )
            else:
                loop.run_until_complete(
                    DLQManager.push(
                        task_name=self.name,
                        args=list(args) if args else [],
                        kwargs=dict(kwargs) if kwargs else {},
                        exception=exc_str,
                        traceback=trace_str,
                        retries=retries,
                    )
                )
        except Exception as push_exc:
            logger.warning("[DLQ] Could not push to DLQ: %s", push_exc)

        super().on_failure(exc, task_id, args, kwargs, einfo)
