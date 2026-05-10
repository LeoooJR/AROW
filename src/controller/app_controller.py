"""
Application-level controller: one :class:`Controller` owning a single :class:`AsyncRunner`,
composed of *SubController domain objects.
"""

from __future__ import annotations

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from controller.adb_sub_controller import AdbSubController
from controller.controller import Controller
from controller.map_sub_controller import MapSubController
from controller.simulation_sub_controller import SimulationSubController
from core.models import CoreRuntimeModel
from gui.window import MainWindow
from logger import logger

# Hard cap blocking quit until close job applies; avoids orphaned ADB during exit.
_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS = 30_000


class AppController(Controller):
    """
    Main coordinator. Subclass of :class:`Controller` with a single async runner;
    delegates ADB, simulation, and map concerns to *SubController instances.
    """

    def __init__(self, model: CoreRuntimeModel, view: MainWindow) -> None:
        # Subcontrollers need a fully constructed app reference; defer signal
        # wiring in Controller until children exist.
        super().__init__(model, view, defer_signal_connect=True)
        self._simulation: SimulationSubController = SimulationSubController(self)
        self._adb: AdbSubController = AdbSubController(self)
        self._map: MapSubController = MapSubController(self)
        self._connect_view_signals()
        self._connect_model_signals()
        self._simulation.send_host_device_information()
        self._simulation.send_simulation_log_file_to_view()
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

        qt_app = QApplication.instance()
        if qt_app is not None:
            qt_app.aboutToQuit.connect(self._on_application_about_to_quit)

    def _connect_model_signals(self) -> None:
        self._simulation.connect_model_signals()
        self._adb.connect_model_signals()
        self._map.connect_model_signals()

    def _on_application_about_to_quit(self) -> None:
        """Run close work like other jobs; block until applied, then tear down runners."""
        if self.model.adb_server is None:
            self.model.apply_result(self.model.close_core_runtime())
            self.runner.shutdown()
            return

        self.view = None  # Ensure the view is not accessible anymore, no data will be forwarded to it

        shutdown_loop = QEventLoop()
        watchdog = QTimer()
        watchdog.setSingleShot(True)

        def _unblock_shutdown_loop() -> None:
            logger.warning(
                "AppController: close_core_runtime exceeded shutdown wait",
                timeout_ms=_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS,
            )
            if shutdown_loop.isRunning():
                shutdown_loop.quit()

        def _after_close_applied() -> None:
            watchdog.stop()
            if shutdown_loop.isRunning():
                shutdown_loop.quit()

        watchdog.timeout.connect(_unblock_shutdown_loop)
        watchdog.start(_SHUTDOWN_CLOSE_JOB_TIMEOUT_MS)
        self._adb._enqueue_close_core_runtime(after_apply=_after_close_applied)
        shutdown_loop.exec()
        watchdog.stop()
        self.runner.shutdown()
