"""
Simulation state and lifecycle (active device, locations, start/stop/resume/pause).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from collection import Repository
from controller.helper import validate_model, validate_view
from core.devices import Phone
from core.location import Location
from core.models import CoreRuntimeModel
from gui.signals import view_signals
from gui.window import MainWindow
from logger import logger

if TYPE_CHECKING:
    from controller.app_controller import AppController


@dataclass(unsafe_hash=True, match_args=True)
class Simulation:
    """Simulation."""

    id: Final[str] = field(
        default_factory=lambda: uuid.uuid4().hex,
        metadata={"description": "The id of the simulation"},
        hash=True,
    )
    real_location: Location = field(
        default_factory=lambda: Location(lat=0.0, lon=0.0, label=None),
        metadata={"description": "The real location of the device"},
    )
    fake_location: Location = field(
        default_factory=lambda: Location(lat=0.0, lon=0.0, label=None),
        metadata={"description": "The fake location to simulate on the device"},
    )
    device: Final[Phone] = field(
        default=None, metadata={"description": "The device of the simulation"}
    )
    log_file: Path = field(
        default=None, metadata={"description": "The log file of the simulation"}
    )
    active: bool = field(
        default=False, metadata={"description": "Whether the simulation is active"}
    )
    # When True, ``__setattr__`` logs changes to the public simulation fields.
    _fields_ready: bool = field(init=False, repr=False, compare=False, default=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_fields_ready", True)

    def __setattr__(self, name: str, value: object) -> None:
        if name in self.__class__.__dataclass_fields__ and name != "_fields_ready":
            if self._fields_ready and hasattr(self, name):
                old = getattr(self, name)
                if old != value:
                    logger.info(
                        f"Simulation {self.id}: field updated",
                        field=name,
                        old=old,
                        new=value,
                    )
        object.__setattr__(self, name, value)


class SimulationRepository(Repository[Simulation]):
    """Repository for the simulations."""

    def __init__(self) -> None:
        super().__init__()


class SimulationSubController:
    """Subcontroller for the current simulation model state (no own AsyncRunner)."""

    def __init__(self, app: AppController) -> None:
        self._app = app
        sim_id = uuid.uuid4().hex
        self._session: Simulation = Simulation(
            id=sim_id,
            log_file=self._app.model.config_dir / "simulations" / f"{sim_id}.log",
        )

    @property
    def model(self) -> CoreRuntimeModel:
        return self._app.model

    @property
    def view(self) -> MainWindow:
        return self._app.view

    def connect_view_signals(self) -> None:
        view_signals.DeviceSelectionRequested.connect(
            self._on_device_selection_requested
        )
        view_signals.SimulationLogFileUpdateRequested.connect(
            self._on_simulation_log_file_update_requested
        )

    def connect_model_signals(self) -> None:
        # Simulation-specific model subscriptions (none yet) — extension point.
        return

    def send_host_device_information(self) -> None:
        """
        Send the host device information to the view.

        Run once after the main window is wired.
        """
        self._send_host_device_information()

    def send_simulation_log_file_to_view(self) -> None:
        """
        Send the default log file path for the current simulation to the view.

        Run once after the main window is wired.
        """
        self._send_simulation_log_file_to_view()

    @validate_view
    def _send_host_device_information(self) -> None:
        self.view.forward_host_device_information_updated(
            self.model.host.get_name(),
            self.model.host.get_os(),
            self.model.host.get_ip(),
        )

    @validate_view
    def _send_simulation_log_file_to_view(self) -> None:
        log = self._session.log_file
        path_str = str(log) if log is not None else ""
        self.view.forward_simulation_log_file_updated(self._session.id, path_str)

    @property
    def device(self) -> Phone | None:
        return self._session.device

    @device.setter
    def device(self, device: Phone) -> None:
        self._session.device = device

    @property
    def real_location(self) -> Location | None:
        return self._session.real_location

    @real_location.setter
    def real_location(self, real_location: Location) -> None:
        self._session.real_location = real_location

    @property
    def fake_location(self) -> Location | None:
        return self._session.fake_location

    @fake_location.setter
    def fake_location(self, fake_location: Location) -> None:
        self._session.fake_location = fake_location

    def run(self) -> None:
        """Run the simulation."""
        pass

    def stop(self) -> None:
        """Stop the simulation."""
        pass

    def pause(self) -> None:
        """Pause the simulation."""
        pass

    def resume(self) -> None:
        """Resume the simulation."""
        pass

    @validate_model
    def _on_device_selection_requested(self, device_id: str) -> None:
        """In-memory selection of the active device (UI thread)."""
        logger.info(
            "SimulationSubController: device connection requested",
            device_id=device_id,
        )
        try:
            device: Phone = self.model.get_device(device_id)
        except AttributeError as e:
            logger.error(
                "SimulationSubController: failed to get device",
                error=str(e),
                device_id=device_id,
            )
            return
        self._session.device = device
        desc = device.descriptor
        logger.info(
            "SimulationSubController: active device set",
            device_id=desc.id,
            device_name=desc.name,
        )

    @validate_view
    def _on_simulation_log_file_update_requested(self, filename: str) -> None:
        """In-memory selection of the active device (UI thread)."""
        logger.info(
            "SimulationSubController: simulation log file update requested",
            filename=filename,
        )
        self._session.log_file = Path(filename)
        self._send_simulation_log_file_to_view()
