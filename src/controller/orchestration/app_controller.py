"""
Application-level controller: one :class:`Controller` owning a single :class:`AsyncRunner`,
composed of *SubController domain objects.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import NoReturn

from PySide6.QtCore import Slot

from controller.controller import Controller
from controller.domains.adb_sub_controller import AdbSubController
from controller.domains.map_sub_controller import MapSubController
from controller.domains.simulation_sub_controller import SimulationSubController
from controller.runner import DrainHandle
from core.entrypoint import ModelEntrypoint
from core.signals import ActivityLogFileUpdatedPayload, CoreSignals
from gui.signals import signals
from gui.windows import MainWindow
from logger import logger

# Offer wait/force-close choices when one shutdown drain exceeds this duration.
_SHUTDOWN_DRAIN_TIMEOUT_S = 60.0

# Async jobs that must finish (or fail/cancel) before quit runs close/shutdown.
_ADB_BOOTSTRAP_JOB_NAMES = frozenset({"startup_core_runtime", "host_install_identity"})


class _ShutdownState(Enum):
    RUNNING = "running"
    QUIESCING = "quiescing"
    WAITING_FOR_QUIESCENCE = "waiting-for-quiescence"
    CLOSING_ADB = "closing-adb"
    WAITING_FOR_CLOSE = "waiting-for-close"
    FORCING = "forcing"
    FINALIZED = "finalized"


class AppController(Controller):
    """
    Main coordinator. Subclass of :class:`Controller` with a single async runner;
    delegates ADB, simulation, and map concerns to *SubController instances.
    """

    def __init__(
        self,
        model_entrypoint: ModelEntrypoint,
        view: MainWindow,
        *,
        force_exit: Callable[[int], NoReturn] = os._exit,
    ) -> None:
        # Subcontrollers need a fully constructed app reference; defer signal
        # wiring in Controller until children exist.
        super().__init__(model_entrypoint, view, defer_signal_connect=True)
        self._shutdown_state = _ShutdownState.RUNNING
        self._shutdown_drain: DrainHandle | None = None
        self._force_exit = force_exit
        self._simulation: SimulationSubController = SimulationSubController(
            self
        )  # Create simulation subcontroller before adb subcontroller to avoid race condition, signals are connected in the order of creation
        self._adb: AdbSubController = AdbSubController(self)
        self._map: MapSubController = MapSubController(self)
        self._connect_view_signals()
        self.view.enable_managed_shutdown()
        self._connect_model_signals()
        self._commit_cron_jobs()
        self._sync_activity_log_file_to_view()
        self._send_host_device_information()
        self._adb.run_startup()

    @property
    def simulation(self) -> SimulationSubController:
        return self._simulation

    @property
    def adb(self) -> AdbSubController:
        return self._adb

    @property
    def map(self) -> MapSubController:
        return self._map

    def _connect_view_signals(self) -> None:
        self._simulation.connect_view_signals()
        self._adb.connect_view_signals()
        self._map.connect_view_signals()
        signals.ACTIVITY_LOG.ActivityLogFileUpdateRequested.connect(
            self._on_activity_log_file_update_requested
        )
        signals.UI.ApplicationShutdownRequested.connect(
            self._on_application_shutdown_requested
        )
        signals.UI.ApplicationShutdownWaitRequested.connect(
            self._on_application_shutdown_wait_requested
        )
        signals.UI.ApplicationForceCloseRequested.connect(
            self._on_application_force_close_requested
        )

    def _connect_model_signals(self) -> None:
        self._simulation.connect_model_signals()
        self._adb.connect_model_signals()
        self._map.connect_model_signals()
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.ACTIVITY_LOG_FILE_UPDATED, self._on_activity_log_file_updated
        )

    def _commit_cron_jobs(self) -> None:
        """Collect every domain declaration, then activate the schedule once."""
        for subcontroller in (self._simulation, self._adb, self._map):
            for job in subcontroller.declare_cron_jobs():
                self.cron_manager.declare(job)
        self.cron_manager.commit()

    def _send_host_device_information(self) -> None:
        """Send the host device information to the view. Run once after the main window is wired."""
        self.view.forward_host_device_information_updated(
            self.model_entrypoint.host.name,
            self.model_entrypoint.host.os,
            self.model_entrypoint.host.ip,
        )

    @Slot(str)
    def _on_activity_log_file_update_requested(self, path: str) -> None:
        """Update the app-wide activity log file path."""
        logger.debug(
            "Activity log file update requested",
            path=path,
        )
        self.model_entrypoint.activity_log_file = Path(path)

    def _on_activity_log_file_updated(
        self, payload: ActivityLogFileUpdatedPayload
    ) -> None:
        """Forward the activity log file updated signal to the view."""
        logger.debug(
            "Activity log file update forwarded",
            path=payload.path,
        )
        self.view.forward_activity_log_file_updated(str(payload.path))

    def _sync_activity_log_file_to_view(self) -> None:
        """Push the current activity log file to the view after controller wiring."""
        log_file = self.model_entrypoint.activity_log_file
        if log_file is None:
            return
        AppController._on_activity_log_file_updated(
            self,
            ActivityLogFileUpdatedPayload(path=log_file),
        )

    @Slot()
    def _on_application_shutdown_requested(self) -> None:
        """Begin non-blocking application quiescence before Qt accepts close."""
        if self._shutdown_state is not _ShutdownState.RUNNING:
            return
        self._shutdown_state = _ShutdownState.QUIESCING
        self.cron_manager.pause()
        self.runner.cancel_active(excluding_names=_ADB_BOOTSTRAP_JOB_NAMES)
        self._await_runner_drain(
            timeout=_SHUTDOWN_DRAIN_TIMEOUT_S,
            on_drained=self._begin_adb_shutdown,
            on_timed_out=self._continue_waiting_for_background_work,
        )

    def _await_runner_drain(
        self,
        *,
        timeout: float | None,
        on_drained: Callable[[], None],
        on_timed_out: Callable[[], None] | None = None,
    ) -> None:
        """Bind one runner drain to the next shutdown-state transition."""
        drain = self.runner.request_drain(timeout)
        self._shutdown_drain = drain
        drain.Drained.connect(on_drained)
        if on_timed_out is not None:
            drain.TimedOut.connect(on_timed_out)

    @Slot()
    def _continue_waiting_for_background_work(self) -> None:
        """Offer an escape while continuing to observe pre-close work."""
        if self._shutdown_state is not _ShutdownState.QUIESCING:
            return
        logger.warning(
            "Application shutdown is waiting for active background work",
            timeout_s=_SHUTDOWN_DRAIN_TIMEOUT_S,
        )
        self._shutdown_state = _ShutdownState.WAITING_FOR_QUIESCENCE
        self.view.show_background_shutdown_decision()
        self._await_runner_drain(timeout=None, on_drained=self._begin_adb_shutdown)

    @Slot()
    def _on_application_shutdown_wait_requested(self) -> None:
        """Acknowledge continued waiting without changing the active drain."""
        if self._shutdown_state not in {
            _ShutdownState.WAITING_FOR_QUIESCENCE,
            _ShutdownState.WAITING_FOR_CLOSE,
        }:
            return
        self.view.show_managed_shutdown_waiting()

    @Slot()
    def _on_application_force_close_requested(self) -> None:
        """Perform best-effort teardown, then terminate despite hung workers."""
        if self._shutdown_state not in {
            _ShutdownState.WAITING_FOR_QUIESCENCE,
            _ShutdownState.WAITING_FOR_CLOSE,
        }:
            return
        self._shutdown_state = _ShutdownState.FORCING
        logger.warning("Forced application shutdown requested")
        self._persist_simulations_best_effort()
        self.cron_manager.stop()
        self.runner.shutdown()
        self._force_exit(1)

    @Slot()
    def _begin_adb_shutdown(self) -> None:
        """Submit domain-owned ADB close after every earlier job is terminal."""
        if self._shutdown_state not in {
            _ShutdownState.QUIESCING,
            _ShutdownState.WAITING_FOR_QUIESCENCE,
        }:
            return
        self._shutdown_drain = None
        self._shutdown_state = _ShutdownState.CLOSING_ADB
        try:
            self._adb.run_shutdown()
        except Exception:
            logger.exception("Core runtime shutdown submission failed")
            self._shutdown_state = _ShutdownState.CLOSING_ADB
            self._finalize_shutdown()
            return
        self._await_runner_drain(
            timeout=_SHUTDOWN_DRAIN_TIMEOUT_S,
            on_drained=self._finalize_shutdown,
            on_timed_out=self._continue_waiting_for_adb_close,
        )

    @Slot()
    def _continue_waiting_for_adb_close(self) -> None:
        """Keep Qt alive until an already-started ADB close actually commits."""
        if self._shutdown_state is not _ShutdownState.CLOSING_ADB:
            return
        logger.warning(
            "Core runtime close exceeded the shutdown deadline; continuing to wait",
            timeout_s=_SHUTDOWN_DRAIN_TIMEOUT_S,
        )
        self._shutdown_state = _ShutdownState.WAITING_FOR_CLOSE
        self.view.show_adb_shutdown_decision()
        self._await_runner_drain(
            timeout=None,
            on_drained=self._finalize_shutdown,
        )

    @Slot()
    def _finalize_shutdown(self) -> None:
        """Persist domain state and release resources before accepting close."""
        if self._shutdown_state not in {
            _ShutdownState.CLOSING_ADB,
            _ShutdownState.WAITING_FOR_CLOSE,
        }:
            return
        self._shutdown_drain = None
        self._shutdown_state = _ShutdownState.FINALIZED
        self._persist_simulations_best_effort()
        self.cron_manager.stop()
        self.runner.shutdown()
        view = self.view
        view.complete_managed_shutdown()
        self.view = None

    def _persist_simulations_best_effort(self) -> None:
        """Persist simulation state without preventing final or forced teardown."""
        try:
            self._simulation.persist_simulation_repository()
        except Exception:
            logger.exception("Simulation repository persistence failed during shutdown")
