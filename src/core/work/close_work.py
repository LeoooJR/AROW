from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from core.adb.server import AdbServer
from core.entrypoint_protocol import AdbRuntimeEntrypoint, CoreSignalEmitter
from core.exceptions import CoreException
from core.signals import AdbServerStoppedPayload, CoreSignals
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from core.work.helper import preflight
from logger import logger


class CloseCoreRuntimeError(CoreException):
    """Close core runtime work failed."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class CloseOutcome(CoreRuntimeWorkOutcome):
    """Outcome of the close job."""

    adb_server: AdbServer | None = None


class CloseCoreRuntimeWork(CoreRuntimeWork[CloseOutcome]):
    """
    Worker job: close the core runtime.
    """

    def __init__(self, adb_server: AdbServer) -> None:
        self._adb_server = adb_server

    @preflight(
        check_server_started=True,
        error_to_raise=lambda self: CloseCoreRuntimeError(
            "ADB server must be running before close work can stop it"
        ),
    )
    def run(self) -> CloseOutcome:
        """
        Stop the bound ADB server on a worker thread (AsyncRunner).

        Calls :meth:`~core.adb.server.AdbServer.stop` on the server instance bound at
        job construction. :meth:`apply_main_thread` clears entrypoint server state and
        emits ``ADB_SERVER_STOPPED`` when stop succeeds.

        Returns:
            CloseOutcome: ``adb_server`` set to the stopped server instance.

        Raises:
            AdbServerException: Stop command failed after subprocess retries.
            Exception: Any unexpected failure from the server stop path propagates to
            AsyncRunner.
        """
        stopped_binary = self._adb_server.binary
        adb_path = str(stopped_binary.path)
        self._adb_server.stop()
        logger.info(
            "ModelEntrypoint: ADB server stopped",
            adb_path=adb_path,
        )
        return CloseOutcome(adb_server=self._adb_server)

    @staticmethod
    def apply_main_thread(
        model_entrypoint: CoreSignalEmitter, result: CloseOutcome
    ) -> None:
        """
        Apply the result of the close job to the entrypoint in the main thread.
        """
        if result.adb_server is None:
            logger.warning(
                "ModelEntrypoint: close apply skipped stop signal (no stopped server)",
            )
            return
        adb_entrypoint = cast(AdbRuntimeEntrypoint, model_entrypoint)
        adb_entrypoint.adb_server = None
        adb_entrypoint.adb_client = None
        adb_entrypoint.emit_core_signal(
            CoreSignals.ADB_SERVER_STOPPED,
            AdbServerStoppedPayload(
                adb_binary_path=str(result.adb_server.binary.path),
            ),
        )

    @staticmethod
    def apply_failure_main_thread(
        model_entrypoint: CoreSignalEmitter, error: BaseException
    ) -> None:
        CloseCoreRuntimeWork.emit_generic_error(
            model_entrypoint,
            source="CloseCoreRuntimeWork",
            message=str(error),
            error=error,
        )
