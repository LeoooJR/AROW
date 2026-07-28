"""
Paired worker output and main-thread application for core runtime startup.

:class:`StartupCoreRuntimeWork` implements :class:`~core.work.core_runtime_work.CoreRuntimeWork`
so startup matches the project-wide paired worker / apply convention.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

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
from core.devices.phone import Phone, serialize_phone_collection
from core.entrypoint_protocol import CoreSignalEmitter, StartupRuntimeEntrypoint
from core.exceptions import CoreException
from core.signals import (
    AdbServerStartedPayload,
    CoreSignals,
    DevicesUpdatedPayload,
)
from core.simulation import PersistedSimulationState, Simulation, SimulationDiskStore
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from core.work.helper import preflight
from core.work.refresh_known_devices_work import enrich_phones_with_adb_shell_properties
from logger import logger


def _use_mock_adb_effective(cli_or_model_flag: bool) -> bool:
    """Enable mock ADB from constructor/CLI flag or ``AROW_USE_MOCK_ADB`` env."""
    if cli_or_model_flag:
        return True
    return os.environ.get("AROW_USE_MOCK_ADB", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


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
        "Bundled ADB metadata does not match the expected release",
        expected_version=expected.version,
        expected_build_version=expected.build_version,
        expected_build_number=expected.build_number,
        actual_version=actual.version,
        actual_build_version=actual.build_version,
        actual_build_number=actual.build_number,
        actual_path=str(actual.path),
    )
    raise RuntimeError("Bundled ADB binary version does not match frozen metadata")


def _start_adb_server(adb_binary_path: Path) -> AdbServer:
    """
    Instantiate an ADB server bound to the shipped binary (blocking I/O on process start).

    Does not update :class:`~core.entrypoint.ModelEntrypoint` state; the startup job
    ``apply_main_thread`` path assigns ``_adb_server`` on the Qt main thread.
    """
    try:
        if not adb_binary_path.exists():
            raise FileNotFoundError(
                f"ADB binary not found at expected path: {adb_binary_path}"
            )
        _ensure_adb_binary_executable(adb_binary_path)
        adb_binary: AdbBinary = AdbBinary(path=adb_binary_path)
        actual_binary: AdbBinary = AdbServer.get_binary_version(adb_binary)
        _validate_frozen_adb_binary_version(
            expected=AdbBinary(path=adb_binary_path), actual=actual_binary
        )
        adb_server: AdbServer = AdbServer(binary=adb_binary)
        logger.info(
            "ADB server started",
            adb_path=str(adb_binary.path),
            adb_version=actual_binary.version,
            adb_build_version=actual_binary.build_version,
        )
        return adb_server
    except Exception as error:
        logger.exception(
            "ADB server startup failed",
            error=str(error),
        )
        raise


def _create_adb_client(adb_binary_path: Path) -> AdbClient:
    """Build an :class:`~core.adb.client.AdbClient` using the project's ADB binary path."""
    logger.debug("ADB client creation started")
    adb_binary: AdbBinary = AdbBinary(path=adb_binary_path)
    return AdbClient(binary=adb_binary)


class StartupCoreRuntimeError(CoreException):
    """Startup core runtime work failed."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


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
    simulations: list[Simulation] = field(
        default_factory=list,
        metadata={"description": "Persisted simulations bound to paired devices"},
    )
    last_active_device_id: str | None = field(
        default=None,
        metadata={"description": "Persisted last selected device id from index"},
    )


class StartupCoreRuntimeWork(CoreRuntimeWork[StartupOutcome]):
    """
    Worker job: start ADB server/client, list devices, enrich phones from ADB shell properties.

    Apply path owns model server/client fields and emits on the core bus.
    """

    def __init__(
        self,
        use_mock_adb: bool = False,
        *,
        adb_binary_path: Path,
        simulations_dir: Path,
    ) -> None:
        self._use_mock_adb: bool = use_mock_adb
        self._adb_binary_path = adb_binary_path
        self._simulations_dir = simulations_dir

    @preflight()
    def run(self) -> StartupOutcome:
        """
        Start ADB server and client, snapshot paired devices, and enrich phones
        from ADB shell properties (AsyncRunner worker thread).

        Chooses mock vs real ADB from the constructor flag or ``AROW_USE_MOCK_ADB``.
        Real path resolves the packaged binary, starts :class:`~core.adb.server.AdbServer`,
        and builds :class:`~core.adb.client.AdbClient`. Mock path uses
        :class:`~core.adb.adb_mock.MockAdbServer` / :class:`~core.adb.adb_mock.MockAdbClient`.
        Shell enrichment is best-effort: ADB shell read failures are logged and
        swallowed inside the client, so this method still returns an outcome.

        Returns:
            StartupOutcome: ``adb_server``, ``adb_client``, and ``devices`` for
            :meth:`apply_main_thread` to assign on the model entrypoint and emit
            ``ADB_SERVER_STARTED`` / ``DEVICES_UPDATED``.

        Raises:
            RuntimeError: Real ADB startup failed in :func:`_start_adb_server`
            (unsupported OS, missing or non-executable binary, frozen metadata
            mismatch, version preflight failure, or server start failure). Any
            underlying exception is logged and chained as
            ``"Failed to start ADB server"``.
            RuntimeError: Unsupported OS or frozen-metadata mismatch during
            :func:`_create_adb_client` binary resolution (not wrapped by
            :func:`_start_adb_server`).
            FileNotFoundError: Packaged ADB binary missing or not a file during
            client creation after server startup succeeded.
            AdbServerException: Mock server construction or :meth:`~core.adb.server.AdbServer.start`
            failed when mock ADB is enabled (uncaught by the real-path wrapper).
            Exception: Any unexpected failure from mock state construction,
            enrichment helpers, or outcome construction propagates to AsyncRunner.
        """
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
                "Mock ADB runtime initialized",
                adb_path=str(adb_binary.path),
                mock_seed=seed,
            )
        else:
            adb_server = _start_adb_server(self._adb_binary_path)
            adb_client = _create_adb_client(self._adb_binary_path)
        devices = list(adb_server.paired_devices)
        enrich_phones_with_adb_shell_properties(adb_client, devices)
        persisted_state: PersistedSimulationState = SimulationDiskStore(
            self._simulations_dir
        ).load_for_devices(adb_server.paired_devices)
        return StartupOutcome(
            adb_server=adb_server,
            adb_client=adb_client,
            devices=devices,
            simulations=persisted_state.simulations,
            last_active_device_id=persisted_state.last_active_device_id,
        )

    @staticmethod
    def apply_main_thread(
        model_entrypoint: CoreSignalEmitter, result: StartupOutcome
    ) -> None:
        """
        Own server/client state and emit on the bus (Qt main thread; AsyncRunner
        completion runs there).
        """
        startup_entrypoint = cast(StartupRuntimeEntrypoint, model_entrypoint)
        if result.adb_server is not None:
            startup_entrypoint.adb_server = result.adb_server
        if result.adb_client is not None:
            startup_entrypoint.adb_client = result.adb_client
        for simulation in result.simulations:
            startup_entrypoint.restore_persisted_simulation(simulation)
        if result.adb_server is not None:
            startup_entrypoint.emit_core_signal(
                CoreSignals.ADB_SERVER_STARTED,
                AdbServerStartedPayload(
                    adb_binary_path=str(result.adb_server.binary.path),
                ),
            )
            startup_entrypoint.emit_core_signal(
                CoreSignals.DEVICES_UPDATED,
                DevicesUpdatedPayload(
                    devices=serialize_phone_collection(result.devices),
                ),
            )
        startup_entrypoint.sync_last_active_device_id(result.last_active_device_id)
        if result.last_active_device_id is not None:
            paired_device = (
                result.adb_server.paired_devices.get(result.last_active_device_id)
                if result.adb_server is not None
                else None
            )
            if paired_device is not None and paired_device.state == "device":
                try:
                    startup_entrypoint.create_simulation(result.last_active_device_id)
                except (AttributeError, ValueError) as error:
                    logger.warning(
                        "Last active device could not be restored",
                        device_id=result.last_active_device_id,
                        error=str(error),
                    )

    @staticmethod
    def apply_failure_main_thread(
        model_entrypoint: CoreSignalEmitter, error: BaseException
    ) -> None:
        StartupCoreRuntimeWork.emit_generic_error(
            model_entrypoint,
            source="StartupCoreRuntimeWork",
            message=str(error),
            error=error,
        )
