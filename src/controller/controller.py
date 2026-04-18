import importlib
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtWidgets import QWidget

from core.devices import Phone
from core.location import Location
from core.models import CoreRuntimeModel
from core.signals import (
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    DevicePairingFailedPayload,
    DevicePairingSucceededPayload,
    DevicesUpdatedPayload,
)
from gui.signals import app_signals
from logger import logger

_async_mod = importlib.import_module("controller.async")
AsyncRunner = _async_mod.AsyncRunner
JobError = _async_mod.JobError
JobHandler = _async_mod.JobHandler
JobSpecification = _async_mod.JobSpecification
ProgressEvent = _async_mod.ProgressEvent


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
        self._runner: AsyncRunner = AsyncRunner(view)
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

    @property
    def runner(self) -> AsyncRunner:

        return self._runner

    def _submit_model_async_call(
        self,
        *,
        name: str,
        fn: Callable[..., Any],
        description: str = "",
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        on_completed: Callable[[object], None] | None = None,
        on_failed: Callable[[JobError], None] | None = None,
        on_cancelled: Callable[[], None] | None = None,
        on_progress: Callable[[ProgressEvent], None] | None = None,
        job_type: str = "auto",
        timeout: int | None = None,
        priority: int = 0,
        coalesce_key: str | None = None,
    ) -> JobHandler:
        """
        Submit a model-related async job and bind any provided callbacks.

        Completed callbacks are invoked by AsyncRunner on the Qt main thread,
        which makes this helper the standard entry point for future controller
        -> model async orchestration.
        """
        job = JobSpecification(
            name=name,
            description=description or name,
            fn=fn,
            args=args,
            kwargs={} if kwargs is None else kwargs,
            timeout=timeout,
            priority=priority,
            coalesce_key=coalesce_key,
            type=job_type,
        )
        handle = self.runner.submit(job)
        handle_signals = self.runner.bind_handle_signals(handle)

        if on_progress is not None:
            handle_signals.Progress.connect(on_progress)
        if on_completed is not None:
            handle_signals.Completed.connect(on_completed)
        if on_cancelled is not None:
            handle_signals.Cancelled.connect(on_cancelled)
        if on_failed is not None:
            handle_signals.Failed.connect(on_failed)

        logger.debug(
            "Controller: async model job submitted",
            controller_type=type(self).__name__,
            model_type=type(self.model).__name__,
            job_id=handle.job_id,
            job_name=name,
            job_type=job_type,
            coalesce_key=coalesce_key,
        )
        return handle


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
                "SimulationController: core runtime startup skipped (model type)",
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
        self.model.subscribe(CoreSignal.ADB_SERVER_STARTED, self._on_adb_server_started)
        self.model.subscribe(CoreSignal.ADB_SERVER_STOPPED, self._on_adb_server_stopped)

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

    def _on_adb_server_started(self, payload: AdbServerStartedPayload) -> None:
        """Handle the ADB server started event."""
        logger.info(
            "SimulationController: ADB server started",
            adb_binary=str(payload.adb_binary),
        )
        self.view.on_adb_server_started()

    def _on_adb_server_stopped(self, payload: AdbServerStoppedPayload) -> None:
        """Handle the ADB server stopped event."""
        logger.info(
            "SimulationController: ADB server stopped",
            adb_binary=str(payload.adb_binary),
        )
        self.view.on_adb_server_stopped()

    def _on_authentification_confirmed(
        self, ip: str, port: str, association_code: str
    ) -> None:
        """Handle the authentification confirmation."""
        logger.info(
            "SimulationController: pair_device requested (auth confirmed)",
            ip=ip,
            port=port,
            association_code=association_code,
        )
        self.model.pair_device(ip, port, association_code)

    def _on_devices_updated(self, payload: DevicesUpdatedPayload) -> None:
        """Handle the devices updated event."""
        device_ids = [d.descriptor.id for d in payload.devices]
        logger.info(
            "SimulationController: devices updated",
            device_count=len(device_ids),
            device_ids=device_ids,
        )
        self.view.on_devices_updated(device_ids)

    def _on_device_pairing_succeeded(
        self, payload: DevicePairingSucceededPayload
    ) -> None:
        """Handle the device pairing succeeded event."""
        desc = payload.device.descriptor
        logger.success(
            "SimulationController: device pairing succeeded",
            device_id=desc.id,
            device_name=desc.name,
        )
        # TODO: Retrieve device informations
        self.view.on_device_pairing_succeeded(desc.id)

    def _on_device_pairing_failed(self, payload: DevicePairingFailedPayload) -> None:
        """Handle the device pairing failed event."""
        logger.warning(
            "SimulationController: device pairing failed",
            ip=payload.ip,
            port=payload.port,
            association_code=payload.association_code,
        )

    def _on_device_connection_requested(self, device_id: str) -> None:
        """Handle the device connection requested event."""
        logger.info(
            "SimulationController: device connection requested",
            device_id=device_id,
        )
        device: Phone | None = self.model.get_device(device_id)
        if device is None:
            logger.warning(
                "SimulationController: device not found",
                device_id=device_id,
            )
            return
        self._state.device = device
        desc = device.descriptor
        logger.info(
            "SimulationController: active device set",
            device_id=desc.id,
            device_name=desc.name,
        )

    def _on_refresh_device_list_requested(self) -> None:
        """Handle the refresh device list requested event."""
        logger.info("SimulationController: refresh device list requested")
        known_devices: list[Phone] = self.model.get_known_devices()
        device_ids = [d.descriptor.id for d in known_devices]
        logger.info(
            "SimulationController: known devices listed",
            device_count=len(device_ids),
            device_ids=device_ids,
        )
        self.view.on_devices_updated(device_ids)


class MapController(Controller):

    def __init__(self, model, view):
        super().__init__(model, view)
