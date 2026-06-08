from abc import ABC
from functools import cached_property
from pathlib import Path
from typing import Any, Callable

from core.adb import AdbClient, AdbServer
from core.application_paths import (
    get_or_create_application_dir,
    get_or_create_config_dir,
)
from core.devices import Computer, Phone
from core.signals import (
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    DeviceAuthentificationFailedPayload,
    DevicesUpdatedPayload,
    InMemoryCoreSignalBus,
    SignalHandler,
)
from core.simulation import Simulation, SimulationRepository
from core.work.authentificate_device_work import (
    AuthenticateDeviceWork,
    AuthentificateDeviceOutcome,
)
from core.work.close_work import CloseCoreRuntimeWork, CloseOutcome
from core.work.core_runtime_work import CoreRuntimeWorkOutcome
from core.work.host_install_identity_work import (
    HostInstallIdentityOutcome,
    HostInstallIdentityWork,
)
from core.work.refresh_known_devices_work import (
    RefreshKnownDevicesOutcome,
    RefreshKnownDevicesWork,
)
from core.work.startup_work import StartupCoreRuntimeWork, StartupOutcome
from core.work.works_repository import CORE_RUNTIME_WORKS
from logger import logger

# Main-thread appliers keyed by exact worker outcome type (AsyncRunner completion).
CoreRuntimeResultApplier = Callable[["CoreRuntimeModel", CoreRuntimeWorkOutcome], None]

_CORE_RUNTIME_RESULT_APPLIERS: dict[
    type[CoreRuntimeWorkOutcome], CoreRuntimeResultApplier
] = {
    entry.outcome_cls: entry.work_cls.apply_main_thread for entry in CORE_RUNTIME_WORKS
}


def register_core_runtime_result_applier(
    result_type: type[CoreRuntimeWorkOutcome],
    applier: CoreRuntimeResultApplier,
) -> None:
    """Register or replace the main-thread applier for ``result_type`` outcomes."""
    _CORE_RUNTIME_RESULT_APPLIERS[result_type] = applier


class Model(ABC):

    def __init__(self):

        self._signal_bus: InMemoryCoreSignalBus = InMemoryCoreSignalBus()

    @cached_property
    def config_dir(self) -> Path:
        return get_or_create_config_dir()

    @cached_property
    def application_dir(self) -> Path:
        return get_or_create_application_dir()

    def subscribe(self, signal: CoreSignal, handler: SignalHandler[object]) -> None:
        self._signal_bus.subscribe(signal, handler)

    def unsubscribe(self, signal: CoreSignal, handler: SignalHandler[object]) -> None:
        self._signal_bus.unsubscribe(signal, handler)


class CoreRuntimeModel(Model):
    """
    Generic core model that owns runtime services used by controllers.

    This class centralizes core infrastructure startup concerns so controllers
    can interact with a stable model API rather than low-level core classes.
    """

    def __init__(self, *, use_mock_adb: bool = False) -> None:
        super().__init__()
        self._host: Computer = Computer(id="host-1")
        self._adb_server: AdbServer | None = None
        self._adb_client: AdbClient | None = None
        self._use_mock_adb: bool = use_mock_adb
        self._simulations: SimulationRepository = SimulationRepository(
            self.application_dir / "simulations"
        )

    @property
    def host(self) -> Computer:
        """Return the host device."""
        return self._host

    @property
    def adb_server(self) -> AdbServer | None:
        """Return the active ADB server instance if available."""
        return self._adb_server

    def startup(self) -> StartupOutcome:
        """
        Initialize runtime core services at application startup (worker thread).
        """
        return StartupCoreRuntimeWork(use_mock_adb=self._use_mock_adb).run()

    def authentificate_device(
        self, ip: str, port: int, association_code: str
    ) -> AuthentificateDeviceOutcome:
        """
        Pair the device over ADB (worker thread). Does not emit on the core bus;
        controllers apply outcomes on the main thread after AsyncRunner completes.
        """
        if self._adb_server is None or self._adb_client is None:
            raise AttributeError(
                "ADB server and client must be initialized before authentification"
            )
        self._host.refresh_network_identity()
        if not self._host.is_network_available():
            return AuthentificateDeviceOutcome(
                success_phone=None,
                failure=DeviceAuthentificationFailedPayload(
                    ip=ip,
                    port=port,
                    association_code=association_code,
                    reason="Host network is unavailable",
                ),
            )
        # Check if a device with this IP address on the current ADB server is already paired
        for device in self._adb_server.paired_devices:
            if device.ip == ip:
                return AuthentificateDeviceOutcome(
                    success_phone=None,
                    failure=DeviceAuthentificationFailedPayload(
                        ip=ip,
                        port=port,
                        association_code=association_code,
                        reason="Device with this IP address is already paired",
                    ),
                )
        return AuthenticateDeviceWork(
            adb_server=self._adb_server,
            adb_client=self._adb_client,
            ip=ip,
            port=port,
            association_code=association_code,
        ).run()

    def refresh_known_devices(self) -> RefreshKnownDevicesOutcome:
        """
        List devices from the bound server and enrich ``ro.serialno`` via ADB.
        Blocking; intended for AsyncRunner / worker-thread use only.
        """
        if self._adb_server is None or self._adb_client is None:
            raise AttributeError(
                "ADB server and client must be initialized before refreshing devices"
            )
        return RefreshKnownDevicesWork(self._adb_server, self._adb_client).run()

    def run_host_install_identity(self) -> HostInstallIdentityOutcome:
        """
        Load or create persisted install UUID (worker thread).

        Apply on the main thread via :meth:`apply_result` after AsyncRunner completes.
        """
        return HostInstallIdentityWork().run()

    def close_core_runtime(self) -> CloseOutcome:
        """
        Stop the ADB server (worker thread). Apply on the main thread via :meth:`apply_result`.
        """
        if self._adb_server is None:
            return CloseOutcome(adb_server=None)
        return CloseCoreRuntimeWork(self._adb_server).run()

    def restart_adb_server(self) -> None:
        """
        Restart the ADB server and keep the instance in model state.
        """
        if self._adb_server is not None:
            self._signal_bus.emit(
                CoreSignal.ADB_SERVER_STOPPED,
                AdbServerStoppedPayload(adb_binary=self._adb_server.binary),
            )
            self._adb_server.restart()
            logger.info(
                "CoreRuntimeModel: ADB server restarted",
                adb_path=str(self._adb_server.binary.path),
            )
            self._signal_bus.emit(
                CoreSignal.ADB_SERVER_STARTED,
                AdbServerStartedPayload(adb_binary=self._adb_server.binary),
            )
            self._signal_bus.emit(
                CoreSignal.DEVICES_UPDATED,
                DevicesUpdatedPayload(devices=self.get_known_devices()),
            )
        else:
            logger.warning(
                "CoreRuntimeModel: ADB server restart skipped (not running)",
            )

    def get_device(self, device_id: str) -> Phone | None:
        """
        Get a device from the ADB server.
        """
        if self._adb_server is None or self._adb_client is None:
            raise AttributeError(
                "ADB server and client must be initialized before getting a device"
            )
        return self._adb_server.paired_devices.get(
            device_id
        )  # Returns None if the device is not found

    def get_known_devices(self, server: AdbServer | None = None) -> list[Phone]:
        """
        List devices from a server instance, or from the current model server when
        ``server`` is omitted (e.g. after startup has been applied on the main thread).
        """
        resolved: AdbServer | None = server if server is not None else self._adb_server
        if resolved is None:
            return []
        return resolved.get_known_devices()

    def create_simulation(self, device_id: str) -> str:
        """
        Create a new simulation.
        """
        device: Phone | None = self.get_device(device_id)
        if device is None:
            raise AttributeError(f"Device with id {device_id} not found")
        simulation: Simulation = Simulation(device=device)
        self._simulations.add(simulation)
        return simulation.id

    def get_simulation(self, id: str) -> Simulation | None:
        """
        Get a simulation by id.
        """
        return self._simulations.get(id)

    def is_simulation_active(self, id: str) -> bool:
        """
        Check if a simulation is active.
        """
        simulation: Simulation | None = self._simulations.get(id)
        if simulation is None:
            raise ValueError(f"Simulation with id {id} not found")
        return simulation.active

    def set_simulation_active(self, id: str, active: bool) -> None:
        """
        Set a simulation active or inactive.
        """
        simulation: Simulation | None = self._simulations.get(id)
        if simulation is None:
            raise ValueError(f"Simulation with id {id} not found")
        simulation.active = active

    def update_simulation(self, id: str, **kwargs: Any) -> None:
        """
        Update a simulation.
        """
        simulation: Simulation | None = self._simulations.get(id)
        if simulation is None:
            raise ValueError(f"Simulation with id {id} not found")
        for key, value in kwargs.items():
            setattr(simulation, key, value)

    def delete_simulation(self, simulation: Simulation) -> None:
        """
        Delete a simulation by id.
        """
        return self._simulations.remove(simulation)

    def delete_simulation_for_device(self, device_id: str) -> None:
        """
        Delete a simulation for a device by id.
        """
        for simulation in self._simulations:
            if simulation.device.id == device_id:
                self.delete_simulation(simulation)
                return
        raise ValueError(f"Simulation for device with id {device_id} not found")

    def apply_result(self, result: CoreRuntimeWorkOutcome) -> None:
        """
        Dispatch worker results to the matching ``apply_main_thread`` helper (Qt main thread).

        Unknown types are logged; callbacks may validate before calling for clearer context.
        """
        applier = _CORE_RUNTIME_RESULT_APPLIERS.get(type(result))
        if applier is None:
            logger.error(
                "CoreRuntimeModel.apply_result: unsupported result type",
                result_type=type(result).__name__,
            )
            return
        applier(self, result)
