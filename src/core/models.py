import platform
from abc import ABC, abstractmethod
from pathlib import Path

from core.adb import AdbBinary, AdbClient, AdbClientException, AdbServer
from core.devices import Computer, Phone
from core.signals import (
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    DeviceConnectionFailedPayload,
    DeviceConnectionSucceededPayload,
    DevicesUpdatedPayload,
    InMemoryCoreSignalBus,
    SignalHandler,
)
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

    def startup(self) -> None:
        """
        Initialize runtime core services at application startup.
        """
        self.start_adb_server()
        self.get_adb_client()

    def start_adb_server(self) -> None:
        """
        Start or restart the ADB server and keep the instance in model state.
        """
        try:
            adb_binary: AdbBinary = AdbBinary(path=self._resolve_adb_binary_path())
            self._adb_server: AdbServer = AdbServer(binary=adb_binary)
            logger.info(
                "CoreRuntimeModel: ADB server started",
                adb_path=str(adb_binary.path),
            )
            self._signal_bus.emit(
                CoreSignal.ADB_SERVER_STARTED,
                AdbServerStartedPayload(adb_binary=adb_binary),
            )
            self._signal_bus.emit(
                CoreSignal.DEVICES_UPDATED,
                DevicesUpdatedPayload(devices=self.get_known_devices()),
            )
        except Exception as error:
            self._adb_server = None
            logger.exception(
                "CoreRuntimeModel: failed to start ADB server",
                error=str(error),
            )

    def stop_adb_server(self) -> None:
        """
        Stop the ADB server and remove the instance from model state.
        """
        if self._adb_server is not None:
            self._adb_server.stop()
            self._adb_server = None
            self._signal_bus.emit(
                CoreSignal.ADB_SERVER_STOPPED,
                AdbServerStoppedPayload(adb_binary=self._adb_server.binary),
            )
            logger.info(
                "CoreRuntimeModel: ADB server stopped",
                adb_path=str(self._adb_server.binary.path),
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
        return self._adb_server.paired_devices.get(device_id)

    def get_known_devices(self) -> list[Phone]:
        """
        Get the known devices from the ADB server.
        """
        return self._adb_server.get_known_devices()

    def get_adb_client(self) -> AdbClient:
        """
        Get the ADB client.
        """
        if self._adb_client is None:
            logger.debug("CoreRuntimeModel: creating ADB client")
            adb_binary: AdbBinary = AdbBinary(path=self._resolve_adb_binary_path())
            self._adb_client = AdbClient(binary=adb_binary)
        return self._adb_client

    def pair_device(self, ip: str, port: int, association_code: str) -> None:
        """
        Pair a device with the ADB server.
        """
        adb_client: AdbClient = self.get_adb_client()
        try:
            phone = adb_client.pair(ip, port, association_code)
            self._signal_bus.emit(
                CoreSignal.DEVICE_CONNECTION_SUCCEEDED,
                DeviceConnectionSucceededPayload(phone=phone),
            )
            return
        except AdbClientException as error:
            error_message: str = str(error)
            logger.warning(
                "CoreRuntimeModel: device pairing failed (first attempt)",
                ip=ip,
                port=port,
                error=error_message,
            )
            # ADB can return protocol-fault errors when the daemon is in a stale state.
            # Restarting the daemon and retrying once reproduces the manual workaround.
            if "protocol fault" in error_message.lower():
                try:
                    if self._adb_server is not None:
                        self._adb_server.restart()
                    else:
                        self.start_adb_server()
                    logger.info(
                        "CoreRuntimeModel: ADB server restarted after protocol fault",
                        ip=ip,
                        port=port,
                    )
                    phone = adb_client.pair(ip, port, association_code)
                    self._signal_bus.emit(
                        CoreSignal.DEVICE_CONNECTION_SUCCEEDED,
                        DeviceConnectionSucceededPayload(phone=phone),
                    )
                    return
                except AdbClientException as retry_error:
                    logger.warning(
                        "CoreRuntimeModel: pairing retry failed after restart",
                        ip=ip,
                        port=port,
                        error=str(retry_error),
                    )
            self._signal_bus.emit(
                CoreSignal.DEVICE_CONNECTION_FAILED,
                DeviceConnectionFailedPayload(
                    ip=ip, port=port, association_code=association_code
                ),
            )
