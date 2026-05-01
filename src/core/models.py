from abc import ABC
from typing import Callable

from core.adb import AdbClient, AdbServer
from core.authentificate_device_work import (
    AuthenticateDeviceWork,
    AuthentificateDeviceOutcome,
)
from core.device_serial_work import refresh_known_devices_with_serial
from core.devices import Computer, Phone
from core.signals import (
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    DevicesUpdatedPayload,
    InMemoryCoreSignalBus,
    SignalHandler,
)
from core.startup_work import (
    StartupCoreRuntimeWork,
    StartupResult,
    _create_adb_client,
)
from logger import logger

# Main-thread appliers keyed by exact worker result type (AsyncRunner completion).
CoreRuntimeResultApplier = Callable[["CoreRuntimeModel", object], None]

_CORE_RUNTIME_RESULT_APPLIERS: dict[type[object], CoreRuntimeResultApplier] = {
    StartupResult: StartupCoreRuntimeWork.apply_main_thread,
    AuthentificateDeviceOutcome: AuthenticateDeviceWork.apply_main_thread,
}


def register_core_runtime_result_applier(
    result_type: type[object],
    applier: CoreRuntimeResultApplier,
) -> None:
    """Register or replace the main-thread applier for ``result_type`` outcomes."""
    _CORE_RUNTIME_RESULT_APPLIERS[result_type] = applier


class Model(ABC):

    def __init__(self):

        self._signal_bus: InMemoryCoreSignalBus = InMemoryCoreSignalBus()

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

    def __init__(self) -> None:
        super().__init__()
        self._host: Computer = Computer(id="host-1")
        self._adb_server: AdbServer | None = None
        self._adb_client: AdbClient | None = None

    @property
    def host(self) -> Computer:
        """Return the host device."""
        return self._host

    @property
    def adb_server(self) -> AdbServer | None:
        """Return the active ADB server instance if available."""
        return self._adb_server

    def startup(self) -> StartupResult:
        """
        Initialize runtime core services at application startup (worker thread).
        """
        return StartupCoreRuntimeWork().run()

    def authentificate_device(
        self, ip: str, port: int, association_code: str
    ) -> AuthentificateDeviceOutcome:
        """
        Pair the device over ADB (worker thread). Does not emit on the core bus;
        controllers apply outcomes on the main thread after AsyncRunner completes.
        """
        return AuthenticateDeviceWork(
            adb_server=self._adb_server,
            adb_client=self._adb_client,
            ip=ip,
            port=port,
            association_code=association_code,
        ).run()

    def refresh_known_devices(self) -> list[Phone]:
        """
        List devices from the bound server and enrich ``ro.serialno`` via ADB.
        Blocking; intended for AsyncRunner / worker-thread use only.
        """
        return refresh_known_devices_with_serial(self._adb_server, self._adb_client)

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
        if self._adb_server is None:
            return None
        return self._adb_server.paired_devices.get(device_id)

    def get_known_devices(self, server: AdbServer | None = None) -> list[Phone]:
        """
        List devices from a server instance, or from the current model server when
        ``server`` is omitted (e.g. after startup has been applied on the main thread).
        """
        resolved: AdbServer | None = server if server is not None else self._adb_server
        if resolved is None:
            return []
        return resolved.get_known_devices()

    def apply_result(self, result: object) -> None:
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
