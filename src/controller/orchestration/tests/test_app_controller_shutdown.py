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
    _continue_waiting_for_background_work = (
        AppController._continue_waiting_for_background_work
    )
    _on_application_shutdown_wait_requested = (
        AppController._on_application_shutdown_wait_requested
    )
    _on_application_force_close_requested = (
        AppController._on_application_force_close_requested
    )
    _begin_adb_shutdown = AppController._begin_adb_shutdown
    _continue_waiting_for_adb_close = AppController._continue_waiting_for_adb_close
    _finalize_shutdown = AppController._finalize_shutdown
    _persist_simulations_best_effort = AppController._persist_simulations_best_effort

    def __init__(self) -> None:
        self._shutdown_state = _ShutdownState.RUNNING
        self._shutdown_drain: DrainHandle | None = None
        self.runner = _RunnerStub()
        self.cron_manager = MagicMock()
        self._adb = MagicMock()
        self._simulation = MagicMock()
        self.view = MagicMock()
        self.force_exit = MagicMock()
        self._force_exit = self.force_exit


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


def test_pre_close_drain_timeout_offers_choice_and_keeps_draining() -> None:
    probe = _AppControllerProbe()

    probe._on_application_shutdown_requested()
    probe.runner.drain_requests[0][1].TimedOut.emit()

    assert probe._shutdown_state is _ShutdownState.WAITING_FOR_QUIESCENCE
    probe.view.show_background_shutdown_decision.assert_called_once_with()
    assert probe.runner.drain_requests[1][0] is None
    probe._adb.run_shutdown.assert_not_called()

    probe._on_application_shutdown_wait_requested()
    probe.view.show_managed_shutdown_waiting.assert_called_once_with()

    probe.runner.drain_requests[1][1].Drained.emit()
    probe._adb.run_shutdown.assert_called_once_with()


def test_close_timeout_keeps_window_disabled_until_unbounded_drain() -> None:
    probe = _AppControllerProbe()

    probe._on_application_shutdown_requested()
    probe.runner.drain_requests[0][1].Drained.emit()
    probe.runner.drain_requests[1][1].TimedOut.emit()

    assert probe._shutdown_state is _ShutdownState.WAITING_FOR_CLOSE
    probe.view.show_adb_shutdown_decision.assert_called_once_with()
    assert probe.runner.drain_requests[2][0] is None
    probe.runner.shutdown.assert_not_called()

    probe.runner.drain_requests[2][1].Drained.emit()

    probe.runner.shutdown.assert_called_once_with()
    assert probe._shutdown_state is _ShutdownState.FINALIZED


def test_force_close_performs_best_effort_teardown_then_hard_exit() -> None:
    probe = _AppControllerProbe()
    events: list[str] = []
    probe._simulation.persist_simulation_repository.side_effect = lambda: events.append(
        "persist"
    )
    probe.cron_manager.stop.side_effect = lambda: events.append("cron-stop")
    probe.runner.shutdown.side_effect = lambda: events.append("runner-stop")
    probe.force_exit.side_effect = lambda code: events.append(f"exit:{code}")

    probe._on_application_shutdown_requested()
    probe.runner.drain_requests[0][1].TimedOut.emit()
    probe._on_application_force_close_requested()
    probe._on_application_force_close_requested()

    assert events == ["persist", "cron-stop", "runner-stop", "exit:1"]
    assert probe._shutdown_state is _ShutdownState.FORCING
    probe._adb.run_shutdown.assert_not_called()


def test_force_close_exits_when_persistence_fails() -> None:
    probe = _AppControllerProbe()
    probe._simulation.persist_simulation_repository.side_effect = RuntimeError("disk")

    probe._on_application_shutdown_requested()
    probe.runner.drain_requests[0][1].TimedOut.emit()
    probe._on_application_force_close_requested()

    probe.cron_manager.stop.assert_called_once_with()
    probe.runner.shutdown.assert_called_once_with()
    probe.force_exit.assert_called_once_with(1)


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
