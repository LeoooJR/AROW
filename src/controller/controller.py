import importlib
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from collection import Repository
from core.devices import Phone
from core.location import Location
from core.models import CoreRuntimeModel
from core.signals import (
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    DeviceConnectionFailedPayload,
    DeviceConnectionSucceededPayload,
    DevicesUpdatedPayload,
)
from gui.signals import app_signals
from gui.window import MainWindow
from logger import logger

_async_mod = importlib.import_module("controller.async")
AsyncRunner = _async_mod.AsyncRunner
JobError = _async_mod.JobError
JobHandler = _async_mod.JobHandler
JobSpecification = _async_mod.JobSpecification
ProgressEvent = _async_mod.ProgressEvent


def validate_model(function: Callable[..., Any]) -> Callable[..., Any]:
    """Validate the model for the function.

    Args:
        function: Function to validate the model for.

    Returns:
        Function: Function with the model validated.
    """

    def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(self.model, CoreRuntimeModel):
            logger.warning(
                "Controller: model type mismatch",
                model_type=type(self.model).__name__,
            )
            return
        return function(self, *args, **kwargs)

    return wrapper


def validate_view(function: Callable[..., Any]) -> Callable[..., Any]:
    """Validate the view for the function.

    Args:
        function: Function to validate the view for.

    Returns:
        Function: Function with the view validated.
    """

    def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(self.view, MainWindow):
            logger.warning(
                "Controller: view type mismatch",
                view_type=type(self.view).__name__,
            )
            return
        return function(self, *args, **kwargs)

    return wrapper


@dataclass
class Simulation:
    """Simulation."""

    id: str = field(
        default=uuid.uuid4().hex, metadata={"description": "The id of the simulation"}
    )
    real_location: Location = field(
        default_factory=lambda: Location(lat=0.0, lon=0.0, label=None),
        metadata={"description": "The real location of the device"},
    )
    fake_location: Location = field(
        default_factory=lambda: Location(lat=0.0, lon=0.0, label=None),
        metadata={"description": "The fake location to simulate on the device"},
    )
    device: Phone = field(
        default=None, metadata={"description": "The device of the simulation"}
    )
    log_file: Path = field(
        default=None, metadata={"description": "The log file of the simulation"}
    )
    active: bool = field(
        default=False, metadata={"description": "Whether the simulation is active"}
    )


class SimulationRepository(Repository[Simulation]):
    """Repository for the simulations."""

    def __init__(self):
        super().__init__()


class Controller(ABC):
    """Controller for the application."""

    def __init__(self, model: CoreRuntimeModel, view: MainWindow):
        """Initialize the controller.

        Args:
            model: Model for the application.
            view: View for the application.
        """
        self._model: CoreRuntimeModel = model
        self._view: MainWindow = view
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

    #### Getters / Setters ####

    @property
    def view(self) -> MainWindow:
        """Get the view for the application."""
        return self._view

    @view.setter
    def view(self, view: MainWindow) -> None:
        """Set the view for the application."""
        self._view = view

    @property
    def model(self) -> CoreRuntimeModel:
        """Get the model for the application."""
        return self._model

    @model.setter
    def model(self, model: CoreRuntimeModel) -> None:
        """Set the model for the application."""
        self._model = model

    @property
    def runner(self) -> AsyncRunner:
        """Get the asynchronous runner for the application."""
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

        Args:
            name: Name of the job.
            fn: Function to execute.
            description: Description of the job.
            args: Arguments to pass to the function.
            kwargs: Keyword arguments to pass to the function.
            on_completed: Callback to execute when the job is completed.
            on_failed: Callback to execute when the job fails.
            on_cancelled: Callback to execute when the job is cancelled.
            on_progress: Callback to execute when the job progresses.
            job_type: Type of the job (auto, thread, process).
            timeout: Timeout for the job.
            priority: Priority of the job (0-100).
            coalesce_key: Key to coalesce the job (none, location, network, device).

        Returns:
            JobHandler: JobHandler for the job. This can be used to cancel the job.
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
    """Controller for the simulation."""

    def __init__(self, model, view):
        """Initialize the simulation controller.

        Args:
            model: Model for the simulation.
            view: View for the simulation.
        """
        super().__init__(model, view)

        self._simulation: Simulation = Simulation()
        self._send_host_device_information()
        self._startup_core_runtime()

    @validate_view
    def _connect_view_signals(self) -> None:
        """Connect view signals to controller methods.

        Args:
            None

        Returns:
            None
        """
        app_signals.AuthentificationConfirmed.connect(
            self._on_authentification_confirmed
        )
        app_signals.DeviceConnectionRequested.connect(
            self._on_device_connection_requested
        )
        app_signals.RefreshDeviceListRequested.connect(
            self._on_refresh_device_list_requested
        )

    @validate_model
    def _connect_model_signals(self) -> None:
        """Connect model signals to controller methods.

        Args:
            None

        Returns:
            None
        """

        #### ADB Server Signals ####
        self.model.subscribe(CoreSignal.ADB_SERVER_STARTED, self._on_adb_server_started)
        self.model.subscribe(CoreSignal.ADB_SERVER_STOPPED, self._on_adb_server_stopped)

        #### Device Signals ####
        self.model.subscribe(CoreSignal.DEVICES_UPDATED, self._on_devices_updated)
        self.model.subscribe(
            CoreSignal.DEVICE_CONNECTION_SUCCEEDED, self._on_device_connection_succeeded
        )
        self.model.subscribe(
            CoreSignal.DEVICE_CONNECTION_FAILED, self._on_device_connection_failed
        )

    #### Getters / Setters ####

    @property
    def device(self) -> Phone | None:
        """Get the device for the simulation."""

        return self._simulation.device

    @device.setter
    def device(self, device: Phone) -> None:
        """Set the device for the simulation."""
        self._simulation.device = device

    @property
    def real_location(self) -> Location | None:
        """Get the real location for the simulation."""
        return self._simulation.real_location

    @real_location.setter
    def real_location(self, real_location: Location) -> None:
        """Set the real location for the simulation."""
        self._simulation.real_location = real_location

    @property
    def fake_location(self) -> Location | None:
        """Get the fake location for the simulation."""
        return self._simulation.fake_location

    @fake_location.setter
    def fake_location(self, fake_location: Location) -> None:
        """Set the fake location for the simulation."""
        self._simulation.fake_location = fake_location

    @validate_view
    def _send_host_device_information(self) -> None:
        """
        Send the host device information to the view.

        Args:
            None

        Returns:
            None
        """
        self.view.on_host_device_information_updated(
            self.model.host.get_name(),
            self.model.host.get_os(),
            self.model.host.get_ip(),
        )

    @validate_model
    def _startup_core_runtime(self) -> None:
        """
        Ask the core model to initialize runtime services at startup.

        Args:
            None

        Returns:
            None
        """
        self.model.startup()

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

    @validate_view
    def _on_adb_server_started(self, payload: AdbServerStartedPayload) -> None:
        """Handle the ADB server started event."""
        logger.info(
            "SimulationController: ADB server started",
            adb_binary=str(payload.adb_binary),
        )
        self.view.on_adb_server_started()

    @validate_view
    def _on_adb_server_stopped(self, payload: AdbServerStoppedPayload) -> None:
        """Handle the ADB server stopped event."""
        logger.info(
            "SimulationController: ADB server stopped",
            adb_binary=str(payload.adb_binary),
        )
        self.view.on_adb_server_stopped()

    @validate_model
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

    @validate_view
    def _on_devices_updated(self, payload: DevicesUpdatedPayload) -> None:
        """Handle the devices updated event."""
        device_ids = [d.descriptor.id for d in payload.devices]
        logger.info(
            "SimulationController: devices updated",
            device_count=len(device_ids),
            device_ids=device_ids,
        )
        self.view.on_devices_updated(device_ids)

    @validate_view
    def _on_device_connection_succeeded(
        self, payload: DeviceConnectionSucceededPayload
    ) -> None:
        """Handle the device connection succeeded event."""
        desc = payload.phone.descriptor
        logger.success(
            "SimulationController: device connection succeeded",
            device_id=desc.id,
            device_name=desc.name,
        )
        self.view.on_device_pairing_succeeded(
            desc.id
        )  # TODO: Rename to on_device_connection_succeeded

    @validate_view
    def _on_device_connection_failed(
        self, payload: DeviceConnectionFailedPayload
    ) -> None:
        """Handle the device connection failed event."""
        logger.warning(
            "SimulationController: device connection failed",
            ip=payload.ip,
            port=payload.port,
            association_code=payload.association_code,
        )
        # TODO: Handle the device connection failed event

    @validate_model
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

    @validate_view
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
