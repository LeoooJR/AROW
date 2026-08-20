"""Recurring Qt-timer scheduling for async controller jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QTimer

from controller.helper import repeat
from controller.runner import (
    JobHandler,
    JobSpecification,
    ProgressEvent,
)
from logger import logger


@dataclass(frozen=True, slots=True)
class CronJob:
    """Immutable declaration for a recurring async job."""

    interval_ms: int
    specification: JobSpecification
    on_completed: Callable[[Any], None] | None = None
    on_failed: Callable[[Any], None] | None = None
    on_cancelled: Callable[[], None] | None = None
    on_progress: Callable[[ProgressEvent], None] | None = None


CronSubmitter = Callable[[CronJob], JobHandler | None]


class CronManager:
    """Declare recurring jobs and activate their Qt timers in one commit."""

    def __init__(self, submit: CronSubmitter) -> None:
        self._submit = submit
        self._declarations: dict[str, CronJob] = {}
        self._timers: dict[str, QTimer] = {}
        self._committed = False
        self._stopped = False

    def declare(self, job: CronJob) -> None:
        """Register *job* without starting its timer."""
        if self._committed:
            raise RuntimeError("cron jobs cannot be declared after commit")
        if job.interval_ms <= 0:
            raise ValueError("cron job interval_ms must be positive")
        name = job.specification.name
        if not name.strip():
            raise ValueError("cron job name must not be empty")
        if name in self._declarations:
            raise ValueError(f"cron job {name!r} is already declared")
        self._declarations[name] = job

    def commit(self) -> None:
        """Start every declared job; the first run follows one full interval."""
        if self._committed:
            raise RuntimeError("cron jobs are already committed")
        self._committed = True
        for name, job in self._declarations.items():
            self._timers[name] = repeat(job.interval_ms)(lambda job=job: self._run(job))

    def stop(self) -> None:
        """Stop and release all active timers. Safe to call repeatedly."""
        self._stopped = True
        for timer in self._timers.values():
            timer.stop()
        self._timers.clear()

    def _run(self, job: CronJob) -> None:
        if self._stopped:
            return
        try:
            self._submit(job)
        except Exception:
            logger.exception(
                "Recurring async job submission failed",
                job_name=job.specification.name,
                interval_ms=job.interval_ms,
            )
