"""Event-driven application shutdown orchestration tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from controller.orchestration.app_controller import (
    _ADB_BOOTSTRAP_JOB_NAMES,
    _SHUTDOWN_DRAIN_TIMEOUT_S,
    AppController,
    _ShutdownState,
)
from controller.runner import DrainHandle


class _RunnerStub:
    def __init__(self) -> None:
        self.cancel_exclusions: list[frozenset[str]] = []
        self.drain_requests: list[tuple[float | None, DrainHandle]] = []
        self.shutdown = MagicMock()

    def cancel_active(self, *, excluding_names: frozenset[str]) -> None:
        self.cancel_exclusions.append(excluding_names)

    def request_drain(self, timeout: float | None) -> DrainHandle:
        handle = DrainHandle()
        self.drain_requests.append((timeout, handle))
        return handle


class _AppControllerProbe:
    _on_application_shutdown_requested = (
        AppController._on_application_shutdown_requested
    )
    _await_runner_drain = AppController._await_runner_drain
    _abort_shutdown = AppController._abort_shutdown
    _begin_adb_shutdown = AppController._begin_adb_shutdown
    _continue_waiting_for_adb_close = AppController._continue_waiting_for_adb_close
    _finalize_shutdown = AppController._finalize_shutdown

    def __init__(self) -> None:
        self._shutdown_state = _ShutdownState.RUNNING
        self._shutdown_drain: DrainHandle | None = None
        self.runner = _RunnerStub()
        self.cron_manager = MagicMock()
        self._adb = MagicMock()
        self._simulation = MagicMock()
        self.view = MagicMock()


def test_shutdown_cancels_noncritical_jobs_and_ignores_duplicate_request() -> None:
    probe = _AppControllerProbe()

    probe._on_application_shutdown_requested()
    probe._on_application_shutdown_requested()

    probe.cron_manager.pause.assert_called_once_with()
    assert probe.runner.cancel_exclusions == [_ADB_BOOTSTRAP_JOB_NAMES]
    assert len(probe.runner.drain_requests) == 1
    assert probe.runner.drain_requests[0][0] == _SHUTDOWN_DRAIN_TIMEOUT_S
    assert probe._shutdown_state is _ShutdownState.QUIESCING


def test_shutdown_delegates_adb_close_then_finalizes_in_order() -> None:
    probe = _AppControllerProbe()
    events: list[str] = []
    probe._adb.run_shutdown.side_effect = lambda: events.append("adb-close")
    probe._simulation.persist_simulation_repository.side_effect = lambda: events.append(
        "persist"
    )
    probe.cron_manager.stop.side_effect = lambda: events.append("cron-stop")
    probe.runner.shutdown.side_effect = lambda: events.append("runner-stop")
    view = probe.view
    view.complete_managed_shutdown.side_effect = lambda: events.append("view-close")

    probe._on_application_shutdown_requested()
    first_drain = probe.runner.drain_requests[0][1]
    first_drain.Drained.emit()

    assert events == ["adb-close"]
    assert probe._shutdown_state is _ShutdownState.CLOSING_ADB
    assert len(probe.runner.drain_requests) == 2

    close_drain = probe.runner.drain_requests[1][1]
    close_drain.Drained.emit()

    assert events == ["adb-close", "persist", "cron-stop", "runner-stop", "view-close"]
    assert probe._shutdown_state is _ShutdownState.FINALIZED
    assert probe.view is None


def test_pre_close_drain_timeout_aborts_and_restores_application() -> None:
    probe = _AppControllerProbe()

    probe._on_application_shutdown_requested()
    probe.runner.drain_requests[0][1].TimedOut.emit()

    assert probe._shutdown_state is _ShutdownState.RUNNING
    probe.cron_manager.resume.assert_called_once_with()
    probe.view.abort_managed_shutdown.assert_called_once_with(
        "background work did not finish in time"
    )
    probe._adb.run_shutdown.assert_not_called()


def test_close_timeout_keeps_window_disabled_until_unbounded_drain() -> None:
    probe = _AppControllerProbe()

    probe._on_application_shutdown_requested()
    probe.runner.drain_requests[0][1].Drained.emit()
    probe.runner.drain_requests[1][1].TimedOut.emit()

    assert probe._shutdown_state is _ShutdownState.WAITING_FOR_CLOSE
    probe.view.report_managed_shutdown_delay.assert_called_once_with()
    assert probe.runner.drain_requests[2][0] is None
    probe.runner.shutdown.assert_not_called()

    probe.runner.drain_requests[2][1].Drained.emit()

    probe.runner.shutdown.assert_called_once_with()
    assert probe._shutdown_state is _ShutdownState.FINALIZED


def test_persistence_failure_does_not_prevent_final_teardown() -> None:
    probe = _AppControllerProbe()
    probe._simulation.persist_simulation_repository.side_effect = RuntimeError("disk")
    view = probe.view

    probe._on_application_shutdown_requested()
    probe.runner.drain_requests[0][1].Drained.emit()
    probe.runner.drain_requests[1][1].Drained.emit()

    probe.cron_manager.stop.assert_called_once_with()
    probe.runner.shutdown.assert_called_once_with()
    view.complete_managed_shutdown.assert_called_once_with()
    assert probe.view is None
