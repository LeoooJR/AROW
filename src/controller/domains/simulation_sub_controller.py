"""
Simulation state and lifecycle (active device, locations, start/stop/resume/pause).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from collection import Repository
from controller.domains.app_sub_controller import AppSubController
from controller.helper import validate_model, validate_view
from core.devices import Phone, PhoneDescriptor
from core.location import Location
from gui.signals import view_signals
from gui.window import MainWindow
from logger import logger

if TYPE_CHECKING:
    from controller.orchestration.app_controller import AppController


@dataclass(unsafe_hash=True, match_args=True, frozen=False)
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

    # Setting _fields_ready to True to allow __setattr__ to log changes to the public simulation fields
    # This is done in __post_init__ to avoid logging the initial values of the public simulation fields
    def __post_init__(self) -> None:
        object.__setattr__(self, "_fields_ready", True)

    # Overriding __setattr__ to log changes to the public simulation fields
    def __setattr__(self, name: str, value: object) -> None:
        if name in self.__class__.__dataclass_fields__ and name != "_fields_ready":
            if self._fields_ready and hasattr(self, name):
                old = getattr(self, name)
                if old != value:
                    logger.debug(
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


class SimulationSubController(AppSubController):
    """Subcontroller for the current simulation model state (no own AsyncRunner)."""

    def __init__(self, app: AppController) -> None:
        super().__init__(app)
        sim_id: Final[str] = uuid.uuid4().hex
        self._session: Final[Simulation] = Simulation(
            id=sim_id,
            log_file=self.model.config_dir / "simulations" / f"{sim_id}.log",
        )

    def connect_view_signals(self) -> None:
        view_signals.DeviceSelectionConfirmed.connect(
            self._on_device_selection_confirmed
        )  # Ensuring the device is selected when the user confirms the selection
        view_signals.SimulationLogFileUpdateRequested.connect(
            self._on_simulation_log_file_update_requested
        )  # Ensuring the log file path is updated when the user requests it
        view_signals.RemoveDeviceRequested.connect(
            self._on_remove_device_requested
        )  # Ensuring no simulation is running before device is removed by adb subcontroller

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
        log: Path = self._session.log_file
        path_str: str = str(log) if log is not None else ""
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
        self._session.active = True
        # self.view.forward_simulation_started() # TODO: Implement this

    def stop(self) -> None:
        """Stop the simulation."""
        self._session.active = False
        # self.view.forward_simulation_stopped() # TODO: Implement this

    def pause(self) -> None:
        """Pause the simulation."""
        self._session.active = False
        # self.view.forward_simulation_paused() # TODO: Implement this

    def resume(self) -> None:
        """Resume the simulation."""
        self._session.active = True
        # self.view.forward_simulation_resumed() # TODO: Implement this

    def is_simulation_active(self) -> bool:
        """Check if the simulation is active."""
        return self._session.active

    @validate_model
    def _on_device_selection_confirmed(self, device_id: str, device_name: str) -> None:
        """In-memory selection of the active device (UI thread)."""
        logger.debug(
            "SimulationSubController: device selection confirmed",
            input_device_id=device_id,
            input_device_name=device_name,
        )
        try:
            device: Phone | None = self.model.get_device(device_id)
            desc: PhoneDescriptor = (
                device.descriptor
            )  # Will raise AttributeError if the device is not found (AttributeError: 'NoneType' object has no attribute 'descriptor')
            self._session.device: Phone = (
                device  # At this point, the device is guaranteed to be found
            )
            logger.success(
                "SimulationSubController: active device set",
                device_id=desc.id,
                device_name=desc.name,
            )
            self.view.forward_device_selection_succeeded(vars(desc))
        except AttributeError as e:
            logger.error(
                "SimulationSubController: failed to get device",
                error=str(e),
                device_id=device_id,
            )
            self.view.forward_device_selection_failed(
                {"id": device_id, "name": device_name}
            )

    @validate_view
    def _on_simulation_log_file_update_requested(self, path: str) -> None:
        """Update the log file path for the current simulation."""
        logger.debug(
            "SimulationSubController: simulation log file update requested",
            path=path,
        )
        self._session.log_file: Path = Path(path)
        self._send_simulation_log_file_to_view()

    def _on_remove_device_requested(self, id: str) -> None:
        """Handle the remove device requested event."""
        device = self._session.device
        if (
            device is None
        ):  # Remove request has been made before a device has been selected
            return
        if device.id != id:  # Remove request has been made for a different device
            return
        else:  # Remove request has been made for the active device
            if self.is_simulation_active():
                logger.info(
                    f"Active device {id} is being removed, stopping simulation."
                )
                self.stop()
            self._session.device = None
            self.view.forward_active_device_removed()
