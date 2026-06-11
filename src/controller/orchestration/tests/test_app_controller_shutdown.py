from __future__ import annotations

import time
from typing import cast

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import controller.orchestration.app_controller as app_controller
from controller.orchestration.app_controller import AppController
from controller.runner import JobHandler, JobHandlerSignals


@pytest.fixture(scope="session", autouse=True)
def _qt_core_app() -> None:
    """Ensure QTimer and QEventLoop are available for shutdown waiter tests."""

    app = QApplication.instance()
    if app is None:
        QApplication([])


class _RunnerStub:
    def __init__(self) -> None:
        self.history: dict[str, tuple[JobHandler, JobHandlerSignals]] = {}

    def add_job(self, job_id: str, name: str) -> JobHandlerSignals:
        signals = JobHandlerSignals()
        self.history[job_id] = (JobHandler(job_id=job_id, name=name), signals)
        return signals


class _AppControllerProbe:
    def __init__(self, runner: _RunnerStub) -> None:
        self.runner = runner

    def _adb_bootstrap_jobs_pending(self) -> bool:
        return AppController._adb_bootstrap_jobs_pending(cast(AppController, self))


def _wait_for_bootstrap_jobs(runner: _RunnerStub) -> float:
    probe = _AppControllerProbe(runner)
    started = time.monotonic()
    AppController._wait_for_adb_bootstrap_jobs(cast(AppController, probe))
    return time.monotonic() - started


def test_wait_for_adb_bootstrap_jobs_returns_immediately_when_none_pending() -> None:
    runner = _RunnerStub()

    elapsed_s = _wait_for_bootstrap_jobs(runner)

    assert elapsed_s < 0.05


def test_wait_for_adb_bootstrap_jobs_rechecks_after_history_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app_controller, "_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS", 150)
    runner = _RunnerStub()
    startup_signals = runner.add_job("startup", "startup_core_runtime")

    def finish_startup() -> None:
        startup_signals.Completed.emit(object())
        runner.history.pop("startup")

    QTimer.singleShot(0, finish_startup)

    elapsed_s = _wait_for_bootstrap_jobs(runner)

    assert elapsed_s < 0.1
    assert runner.history == {}


def test_wait_for_adb_bootstrap_jobs_waits_for_chained_host_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app_controller, "_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS", 150)
    runner = _RunnerStub()
    startup_signals = runner.add_job("startup", "startup_core_runtime")
    events: list[str] = []

    def finish_startup_and_add_host_identity() -> None:
        startup_signals.Completed.emit(object())
        runner.history.pop("startup")
        host_signals = runner.add_job("host", "host_install_identity")
        events.append("host-added")
        QTimer.singleShot(0, lambda: finish_host_identity(host_signals))

    def finish_host_identity(host_signals: JobHandlerSignals) -> None:
        events.append("host-finished")
        host_signals.Completed.emit(object())
        runner.history.pop("host")

    QTimer.singleShot(0, finish_startup_and_add_host_identity)

    elapsed_s = _wait_for_bootstrap_jobs(runner)

    assert elapsed_s < 0.1
    assert events == ["host-added", "host-finished"]
    assert runner.history == {}
