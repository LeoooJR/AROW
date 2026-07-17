from abc import ABC
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Callable, Literal, Mapping, Tuple, TypeVar

from core.adb.client import AdbClient
from core.adb.server import AdbServer
from core.application_paths import (
    default_activity_log_file_path,
    get_or_create_application_dir,
    get_or_create_config_dir,
)
from core.devices.computer import Computer
from core.devices.phone import (
    Phone,
    PhoneRepository,
    apply_discovered_phone_state,
    serialize_phone_collection,
)
from core.devices.stable_key import StableKey
from core.signal_bus import InMemoryCoreSignalBus
from core.signals import (
    ActivityLogFileUpdatedPayload,
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    CoreSignals,
    DevicesUpdatedPayload,
    HostComputerIdentityPayload,
    SimulationLocationValidatedPayload,
)
from core.simulation import Simulation
from core.simulation_service import SimulationService
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
from core.work.validate_simulation_marker_location_work import (
    ValidateSimulationMarkerLocationOutcome,
    ValidateSimulationMarkerLocationWork,
)
from core.work.works_repository import CORE_RUNTIME_WORKS
from logger import logger

PayloadT = TypeVar("PayloadT")

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

    @property
    def signal_bus(self) -> InMemoryCoreSignalBus:
        """Return the core domain signal bus."""
        return self._signal_bus

    def emit_core_signal(
        self,
        signal: CoreSignal[PayloadT],
        payload: PayloadT,
    ) -> None:
        """Publish one typed payload on the core signal bus."""
        self.signal_bus.emit(signal, payload)

    @cached_property
    def config_dir(self) -> Path:
        return get_or_create_config_dir()

    @cached_property
    def application_dir(self) -> Path:
        return get_or_create_application_dir()


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
        self._simulation_service = SimulationService(
            self,
            save_dir=self.application_dir / "simulations",
        )

    @property
    def host(self) -> Computer:
        """Return the host device."""
        return self._host

    @property
    def adb_server(self) -> AdbServer | None:
        """Return the active ADB server instance if available."""
        return self._adb_server

    @adb_server.setter
    def adb_server(self, value: AdbServer | None) -> None:
        """Bind or clear the active ADB server instance."""
        self._adb_server = value

    @property
    def adb_client(self) -> AdbClient | None:
        """Return the active ADB client instance if available."""
        return self._adb_client

    @adb_client.setter
    def adb_client(self, value: AdbClient | None) -> None:
        """Bind or clear the active ADB client instance."""
        self._adb_client = value

    def register_paired_device(self, phone: Phone) -> None:
        """Add one paired phone to the active ADB server repository."""
        if self._adb_server is None:
            return
        self._adb_server.paired_devices.add(phone)

    def restore_persisted_simulation(self, simulation: Simulation) -> None:
        """Restore one persisted simulation into the in-memory repository."""
        self._simulation_service.restore_persisted_simulation(simulation)

    def sync_last_active_device_id(self, device_id: str | None) -> None:
        """Update the persisted last-active device selection."""
        self._simulation_service.sync_last_active_device_id(device_id)

    def set_host_identity(self, stable_key: str) -> None:
        """Apply persisted install identity to the host descriptor and emit."""
        self._host.descriptor.stable_key = stable_key
        self.emit_core_signal(
            CoreSignals.HOST_COMPUTER_IDENTITY_UPDATED,
            HostComputerIdentityPayload(stable_key=stable_key),
        )

    @property
    def activity_log_file(self) -> Path | None:
        """Return the current app-wide activity log path, creating a default when unset."""
        return self._resolve_activity_log_file()

    @activity_log_file.setter
    def activity_log_file(self, value: Path) -> None:
        """Set the current app-wide activity log path."""
        self._activity_log_file = value
        self.emit_core_signal(
            CoreSignals.ACTIVITY_LOG_FILE_UPDATED,
            ActivityLogFileUpdatedPayload(path=value),
        )

    def _resolve_activity_log_file(self) -> Path:
        """Resolve the current app-wide activity log path, creating a default when unset."""
        if self._activity_log_file is None:
            self._activity_log_file = default_activity_log_file_path(
                self.application_dir
            )
            self.emit_core_signal(
                CoreSignals.ACTIVITY_LOG_FILE_UPDATED,
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
        if not self._host.network_available:
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
                parsed_key = StableKey.from_value(stable_key)
                if parsed_key is not None and parsed_key.is_collision_resistant():
                    paired = paired_by_stable_key.get(stable_key)

            if paired is not None:  # A device has been found, by ADB id or stable key
                matched_paired_ids.add(id(paired))
                if (
                    paired.id == discovered.id
                    and paired.state == discovered.state
                    and paired == discovered
                ):
                    # If no property changed, skip.
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
            self.delete_simulation_for_device(
                paired.id
            )  # Delete the simulation for the device (emits skipped when absent)
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
        """Create a new simulation or restore an existing one for a paired device."""
        self._simulation_service.create_simulation(device_id)

    def get_simulation(self, id: str) -> Simulation | None:
        """Get a simulation by id."""
        return self._simulation_service.get_simulation(id)

    def is_simulation_active(self, id: str) -> bool:
        """Check if a simulation is active."""
        return self._simulation_service.is_simulation_active(id)

    def set_simulation_active(self, id: str, active: bool) -> None:
        """Set a simulation active or inactive."""
        self._simulation_service.set_simulation_active(id, active)

    def set_simulation_real_location(
        self, simulation_id: str, lat: float, lon: float
    ) -> None:
        """Set the simulation real device location and emit position changed."""
        self._simulation_service.set_simulation_real_location(simulation_id, lat, lon)

    def set_simulation_spoofed_location(
        self,
        simulation_id: str,
        lat: float,
        lon: float,
        marker: SimulationLocationValidatedPayload | None = None,
    ) -> None:
        """Set the simulation spoofed location and emit position changed."""
        self._simulation_service.set_simulation_spoofed_location(
            simulation_id,
            lat,
            lon,
            marker,
        )

    def set_simulation_map_file(self, simulation_id: str, map_file: Path) -> None:
        """Set the simulation map file path and emit map-file changed."""
        self._simulation_service.set_simulation_map_file(simulation_id, map_file)

    def validate_simulation_marker_location(
        self,
        simulation_id: str,
        km: int,
        line_code: str,
        line_troncon: int,
        latitude: float,
        longitude: float,
    ) -> ValidateSimulationMarkerLocationOutcome:
        """Validate a map milestone (worker thread). Apply via :meth:`apply_result`."""
        simulation = self.get_simulation(simulation_id)
        if simulation is None:
            raise ValueError(f"Simulation with id {simulation_id} not found")

        return ValidateSimulationMarkerLocationWork(
            simulation_id=simulation_id,
            km=km,
            line_code=line_code,
            line_troncon=line_troncon,
            latitude=latitude,
            longitude=longitude,
        ).run()

    def persist_simulation(self, simulation_id: str) -> None:
        """Write one simulation metadata file to disk."""
        self._simulation_service.persist_simulation(simulation_id)

    def delete_simulation(self, simulation: Simulation) -> None:
        """Delete a simulation by id."""
        self._simulation_service.delete_simulation(simulation)

    def persist_simulations(self) -> None:
        """Persist every simulation and the repository index to disk."""
        self._simulation_service.persist_simulations()

    def _get_simulation_for_device(self, device_id: str) -> Simulation | None:
        """Return the existing simulation for a device when one is already tracked."""
        return self._simulation_service._get_simulation_for_device(device_id)

    def delete_simulation_for_device(self, device_id: str) -> None:
        """Delete a simulation for a device by id."""
        self._simulation_service.delete_simulation_for_device(device_id)

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
