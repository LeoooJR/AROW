"""
Paired worker output and main-thread application for core runtime startup.

:class:`StartupCoreRuntimeWork` implements :class:`~core.work.core_runtime_work.CoreRuntimeWork`
so startup matches the project-wide paired worker / apply convention.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from core.adb.adb_mock import (
    DEFAULT_MOCK_ADB_BINARY_PATH,
    MockAdbClient,
    MockAdbServer,
    MockAdbState,
    mock_adb_seed_from_env,
)
from core.adb.binary import AdbBinary
from core.adb.client import AdbClient
from core.adb.server import AdbServer
from core.devices import Phone
from core.signals import (
    AdbServerStartedPayload,
    CoreSignal,
    DevicesUpdatedPayload,
)
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from core.work.refresh_known_devices_work import enrich_phones_with_adb_shell_properties
from logger import logger

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint


def _use_mock_adb_effective(cli_or_model_flag: bool) -> bool:
    """Enable mock ADB from constructor/CLI flag or ``AROW_USE_MOCK_ADB`` env."""
    if cli_or_model_flag:
        return True
    return os.environ.get("AROW_USE_MOCK_ADB", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _resolve_adb_binary_path() -> Path:
    """
    Resolve the OS-specific ADB binary path shipped with the project.
    """
    src_root: Path = Path(__file__).resolve().parents[2]
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
        raise RuntimeError(f"Unsupported operating system for ADB startup: {system}")

    adb_path: Path = (
        src_root / "assets" / platform_folder / "platform-tools" / binary_name
    )
    if not adb_path.exists():
        raise FileNotFoundError(f"ADB binary not found at expected path: {adb_path}")
    return adb_path


def _ensure_adb_binary_executable(adb_path: Path) -> None:
    """
    Verify that the packaged ADB binary is a runnable file.

    Executable permissions are treated as part of package integrity. The app
    intentionally does not chmod or repair the shipped binary at runtime: a
    missing execute bit may indicate packaging drift, corruption, or an
    unexpected file replacement, so startup fails before launching anything.
    """
    if not adb_path.is_file():
        raise FileNotFoundError(f"ADB binary is not a file: {adb_path}")
    if not os.access(adb_path, os.X_OK):
        raise PermissionError(f"ADB binary is not executable: {adb_path}")


def _validate_frozen_adb_binary_version(
    *, expected: AdbBinary, actual: AdbBinary
) -> None:
    """
    Ensure the packaged ADB binary still matches frozen project metadata.
    """
    if actual == expected:
        return
    # The packaged app expects one known ADB binary. A mismatch here may signal
    # replacement, corruption, packaging drift, or execution of an unexpected binary.
    logger.error(
        "startup_work: bundled ADB metadata mismatch",
        expected_version=expected.version,
        expected_build_version=expected.build_version,
        expected_build_number=expected.build_number,
        actual_version=actual.version,
        actual_build_version=actual.build_version,
        actual_build_number=actual.build_number,
        actual_path=str(actual.path),
    )
    raise RuntimeError("Bundled ADB binary version does not match frozen metadata")


def _start_adb_server() -> AdbServer:
    """
    Instantiate an ADB server bound to the shipped binary (blocking I/O on process start).

    Does not update :class:`~core.entrypoint.ModelEntrypoint` state; the startup job
    ``apply_main_thread`` path assigns ``_adb_server`` on the Qt main thread.
    """
    try:
        adb_path = _resolve_adb_binary_path()
        _ensure_adb_binary_executable(adb_path)
        adb_binary: AdbBinary = AdbBinary(path=adb_path)
        actual_binary: AdbBinary = AdbServer.get_binary_version(adb_binary)
        _validate_frozen_adb_binary_version(
            expected=AdbBinary(path=adb_path), actual=actual_binary
        )
        adb_server: AdbServer = AdbServer(binary=adb_binary)
        logger.info(
            "startup_work: ADB server started",
            adb_path=str(adb_binary.path),
            adb_version=actual_binary.version,
            adb_build_version=actual_binary.build_version,
        )
        return adb_server
    except Exception as error:
        logger.exception(
            "startup_work: failed to start ADB server",
            error=str(error),
        )
        raise RuntimeError("Failed to start ADB server") from error


def _create_adb_client() -> AdbClient:
    """Build an :class:`~core.adb.client.AdbClient` using the project's ADB binary path."""
    logger.debug("startup_work: creating ADB client")
    adb_binary: AdbBinary = AdbBinary(path=_resolve_adb_binary_path())
    return AdbClient(binary=adb_binary)


@dataclass(frozen=True, slots=True)
class StartupOutcome(CoreRuntimeWorkOutcome):
    """Outcome of the async startup job (build on a worker, apply on the main thread)."""

    adb_server: AdbServer | None = field(
        default=None, metadata={"description": "The ADB server instance"}
    )
    adb_client: AdbClient | None = field(
        default=None, metadata={"description": "The ADB client instance"}
    )
    devices: list[Phone] = field(
        default_factory=list, metadata={"description": "The known devices"}
    )


class StartupCoreRuntimeWork(CoreRuntimeWork[StartupOutcome]):
    """
    Worker job: start ADB server/client, list devices, enrich phones from ADB shell properties.

    Apply path owns model server/client fields and emits on the core bus.
    """

    def __init__(self, use_mock_adb: bool = False) -> None:
        self._use_mock_adb: bool = use_mock_adb

    def run(self) -> StartupOutcome:
        """Execute startup steps that may block (AsyncRunner worker thread)."""
        use_mock = _use_mock_adb_effective(self._use_mock_adb)
        adb_server: AdbServer
        adb_client: AdbClient
        if use_mock:
            seed = mock_adb_seed_from_env()
            adb_state = MockAdbState(seed=seed)
            adb_binary = AdbBinary(path=DEFAULT_MOCK_ADB_BINARY_PATH)
            adb_server = MockAdbServer(state=adb_state, binary=adb_binary)
            adb_client = MockAdbClient(state=adb_state, binary=adb_binary)
            logger.info(
                "startup_work: mock ADB server/client initialized",
                adb_path=str(adb_binary.path),
                mock_seed=seed,
            )
        else:
            adb_server = _start_adb_server()
            adb_client = _create_adb_client()
        devices = list(adb_server.paired_devices)
        enrich_phones_with_adb_shell_properties(adb_client, devices)
        return StartupOutcome(
            adb_server=adb_server,
            adb_client=adb_client,
            devices=devices,
        )

    @staticmethod
    def apply_main_thread(
        model_entrypoint: ModelEntrypoint, result: StartupOutcome
    ) -> None:
        """
        Own server/client state and emit on the bus (Qt main thread; AsyncRunner
        completion runs there).
        """
        from core.entrypoint import ModelEntrypoint as _ModelEntrypoint

        if not isinstance(model_entrypoint, _ModelEntrypoint):
            raise TypeError("apply_main_thread() requires ModelEntrypoint")
        if result.adb_server is not None:
            model_entrypoint._adb_server = result.adb_server
        if result.adb_client is not None:
            model_entrypoint._adb_client = result.adb_client
        if result.adb_server is not None:
            model_entrypoint._signal_bus.emit(
                CoreSignal.ADB_SERVER_STARTED,
                AdbServerStartedPayload(adb_binary=result.adb_server.binary),
            )
            model_entrypoint._signal_bus.emit(
                CoreSignal.DEVICES_UPDATED,
                DevicesUpdatedPayload(devices=result.devices),
            )
