"""
Application-level controller: one :class:`Controller` owning a single :class:`AsyncRunner`,
composed of *SubController domain objects.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEventLoop, QTimer, Slot
from PySide6.QtWidgets import QApplication

from controller.controller import Controller
from controller.domains.adb_sub_controller import AdbSubController
from controller.domains.map_sub_controller import MapSubController
from controller.domains.simulation_sub_controller import SimulationSubController
from controller.helper import watchdog
from core.entrypoint import ModelEntrypoint
from core.signals import ActivityLogFileUpdatedPayload, CoreSignals
from gui.signals import signals
from gui.windows import MainWindow
from logger import logger

# Hard cap blocking quit until close job applies; avoids orphaned ADB during exit.
_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS = 60_000

# Async jobs that must finish (or fail/cancel) before quit runs close/shutdown.
_ADB_BOOTSTRAP_JOB_NAMES = frozenset({"startup_core_runtime", "host_install_identity"})


class AppController(Controller):
    """
    Main coordinator. Subclass of :class:`Controller` with a single async runner;
    delegates ADB, simulation, and map concerns to *SubController instances.
    """

    def __init__(self, model_entrypoint: ModelEntrypoint, view: MainWindow) -> None:
        # Subcontrollers need a fully constructed app reference; defer signal
        # wiring in Controller until children exist.
        super().__init__(model_entrypoint, view, defer_signal_connect=True)
        self._simulation: SimulationSubController = SimulationSubController(
            self
        )  # Create simulation subcontroller before adb subcontroller to avoid race condition, signals are connected in the order of creation
        self._adb: AdbSubController = AdbSubController(self)
        self._map: MapSubController = MapSubController(self)
        self._connect_view_signals()
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

        qt_app = QApplication.instance()
        if qt_app is not None:
            qt_app.aboutToQuit.connect(self._on_application_about_to_quit)

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

    def _adb_bootstrap_jobs_pending(self) -> bool:
        """True while startup or chained host-install jobs are still in the runner queue."""
        return any(
            handler.name in _ADB_BOOTSTRAP_JOB_NAMES
            for handler, _ in self.runner.history.values()
        )

    def _wait_for_adb_bootstrap_jobs(self) -> None:
        """
        Block quit until in-flight startup / host_install_identity jobs leave ``history``,
        so ``runner.shutdown()`` cannot strand worker completions that re-apply model state.

        Uses each job's :class:`~controller.runner.JobHandlerSignals` (not runner-level
        signals) so lifecycle ordering matches the intended job graph; ``host_install_identity``
        may appear while draining startup, so connections are attached incrementally.
        """
        if not self._adb_bootstrap_jobs_pending():
            return

        bootstrap_loop = QEventLoop()

        # Pairs of (per-job signals object, slot) for teardown.
        handle_bindings: list[tuple[Any, Callable[..., None]]] = []
        connected_job_ids: set[str] = set()

        def _on_bootstrap_job_finished(*_args: object) -> None:
            # AsyncRunner cleans history after emitting per-job signals, so recheck on
            # the next Qt turn to avoid waiting for the watchdog on an already-done job.
            QTimer.singleShot(0, _recheck_bootstrap_jobs)

        def _recheck_bootstrap_jobs() -> None:
            # Startup completion may enqueue host_install_identity before history is cleaned up.
            _ensure_per_job_bootstrap_connections()
            if not self._adb_bootstrap_jobs_pending():
                if bootstrap_watchdog.isActive():
                    bootstrap_watchdog.stop()
                if bootstrap_loop.isRunning():
                    bootstrap_loop.quit()

        def _ensure_per_job_bootstrap_connections() -> None:
            for job_id, (handler, handle_signals) in list(self.runner.history.items()):
                if handler.name not in _ADB_BOOTSTRAP_JOB_NAMES:
                    continue
                if job_id in connected_job_ids:
                    continue
                handle_signals.Completed.connect(_on_bootstrap_job_finished)
                handle_signals.Failed.connect(_on_bootstrap_job_finished)
                handle_signals.Cancelled.connect(_on_bootstrap_job_finished)
                handle_bindings.append((handle_signals, _on_bootstrap_job_finished))
                connected_job_ids.add(job_id)

        def _unblock_bootstrap_loop() -> None:
            logger.warning(
                "Bootstrap jobs exceeded the shutdown wait",
                timeout_ms=_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS,
            )
            if bootstrap_loop.isRunning():
                bootstrap_loop.quit()

        bootstrap_watchdog: QTimer = watchdog(_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS)(
            _unblock_bootstrap_loop
        )

        _ensure_per_job_bootstrap_connections()
        QTimer.singleShot(0, _recheck_bootstrap_jobs)

        try:
            bootstrap_loop.exec()
        finally:
            if bootstrap_watchdog.isActive():
                bootstrap_watchdog.stop()
            for hs, slot in handle_bindings:
                try:
                    hs.Completed.disconnect(slot)
                    hs.Failed.disconnect(slot)
                    hs.Cancelled.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass

    @Slot()
    def _on_application_about_to_quit(self) -> None:
        """Drain bootstrap async work, run close like other jobs, then tear down runners."""

        self.cron_manager.stop()
        self.view = None  # Ensure the view is not accessible anymore, no data will be forwarded to it

        self._wait_for_adb_bootstrap_jobs()  # Waiting for ADB running jobs (pre aboutToQuit signal) to finish before shutting down

        shutdown_loop = QEventLoop()

        def _unblock_shutdown_loop() -> None:
            logger.warning(
                "Core runtime close exceeded the shutdown wait",
                timeout_ms=_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS,
            )
            if shutdown_loop.isRunning():
                shutdown_loop.quit()

        shutdown_watchdog: QTimer = watchdog(_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS)(
            _unblock_shutdown_loop
        )

        def _after_close_applied() -> None:
            if shutdown_watchdog.isActive():
                shutdown_watchdog.stop()
            if shutdown_loop.isRunning():
                shutdown_loop.quit()

        self._adb._enqueue_close_core_runtime(after_apply=_after_close_applied)

        try:
            shutdown_loop.exec()
        finally:
            if shutdown_watchdog.isActive():
                shutdown_watchdog.stop()
        try:
            self._map.persist_simulation_repository()
        except Exception:
            logger.exception("Simulation repository persistence failed during shutdown")
        self.runner.shutdown()
