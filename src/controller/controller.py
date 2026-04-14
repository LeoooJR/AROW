from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PySide6.QtWidgets import QWidget

from core.devices import Phone
from core.location import Location
from core.models import CoreRuntimeModel
from core.signals import (
    CoreSignal,
    DevicePairingFailedPayload,
    DevicePairingSucceededPayload,
    DevicesUpdatedPayload,
)
from gui.signals import app_signals
from logger import logger


@dataclass
class SimulationState:
    real_location: Location = field(
        default_factory=lambda: Location(lat=0.0, lon=0.0, label=None)
    )
    fake_location: Location = field(
        default_factory=lambda: Location(lat=0.0, lon=0.0, label=None)
    )
    device: Phone = field(default=None)
    active: bool = field(default=False)


class Controller(ABC):

    def __init__(self, model, view):

        self._model = model
        self._view = view
        self._connect_view_signals()
        self._connect_model_signals()

    @abstractmethod
    def _connect_view_signals(self):
        """
        Connect view signals to controller methods
        """

    @abstractmethod
    def _connect_model_signals(self):
        """
        Connect model signals to controller methods
        """

    @property
    def view(self) -> QWidget:

        return self._view

    @view.setter
    def view(self, view: QWidget) -> None:

        self._view = view

    @property
    def model(self) -> CoreRuntimeModel:

        return self._model

    @model.setter
    def model(self, model: CoreRuntimeModel) -> None:

        self._model = model


class SimulationController(Controller):

    def __init__(self, model, view):
        super().__init__(model, view)

        self._state: SimulationState = SimulationState()
        self._send_host_device_information()
        self._startup_core_runtime()

    def _send_host_device_information(self) -> None:
        """
        Send the host device information to the view.
        """
        self.view.on_host_device_information_updated(
            self.model.host.descriptor.name,
            self.model.host.descriptor.os,
            self.model.host.descriptor.ip,
        )

    def _startup_core_runtime(self) -> None:
        """
        Ask the core model to initialize runtime services at startup.
        """
        if not isinstance(self.model, CoreRuntimeModel):
            logger.warning(
                "Controller model does not support runtime startup",
                model_type=type(self.model).__name__,
            )
            return
        self.model.startup()

    def _connect_view_signals(self) -> None:
        app_signals.AuthentificationConfirmed.connect(
            self._on_authentification_confirmed
        )
        app_signals.DeviceConnectionRequested.connect(
            self._on_device_connection_requested
        )
        app_signals.RefreshDeviceListRequested.connect(
            self._on_refresh_device_list_requested
        )

    def _connect_model_signals(self) -> None:
        self.model.subscribe(CoreSignal.DEVICES_UPDATED, self._on_devices_updated)
        self.model.subscribe(
            CoreSignal.DEVICE_PAIRING_SUCCEEDED, self._on_device_pairing_succeeded
        )
        self.model.subscribe(
            CoreSignal.DEVICE_PAIRING_FAILED, self._on_device_pairing_failed
        )

    @property
    def device(self) -> Phone | None:

        return self.__dict__.get("_device", None)

    @device.setter
    def device(self, device: str) -> None:

        self._device = device

    @property
    def real_location(self) -> Location | None:
        return self.__dict__.get("_real_location", None)

    @real_location.setter
    def real_location(self, real_location: tuple[float, float]) -> None:
        self._real_location = real_location

    @property
    def fake_location(self) -> Location | None:
        return self.__dict__.get("_fake_location", None)

    @fake_location.setter
    def fake_location(self, fake_location: tuple[float, float]) -> None:
        self._fake_location = fake_location

    def run(self):
        pass

    def stop(self):
        pass

    def pause(self):
        pass

    def resume(self):
        pass

    def _on_authentification_confirmed(
        self, ip: str, port: str, association_code: str
    ) -> None:
        """Handle the authentification confirmation."""
        logger.info(
            f"Trying to connect to device with such credentials: IP: {ip}, Port: {port}, Association code: {association_code}."
        )
        self.model.pair_device(ip, port, association_code)

    def _on_devices_updated(self, payload: DevicesUpdatedPayload) -> None:
        """Handle the devices updated event."""
        logger.info(f"Devices updated: {payload.devices}")
        self.view.on_devices_updated(
            list(map(lambda device: device.descriptor.id, payload.devices))
        )

    def _on_device_pairing_succeeded(
        self, payload: DevicePairingSucceededPayload
    ) -> None:
        """Handle the device pairing succeeded event."""
        logger.success(f"Device pairing succeeded: {payload.device}")
        # TODO: Retrieve device informations
        self.view.on_device_pairing_succeeded(payload.device.descriptor.id)

    def _on_device_pairing_failed(self, payload: DevicePairingFailedPayload) -> None:
        """Handle the device pairing failed event."""
        logger.warning(
            f"Device pairing failed: {payload.ip}:{payload.port} with association code: {payload.association_code}"
        )

    def _on_device_connection_requested(self, device_id: str) -> None:
        """Handle the device connection requested event."""
        logger.info(f"Device connection requested: {device_id}")
        device: Phone | None = self.model.get_device(device_id)
        if device is None:
            logger.warning(f"Device with id {device_id} not found")
            return
        self.state.device = device
        logger.info(f"Working on device: {device}")

    def _on_refresh_device_list_requested(self) -> None:
        """Handle the refresh device list requested event."""
        logger.info("Refresh device list requested.")
        known_devices: list[Phone] = self.model.get_known_devices()
        logger.info(f"Known devices: {known_devices}")
        self.view.on_devices_updated(
            list(map(lambda device: device.descriptor.id, known_devices))
        )


class MapController(Controller):

    def __init__(self, model, view):
        super().__init__(model, view)
