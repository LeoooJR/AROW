from abc import ABC
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Tuple, overload

from shapely.geometry import Point

from core.adb.client import AdbClient
from core.adb.server import AdbServer
from core.application_paths import (
    default_activity_log_file_path,
    get_or_create_application_dir,
    get_or_create_config_dir,
)
from core.devices import (
    Computer,
    Phone,
    PhoneRepository,
    apply_discovered_phone_state,
    paired_phone_matches_discovery,
    phone_stable_key_is_collision_resistant,
    serialize_phone_collection,
)
from core.geo.element import Milestone
from core.geo.exceptions import MilestoneValidationError
from core.geo.location import Location
from core.signals import (
    ActivityLogFileUpdatedPayload,
    AdbServerStartedPayload,
    AdbServerStateChangedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    DeviceAuthentificationFailedPayload,
    DeviceAuthentificationSucceededPayload,
    DevicesUpdatedPayload,
    ErrorRaisedPayload,
    HostComputerIdentityPayload,
    InMemoryCoreSignalBus,
    LogMessagePayload,
    MapRenderedPayload,
    MapRenderFailedPayload,
    SignalHandler,
    SimulationCreatedPayload,
    SimulationDeletedPayload,
    SimulationLocationRejectedPayload,
    SimulationLocationValidatedPayload,
    SimulationMapFileChangedPayload,
    SimulationPositionChangedPayload,
    SimulationStateChangedPayload,
)
from core.simulation import Simulation, SimulationRepository
from core.work.authentificate_device_work import (
    AuthenticateDeviceWork,
    AuthentificateDeviceOutcome,
    DeviceAuthentificationError,
)
from core.work.close_work import CloseCoreRuntimeWork, CloseOutcome
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from core.work.host_install_identity_work import (
    HostInstallIdentityOutcome,
    HostInstallIdentityWork,
)
from core.work.refresh_known_devices_work import (
    RefreshKnownDevicesOutcome,
    RefreshKnownDevicesWork,
)
from core.work.render_map_work import RenderMapOutcome, RenderMapWork
from core.work.startup_work import StartupCoreRuntimeWork, StartupOutcome
from core.work.works_repository import CORE_RUNTIME_WORKS
from logger import logger

# Main-thread appliers keyed by exact worker outcome type (AsyncRunner completion).
CoreRuntimeResultApplier = Callable[["ModelEntrypoint", CoreRuntimeWorkOutcome], None]

_CORE_RUNTIME_RESULT_APPLIERS: dict[
    type[CoreRuntimeWorkOutcome], CoreRuntimeResultApplier
] = {
    entry.outcome_cls: entry.work_cls.apply_main_thread for entry in CORE_RUNTIME_WORKS
}

CoreRuntimeFailureApplier = Callable[["ModelEntrypoint", BaseException], None]

# Map job origin (name of the job) to the failure applier
_CORE_RUNTIME_FAILURE_APPLIERS: dict[str, CoreRuntimeFailureApplier] = {
    entry.job_origin: entry.work_cls.apply_failure_main_thread
    for entry in CORE_RUNTIME_WORKS
}

# Map exception type to the failure applier
_CORE_RUNTIME_EXCEPTION_FAILURE_APPLIERS: dict[
    type[BaseException], CoreRuntimeFailureApplier
] = {
    DeviceAuthentificationError: AuthenticateDeviceWork.apply_failure_main_thread,
}


def register_core_runtime_result_applier(
    result_type: type[CoreRuntimeWorkOutcome],
    applier: CoreRuntimeResultApplier,
) -> None:
    """Register or replace the main-thread applier for ``result_type`` outcomes."""
    _CORE_RUNTIME_RESULT_APPLIERS[result_type] = applier


@dataclass(frozen=True, slots=True)
class DeviceReconcileResult:
    """Outcome of reconciling a fresh ADB discovery list with paired devices."""

    changed: bool
    device_id_rebindings: Mapping[str, str] = field(default_factory=dict)


class Entrypoint(ABC):

    def __init__(self):

        self._signal_bus: InMemoryCoreSignalBus = InMemoryCoreSignalBus()

    @cached_property
    def config_dir(self) -> Path:
        return get_or_create_config_dir()

    @cached_property
    def application_dir(self) -> Path:
        return get_or_create_application_dir()

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STARTED],
        handler: SignalHandler[AdbServerStartedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STOPPED],
        handler: SignalHandler[AdbServerStoppedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STATE_CHANGED],
        handler: SignalHandler[AdbServerStateChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED],
        handler: SignalHandler[DeviceAuthentificationSucceededPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_FAILED],
        handler: SignalHandler[DeviceAuthentificationFailedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.DEVICES_UPDATED],
        handler: SignalHandler[DevicesUpdatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATED],
        handler: SignalHandler[SimulationCreatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_STATE_CHANGED],
        handler: SignalHandler[SimulationStateChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_POSITION_CHANGED],
        handler: SignalHandler[SimulationPositionChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_VALIDATED],
        handler: SignalHandler[SimulationLocationValidatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_REJECTED],
        handler: SignalHandler[SimulationLocationRejectedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_MAP_FILE_CHANGED],
        handler: SignalHandler[SimulationMapFileChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ERROR_RAISED],
        handler: SignalHandler[ErrorRaisedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.LOG_MESSAGE],
        handler: SignalHandler[LogMessagePayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED],
        handler: SignalHandler[HostComputerIdentityPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ACTIVITY_LOG_FILE_UPDATED],
        handler: SignalHandler[ActivityLogFileUpdatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDERED],
        handler: SignalHandler[MapRenderedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDER_FAILED],
        handler: SignalHandler[MapRenderFailedPayload],
    ) -> None: ...

    @overload
    def subscribe(self, signal: CoreSignal, handler: SignalHandler[object]) -> None: ...

    def subscribe(self, signal: CoreSignal, handler: SignalHandler[Any]) -> None:
        self._signal_bus.subscribe(signal, handler)

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STARTED],
        handler: SignalHandler[AdbServerStartedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STOPPED],
        handler: SignalHandler[AdbServerStoppedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STATE_CHANGED],
        handler: SignalHandler[AdbServerStateChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED],
        handler: SignalHandler[DeviceAuthentificationSucceededPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_FAILED],
        handler: SignalHandler[DeviceAuthentificationFailedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.DEVICES_UPDATED],
        handler: SignalHandler[DevicesUpdatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATED],
        handler: SignalHandler[SimulationCreatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_STATE_CHANGED],
        handler: SignalHandler[SimulationStateChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_POSITION_CHANGED],
        handler: SignalHandler[SimulationPositionChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_VALIDATED],
        handler: SignalHandler[SimulationLocationValidatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_REJECTED],
        handler: SignalHandler[SimulationLocationRejectedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_MAP_FILE_CHANGED],
        handler: SignalHandler[SimulationMapFileChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ERROR_RAISED],
        handler: SignalHandler[ErrorRaisedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.LOG_MESSAGE],
        handler: SignalHandler[LogMessagePayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED],
        handler: SignalHandler[HostComputerIdentityPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ACTIVITY_LOG_FILE_UPDATED],
        handler: SignalHandler[ActivityLogFileUpdatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDERED],
        handler: SignalHandler[MapRenderedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDER_FAILED],
        handler: SignalHandler[MapRenderFailedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self, signal: CoreSignal, handler: SignalHandler[object]
    ) -> None: ...

    def unsubscribe(self, signal: CoreSignal, handler: SignalHandler[Any]) -> None:
        self._signal_bus.unsubscribe(signal, handler)


class ModelEntrypoint(Entrypoint):
    """
    Core runtime entrypoint that owns services used by controllers.

    This class centralizes core infrastructure startup concerns so controllers
    can interact with a stable entrypoint API rather than low-level core classes.
    """

    def __init__(self, *, use_mock_adb: bool = False) -> None:
        super().__init__()
        self._host: Computer = Computer(id="host-1")
        self._adb_server: AdbServer | None = None
        self._adb_client: AdbClient | None = None
        self._use_mock_adb: bool = use_mock_adb
        self._activity_log_file: Path | None = None
        self._resolve_activity_log_file()
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

    @property
    def activity_log_file(self) -> Path | None:
        """Return the current app-wide activity log path, creating a default when unset."""
        return self._resolve_activity_log_file()

    @activity_log_file.setter
    def activity_log_file(self, value: Path) -> None:
        """Set the current app-wide activity log path."""
        self._activity_log_file = value
        self._signal_bus.emit(
            CoreSignal.ACTIVITY_LOG_FILE_UPDATED,
            ActivityLogFileUpdatedPayload(path=value),
        )

    def _resolve_activity_log_file(self) -> Path:
        """Resolve the current app-wide activity log path, creating a default when unset."""
        if self._activity_log_file is None:
            self._activity_log_file = default_activity_log_file_path(
                self.application_dir
            )
            self._signal_bus.emit(
                CoreSignal.ACTIVITY_LOG_FILE_UPDATED,
                ActivityLogFileUpdatedPayload(path=self._activity_log_file),
            )
        return self._activity_log_file

    def startup(self) -> StartupOutcome:
        """
        Initialize runtime core services at application startup (worker thread).
        """
        return StartupCoreRuntimeWork(use_mock_adb=self._use_mock_adb).run()

    def authentificate_device(
        self, ip: str, port: int, association_code: str
    ) -> AuthentificateDeviceOutcome:
        """
        Pair the device over ADB (worker thread).

        Success returns an outcome for main-thread apply; failures raise
        :class:`~core.work.authentificate_device_work.DeviceAuthentificationError`
        so AsyncRunner invokes the job ``on_failed`` callback.
        """
        if self._adb_server is None or self._adb_client is None:
            raise AttributeError(
                "ADB server and client must be initialized before authentification"
            )
        self._host.refresh_network_identity()
        if not self._host.is_network_available():
            raise DeviceAuthentificationError(
                ip=ip,
                port=port,
                association_code=association_code,
                reason="Host network is unavailable",
            )
        # Check if a device with this IP address on the current ADB server is already paired
        for device in self._adb_server.paired_devices:
            if device.ip == ip:
                raise DeviceAuthentificationError(
                    ip=ip,
                    port=port,
                    association_code=association_code,
                    reason="Device with this IP address is already paired",
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
        Load or create persisted install UUID (AsyncRunner worker thread).

        Apply on the main thread via :meth:`apply_result` after AsyncRunner completes.

        returns:
            HostInstallIdentityOutcome: The outcome of the work.
                - install_token: The install token.
        raises:
            RuntimeError: If the install token is not created.
        """
        return HostInstallIdentityWork().run()

    def close_core_runtime(self) -> CloseOutcome:
        """
        Stop the ADB server (worker thread). Apply on the main thread via :meth:`apply_result`.

        When no ADB server is active, returns ``CloseOutcome(adb_server=None)`` as a no-op
        without invoking close work. Stop failures inside
        :class:`~core.work.close_work.CloseCoreRuntimeWork` propagate to AsyncRunner.
        """
        if self._adb_server is None:
            logger.warning(
                "ModelEntrypoint: close_core_runtime skipped (no active ADB server)",
            )
            return CloseOutcome(adb_server=None)
        return CloseCoreRuntimeWork(self._adb_server).run()

    def restart_adb_server(self) -> None:
        """
        Restart the ADB server and keep the instance in entrypoint state.
        """
        if self._adb_server is not None:
            self._signal_bus.emit(
                CoreSignal.ADB_SERVER_STOPPED,
                AdbServerStoppedPayload(
                    adb_binary_path=str(self._adb_server.binary.path),
                ),
            )
            self._adb_server.restart()
            logger.info(
                "ModelEntrypoint: ADB server restarted",
                adb_path=str(self._adb_server.binary.path),
            )
            self._signal_bus.emit(
                CoreSignal.ADB_SERVER_STARTED,
                AdbServerStartedPayload(
                    adb_binary_path=str(self._adb_server.binary.path),
                ),
            )
            self._signal_bus.emit(
                CoreSignal.DEVICES_UPDATED,
                DevicesUpdatedPayload(
                    devices=serialize_phone_collection(self.get_known_devices()),
                ),
            )
        else:
            logger.warning(
                "ModelEntrypoint: ADB server restart skipped (not running)",
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
        List devices from a server instance, or from the current entrypoint server when
        ``server`` is omitted (e.g. after startup has been applied on the main thread).
        """
        resolved: AdbServer | None = server if server is not None else self._adb_server
        if resolved is None:
            return []
        return resolved.get_known_devices()

    def reconcile_paired_devices(self, phones: list[Phone]) -> DeviceReconcileResult:
        """
        Reconcile paired devices with a freshly discovered handset list.

        Existing ``Phone`` instances are updated in place when they match by ADB
        connection id or non-empty ``stable_key`` (wireless/USB reconnect).
        Handsets absent from ``phones`` are removed and any linked simulation is
        dropped best-effort.

        Returns:
            Result carrying whether the paired repository or simulations changed
            and any safe old ADB id -> new ADB id rebindings detected during
            collision-resistant identity reconciliation.
        """
        if self._adb_server is None:
            raise AttributeError(
                "ADB server must be initialized before reconciling paired devices"
            )
        paired_devices = self._adb_server.paired_devices
        discovered_phones = _dedupe_discovered_phones(phones)
        paired_by_stable_key = _index_paired_phones_by_stable_key(
            paired_devices
        )  # Create a dictionary of paired devices by stable key
        matched_paired_ids: set[int] = (
            set()
        )  # Set of paired device ids that have been matched
        device_id_rebindings: dict[str, str] = {}
        changed = False

        for discovered in discovered_phones:
            paired = paired_devices.get(discovered.id)
            if (
                paired is None
            ):  # A reconnect can update the ADB id, but stable key remains the same
                stable_key = (discovered.stable_key or "").strip()
                if phone_stable_key_is_collision_resistant(stable_key):
                    paired = paired_by_stable_key.get(stable_key)

            if paired is not None:  # A device has been found, by ADB id or stable key
                matched_paired_ids.add(id(paired))
                if paired_phone_matches_discovery(
                    paired, discovered
                ):  # If no property changed, skip
                    continue
                old_connection_id = paired.id
                if (
                    old_connection_id != discovered.id
                ):  # If the ADB id changed, remove the paired device
                    paired_devices.remove(paired)
                apply_discovered_phone_state(
                    paired, discovered
                )  # Update the paired device with the new properties, if a simulation is bound to the device, it will be updated with the new properties
                if (
                    old_connection_id != discovered.id
                ):  # If the ADB id changed, add the updated paired device back
                    paired_devices.add(paired)
                    device_id_rebindings[old_connection_id] = discovered.id
                changed = (
                    True  # At least one device was updated, UI needs to be refreshed
                )
                continue

            paired_devices.add(
                discovered
            )  # A new device has been found, add it to the paired devices
            matched_paired_ids.add(id(discovered))
            changed = (
                True  # At least one new device was found, UI needs to be refreshed
            )

        for paired in list(paired_devices):
            if (
                id(paired) in matched_paired_ids
            ):  # No operation needed for this device, the device stay as is, updated or newly added
                continue
            paired_devices.remove(
                paired
            )  # Remove the device from the paired devices, it is not in the newly discovered devices
            try:
                self.delete_simulation_for_device(
                    paired.id
                )  # Delete the simulation for the device
            except (
                ValueError
            ):  # The simulation for the device was not found, it was not active
                pass
            changed = True  # At least one device was removed, UI needs to be refreshed

        if changed:
            logger.info(
                "ModelEntrypoint: reconciled paired devices",
                discovered_count=len(discovered_phones),
                paired_count=len(paired_devices),
            )
        return DeviceReconcileResult(
            changed=changed,
            device_id_rebindings=device_id_rebindings,
        )

    def create_simulation(self, device_id: str) -> None:
        """
        Create a new simulation.

        Emits a SIMULATION_CREATED signal.

        Args:
            device_id: The id of the device to create the simulation for.

        Returns:
            None

        Raises:
            AttributeError: If the device is not found.
            ValueError: If the device is not in the repository.
        """
        device: Phone | None = self.get_device(device_id)
        if device is None:
            raise AttributeError(f"Device with id {device_id} not found")
        if self._adb_server is None:
            raise AttributeError(
                "ADB server must be initialized before creating a simulation"
            )
        self._adb_server.set_working_device(device)
        simulation: Simulation | None = self._get_simulation_for_device(device_id)
        if simulation is None:
            simulation = Simulation(device=device)
            self._simulations.add(simulation)
            # Emit the signal for the created simulation
            self._signal_bus.emit(
                CoreSignal.SIMULATION_CREATED,
                SimulationCreatedPayload(
                    simulation_id=simulation.id,
                    device_id=device.id,
                    device_name=device.name,
                ),
            )
        else:
            # Simulation is restored from disk; validate persisted marker metadata.
            logger.info(
                "ModelEntrypoint: reusing existing simulation for device",
                simulation_id=simulation.id,
                device_id=device_id,
            )
            # Validate the simulation marker location, simulation metadata can have been modified by the user
            if simulation.spoofed_location.point_of_interest is not None:
                self.validate_simulation_marker_location(
                    simulation_id=simulation.id,
                    marker_id=simulation.spoofed_location.point_of_interest.id,
                    code_line=simulation.spoofed_location.point_of_interest.line.code,
                    latitude=simulation.spoofed_location.point_of_interest.geometry.y,
                    longitude=simulation.spoofed_location.point_of_interest.geometry.x,
                )
        # Set the last active device id
        self._simulations.last_active_device_id = device_id

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
        if simulation.active == active:
            return
        simulation.active = active
        self._signal_bus.emit(
            CoreSignal.SIMULATION_STATE_CHANGED,
            SimulationStateChangedPayload(
                simulation_id=simulation.id,
                active=simulation.active,
            ),
        )

    def update_simulation(self, id: str, **kwargs: Any) -> None:
        """
        Update a simulation.
        """
        simulation: Simulation | None = self._simulations.get(id)
        if simulation is None:
            raise ValueError(f"Simulation with id {id} not found")
        for key, value in kwargs.items():
            if key not in simulation.__class__.__dataclass_fields__:
                raise ValueError(f"Unknown simulation field: {key}")
            current = getattr(simulation, key)
            # Handle location tuple, controller does not know about custom Location class
            if key in ("real_location", "spoofed_location"):
                if isinstance(value, tuple) and len(value) == 3:
                    lat, lon, poi_raw = value
                    point_of_interest: Milestone | None = None
                    if isinstance(poi_raw, dict):
                        point_of_interest = Milestone.from_payload(poi_raw)
                    elif poi_raw is not None:
                        raise ValueError(
                            f"Invalid point_of_interest in location tuple: {poi_raw!r}"
                        )
                    value = Location(
                        lat=lat,
                        lon=lon,
                        point_of_interest=point_of_interest,
                    )
                else:
                    raise ValueError(f"Invalid location tuple: {value}")
            if current == value:
                continue
            setattr(simulation, key, value)
            # Emit the signal for the changed field
            if key == "active":
                self._signal_bus.emit(
                    CoreSignal.SIMULATION_STATE_CHANGED,
                    SimulationStateChangedPayload(
                        simulation_id=simulation.id,
                        active=simulation.active,
                    ),
                )
            elif key in ("real_location", "spoofed_location"):
                self._signal_bus.emit(
                    CoreSignal.SIMULATION_POSITION_CHANGED,
                    SimulationPositionChangedPayload(
                        simulation_id=simulation.id,
                        lat=value.lat,
                        lon=value.lon,
                        point_of_interest=(
                            value.point_of_interest.to_payload()
                            if value.point_of_interest is not None
                            else None
                        ),
                    ),
                )
            elif key == "map_file":
                if isinstance(value, Path):
                    self._signal_bus.emit(
                        CoreSignal.SIMULATION_MAP_FILE_CHANGED,
                        SimulationMapFileChangedPayload(
                            simulation_id=simulation.id,
                            map_file_path=value,
                        ),
                    )
                else:
                    raise ValueError(f"Invalid map file: {value}")

    def validate_simulation_marker_location(
        self,
        simulation_id: str,
        marker_id: str,
        code_line: str,
        latitude: float,
        longitude: float,
    ) -> None:
        """Validate a map milestone and emit ``SIMULATION_LOCATION_VALIDATED`` on success."""
        simulation = self.get_simulation(simulation_id)
        if simulation is None:
            raise ValueError(f"Simulation with id {simulation_id} not found")

        try:
            validated = Milestone.validate(
                marker_id,
                code_line,
                Point(longitude, latitude),
            )
            self._signal_bus.emit(
                CoreSignal.SIMULATION_LOCATION_VALIDATED,
                SimulationLocationValidatedPayload(
                    simulation_id=simulation_id,
                    lat=validated.geometry.y,
                    lon=validated.geometry.x,
                    point_of_interest=validated.to_payload(),
                ),
            )
        except MilestoneValidationError as error:
            self._signal_bus.emit(
                CoreSignal.SIMULATION_LOCATION_REJECTED,
                SimulationLocationRejectedPayload(
                    simulation_id=simulation_id,
                    id=marker_id,
                    code_line=code_line,
                    lat=latitude,
                    lon=longitude,
                    reason=str(error),
                ),
            )

    def persist_simulation(self, simulation_id: str) -> None:
        """Write one simulation metadata file to disk."""
        simulation = self._simulations.get(simulation_id)
        if simulation is None:
            logger.warning(
                "ModelEntrypoint: persist_simulation skipped (simulation not found)",
                simulation_id=simulation_id,
            )
            return
        self._simulations.write_simulation(simulation)

    def delete_simulation(self, simulation: Simulation) -> None:
        """
        Delete a simulation by id.
        """
        return self._simulations.remove(simulation)

    def persist_simulations(self) -> None:
        """Persist every simulation and the repository index to disk."""
        self._simulations.write_all()

    def _get_simulation_for_device(self, device_id: str) -> Simulation | None:
        """Return the existing simulation for a device when one is already tracked."""
        for simulation in self._simulations:
            device = simulation.device
            if device is not None and device.id == device_id:
                return simulation
        return None

    def delete_simulation_for_device(self, device_id: str) -> None:
        """
        Delete a simulation for a device by id.
        """
        simulation = self._get_simulation_for_device(device_id)
        if simulation is not None:
            simulation_id = simulation.id
            self.delete_simulation(simulation)
            self._signal_bus.emit(
                CoreSignal.SIMULATION_DELETED,
                SimulationDeletedPayload(simulation_id=simulation_id),
            )
            if self._adb_server is not None:
                working_device = self._adb_server.get_working_device()
                if working_device is not None and working_device.id == device_id:
                    self._adb_server.clear_working_device()
            if self._simulations.last_active_device_id == device_id:
                self._simulations.last_active_device_id = None
            return
        raise ValueError(
            f"Simulation for device with id {device_id} not found or working device not cleared"
        )

    @staticmethod
    def render_map(simulation_id: str, application_dir: Path) -> RenderMapOutcome:
        """
        Render the map for a simulation and write HTML under the application dir.

        Process-safe static API: accepts only picklable inputs so controllers can
        submit it through AsyncRunner's ProcessPool without serializing the whole
        ModelEntrypoint instance.

        Blocking; intended for AsyncRunner / worker-process use only.
        Apply on the main thread via :meth:`apply_result` after AsyncRunner completes.

        Args:
            simulation_id: The id of the simulation whose map should be rendered.
            application_dir: Root application data directory.

        Returns:
            RenderMapOutcome: Written HTML path and simulation id.

        Raises:
            RenderMapError: If map rendering or HTML export fails.
        """
        return RenderMapWork(
            simulation_id=simulation_id,
            application_dir=application_dir,
        ).run()

    def get_map_file_for_simulation(self, simulation_id: str) -> Path | None:
        """
        Get the map file for a simulation.
        """
        simulation = self.get_simulation(simulation_id)
        if simulation is None:
            return None
        return simulation.map_file

    def is_map_rendered_for_simulation(self, simulation_id: str) -> bool:
        """
        Check if the map is rendered for a simulation.
        """
        simulation = self.get_simulation(simulation_id)
        if simulation is None:
            return False
        return simulation.map_file is not None and simulation.map_file.exists()

    def apply_result(self, result: CoreRuntimeWorkOutcome) -> None:
        """
        Dispatch worker results to the matching ``apply_main_thread`` helper (Qt main thread).

        Unknown types are logged; callbacks may validate before calling for clearer context.
        """
        applier = _CORE_RUNTIME_RESULT_APPLIERS.get(type(result))
        if applier is None:
            logger.error(
                "ModelEntrypoint.apply_result: unsupported result type",
                result_type=type(result).__name__,
            )
            return
        applier(self, result)

    def apply_failure(self, error: BaseException | object) -> None:
        """
        Dispatch async worker failures to the matching ``apply_failure_main_thread`` helper.

        Accepts a :class:`~controller.runner.JobError` duck-typed object (``origin``,
        ``exception``, ``message``) or a plain :class:`BaseException`. Routing prefers
        the async job ``origin`` so generic exceptions raised inside a specific work
        still reach that work's failure handler.
        """
        origin, exc = _resolve_failure_origin_and_exception(error)
        origin_applier = _CORE_RUNTIME_FAILURE_APPLIERS.get(origin)
        if origin_applier is not None:
            origin_applier(self, exc)
            return
        exception_applier = _resolve_exception_failure_applier(exc)
        if exception_applier is not None:
            exception_applier(self, exc)
            return
        logger.error(
            "ModelEntrypoint.apply_failure: unregistered failure",
            origin=origin or None,
            exception_type=type(exc).__name__,
            message=str(exc),
        )
        CoreRuntimeWork.emit_generic_error(
            self,
            source="ModelEntrypoint",
            message=str(exc),
            error=exc,
        )


def _dedupe_discovered_phones(phones: list[Phone]) -> list[Phone]:
    """Keep the last discovery payload per ADB connection id; skip blank ids."""
    deduped: dict[str, Phone] = {}
    for phone in phones:
        device_id = (phone.id or "").strip()
        if not device_id:
            logger.warning(
                "ModelEntrypoint: skipping discovered phone with empty id",
                phone_repr=repr(phone),
            )
            continue
        deduped[device_id] = phone
    return list(deduped.values())


def _index_paired_phones_by_stable_key(
    paired_devices: PhoneRepository,
) -> dict[str, Phone]:
    """Map non-empty stable keys to currently paired handsets (first wins)."""
    indexed: dict[str, Phone] = {}
    for paired in paired_devices:
        stable_key = (paired.stable_key or "").strip()
        if stable_key and stable_key not in indexed:
            indexed[stable_key] = paired
    return indexed


def _resolve_failure_origin_and_exception(
    error: BaseException | object,
) -> tuple[str, BaseException]:
    """Normalize AsyncRunner ``JobError`` or plain exceptions for failure dispatch."""
    origin = (getattr(error, "origin", None) or "").strip()
    wrapped = getattr(error, "exception", None)
    if isinstance(wrapped, BaseException):
        return origin, wrapped
    if isinstance(error, BaseException):
        return origin, error
    message = (getattr(error, "message", None) or str(error)).strip()
    return origin, RuntimeError(message or "Async worker failure")


def _resolve_exception_failure_applier(
    exc: BaseException,
) -> CoreRuntimeFailureApplier | None:
    """Choose the most specific registered exception failure applier via MRO."""
    for exc_type in type(exc).__mro__:
        if exc_type is BaseException:
            break
        applier = _CORE_RUNTIME_EXCEPTION_FAILURE_APPLIERS.get(exc_type)
        if applier is not None:
            return applier
    return None
