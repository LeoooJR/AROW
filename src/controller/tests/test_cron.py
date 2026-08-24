"""Tests for recurring async job declaration and scheduling."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from unittest.mock import MagicMock, call

import pytest

import controller.cron as cron_module
from controller.controller import Controller
from controller.cron import CronJob, CronManager
from controller.runner import (
    AsyncRunner,
    JobError,
    JobHandler,
    JobHandlerSignals,
    JobSpecification,
    ProgressEvent,
)
from core.entrypoint import ModelEntrypoint
from gui.windows import MainWindow


class _TimerStub:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


@pytest.fixture
def repeat_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[tuple[int, Callable[[], None]]], list[_TimerStub]]:
    callbacks: list[tuple[int, Callable[[], None]]] = []
    timers: list[_TimerStub] = []

    def fake_repeat(interval_ms: int) -> Callable[[Callable[[], None]], _TimerStub]:
        def start(callback: Callable[[], None]) -> _TimerStub:
            timer = _TimerStub()
            callbacks.append((interval_ms, callback))
            timers.append(timer)
            return timer

        return start

    monkeypatch.setattr(cron_module, "repeat", fake_repeat)
    return callbacks, timers


def _cron_job(name: str = "refresh", interval_ms: int = 30_000) -> CronJob:
    return CronJob(
        interval_ms=interval_ms,
        specification=JobSpecification(name=name, fn=lambda: None, type="thread"),
    )


@pytest.mark.parametrize(
    ("job", "message"),
    [
        (_cron_job(interval_ms=0), "interval_ms must be positive"),
        (_cron_job(name=""), "job name must not be empty"),
        (_cron_job(name="   "), "job name must not be empty"),
    ],
)
def test_declare_rejects_invalid_jobs(job: CronJob, message: str) -> None:
    manager = CronManager(MagicMock())

    with pytest.raises(ValueError, match=message):
        manager.declare(job)


def test_declare_rejects_duplicate_names() -> None:
    manager = CronManager(MagicMock())
    manager.declare(_cron_job())

    with pytest.raises(ValueError, match="already declared"):
        manager.declare(_cron_job())


def test_commit_starts_declared_jobs_without_running_them_immediately(
    repeat_probe: tuple[list[tuple[int, Callable[[], None]]], list[_TimerStub]],
) -> None:
    callbacks, _timers = repeat_probe
    submit = MagicMock()
    manager = CronManager(submit)
    job = _cron_job()
    manager.declare(job)

    manager.commit()

    assert callbacks == [(30_000, callbacks[0][1])]
    submit.assert_not_called()

    callbacks[0][1]()
    callbacks[0][1]()

    assert submit.call_args_list == [call(job), call(job)]


def test_commit_and_post_commit_declaration_are_rejected(
    repeat_probe: tuple[list[tuple[int, Callable[[], None]]], list[_TimerStub]],
) -> None:
    manager = CronManager(MagicMock())
    manager.commit()

    with pytest.raises(RuntimeError, match="already committed"):
        manager.commit()
    with pytest.raises(RuntimeError, match="after commit"):
        manager.declare(_cron_job())


def test_submission_exception_does_not_disable_recurring_job(
    repeat_probe: tuple[list[tuple[int, Callable[[], None]]], list[_TimerStub]],
) -> None:
    callbacks, _timers = repeat_probe
    submit = MagicMock(side_effect=[RuntimeError("boom"), None])
    manager = CronManager(submit)
    manager.declare(_cron_job())
    manager.commit()

    callbacks[0][1]()
    callbacks[0][1]()

    assert submit.call_count == 2


def test_stop_stops_all_timers_and_is_idempotent(
    repeat_probe: tuple[list[tuple[int, Callable[[], None]]], list[_TimerStub]],
) -> None:
    callbacks, timers = repeat_probe
    submit = MagicMock()
    manager = CronManager(submit)
    manager.declare(_cron_job("first"))
    manager.declare(_cron_job("second"))
    manager.commit()

    manager.stop()
    manager.stop()
    callbacks[0][1]()

    assert [timer.stop_calls for timer in timers] == [1, 1]
    submit.assert_not_called()


class _RunnerStub:
    def __init__(self) -> None:
        self.submitted: list[JobSpecification] = []
        self.signals: dict[str, JobHandlerSignals] = {}

    def submit(self, specification: JobSpecification) -> JobHandler:
        self.submitted.append(specification)
        handle = JobHandler(
            job_id=f"job-{len(self.submitted)}", name=specification.name
        )
        self.signals[handle.job_id] = JobHandlerSignals()
        return handle

    def bind_handle_signals(self, handle: JobHandler) -> JobHandlerSignals:
        return self.signals[handle.job_id]


class _ControllerProbe(Controller):
    def _connect_view_signals(self) -> None:
        pass

    def _connect_model_signals(self) -> None:
        pass


def test_controller_cron_submission_uses_shared_runner_and_callbacks() -> None:
    runner = _RunnerStub()
    controller = _ControllerProbe(
        ModelEntrypoint(),
        cast(MainWindow, MagicMock()),
        runner=cast(AsyncRunner, runner),
    )
    completed: list[object] = []
    failed: list[JobError] = []
    cancelled: list[str] = []
    progressed: list[ProgressEvent] = []
    specification = JobSpecification(name="scheduled", fn=lambda: "done")
    job = CronJob(
        interval_ms=100,
        specification=specification,
        on_completed=completed.append,
        on_failed=failed.append,
        on_cancelled=lambda: cancelled.append("cancelled"),
        on_progress=progressed.append,
    )

    handle = controller._submit_cron_job(job)

    assert handle is not None
    assert runner.submitted == [specification]
    signals = runner.signals[handle.job_id]
    outcome = object()
    error = JobError(message="failed", traceback="", origin="scheduled")
    progress = ProgressEvent(value=1, message="working")
    signals.Completed.emit(outcome)
    signals.Failed.emit(error)
    signals.Cancelled.emit()
    signals.Progress.emit(progress)
    assert completed == [outcome]
    assert failed == [error]
    assert cancelled == ["cancelled"]
    assert progressed == [progress]
