"""
Application-level controller: one :class:`Controller` owning a single :class:`AsyncRunner`,
composed of *SubController domain objects.
"""

from __future__ import annotations

from controller.adb_sub_controller import AdbSubController
from controller.controller import Controller
from controller.map_sub_controller import MapSubController
from controller.simulation_sub_controller import SimulationSubController
from core.models import CoreRuntimeModel
from gui.window import MainWindow


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

    def _connect_model_signals(self) -> None:
        self._simulation.connect_model_signals()
        self._adb.connect_model_signals()
        self._map.connect_model_signals()
