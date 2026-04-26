import platform
from abc import ABC, abstractmethod
from pathlib import Path

from core.adb import AdbBinary, AdbClient, AdbServer
from core.devices import Computer, Phone
from core.pair_device_work import apply_main_thread as apply_pair_device_main_thread
from core.pair_device_work import run as run_pair_device
from core.signals import (
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    DevicesUpdatedPayload,
    InMemoryCoreSignalBus,
    SignalHandler,
)
from core.startup_work import StartupResult, apply_main_thread
from core.startup_work import run as run_startup_work
from logger import logger


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

    @staticmethod
    def _resolve_adb_binary_path() -> Path:
        """
        Resolve the OS-specific ADB binary path shipped with the project.
        """
        src_root: Path = Path(__file__).resolve().parents[1]
        system: str = platform.system().lower()
        platform_folder: str
        binary_name: str
        if system == "darwin":
            platform_folder = "macos"
            binary_name = "adb"
        elif system == "linux":
            platform_folder = "linux"
            binary_name = "adb"
        elif system == "windows":
            platform_folder = "win"
            binary_name = "adb.exe"
        else:
            raise RuntimeError(
                f"Unsupported operating system for ADB startup: {system}"
            )

        adb_path: Path = (
            src_root / "assets" / platform_folder / "platform-tools" / binary_name
        )
        if not adb_path.exists():
            raise FileNotFoundError(
                f"ADB binary not found at expected path: {adb_path}"
            )
        return adb_path

    def startup(self) -> StartupResult:
        """
        Initialize runtime core services at application startup (worker thread).
        """
        return run_startup_work(self)

    def start_adb_server(self) -> AdbServer:
        """
        Start or restart the ADB server and keep the instance in model state.
        """
        try:
            adb_binary: AdbBinary = AdbBinary(path=self._resolve_adb_binary_path())
            adb_server: AdbServer = AdbServer(binary=adb_binary)
            logger.info(
                "CoreRuntimeModel: ADB server started",
                adb_path=str(adb_binary.path),
            )
            return adb_server
        except Exception as error:
            logger.exception(
                "CoreRuntimeModel: failed to start ADB server",
                error=str(error),
            )
            raise RuntimeError("Failed to start ADB server") from error

    def apply_adb_server_startup_result(self, result: StartupResult) -> None:
        """
        Apply startup work completed on a worker (call from the Qt main thread).
        """
        apply_main_thread(self, result)

    def stop_adb_server(self) -> None:
        """
        Stop the ADB server and remove the instance from model state.
        """
        if self._adb_server is not None:
            stopped_binary = self._adb_server.binary
            adb_path = str(stopped_binary.path)
            self._adb_server.stop()
            self._adb_server = None
            self._signal_bus.emit(
                CoreSignal.ADB_SERVER_STOPPED,
                AdbServerStoppedPayload(adb_binary=stopped_binary),
            )
            logger.info(
                "CoreRuntimeModel: ADB server stopped",
                adb_path=adb_path,
            )
        else:
            logger.warning(
                "CoreRuntimeModel: ADB server stop skipped (not running)",
            )

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

    def get_adb_client(self) -> AdbClient:
        """
        Return the ADB client, creating and caching one if startup has not run yet.
        """
        if self._adb_client is None:
            self._adb_client = self.create_adb_client()
        return self._adb_client

    def create_adb_client(self) -> AdbClient:
        """
        Get the ADB client.
        """
        logger.debug("CoreRuntimeModel: creating ADB client")
        adb_binary: AdbBinary = AdbBinary(path=self._resolve_adb_binary_path())
        adb_client: AdbClient = AdbClient(binary=adb_binary)
        return adb_client

    def pair_device(self, ip: str, port: int, association_code: str) -> None:
        """
        Pair a device with the ADB server (synchronous: worker + main-thread apply).

        For UI-initiated pairing off the main thread, prefer submitting ``run`` /
        ``apply_main_thread`` from ``core.pair_device_work`` via AsyncRunner and
        calling ``apply_pair_device_main_thread`` only in the job completion callback.
        """
        apply_pair_device_main_thread(
            self, run_pair_device(self, ip, port, association_code)
        )
