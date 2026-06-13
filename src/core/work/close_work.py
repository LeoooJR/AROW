from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.adb.server import AdbServer
from core.signals import AdbServerStoppedPayload, CoreSignal
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from logger import logger

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint


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
        model_entrypoint: ModelEntrypoint, result: CloseOutcome
    ) -> None:
        """
        Apply the result of the close job to the entrypoint in the main thread.
        """
        from core.entrypoint import ModelEntrypoint as _ModelEntrypoint

        if not isinstance(model_entrypoint, _ModelEntrypoint):
            raise TypeError("apply_main_thread() requires ModelEntrypoint")
        if result.adb_server is None:
            logger.warning(
                "ModelEntrypoint: close apply skipped stop signal (no stopped server)",
            )
            return
        model_entrypoint._adb_server = None
        model_entrypoint._signal_bus.emit(
            CoreSignal.ADB_SERVER_STOPPED,
            AdbServerStoppedPayload(adb_binary=result.adb_server.binary),
        )

    @staticmethod
    def apply_failure_main_thread(
        model_entrypoint: ModelEntrypoint, error: BaseException
    ) -> None:
        from core.entrypoint import ModelEntrypoint as _ModelEntrypoint

        if not isinstance(model_entrypoint, _ModelEntrypoint):
            raise TypeError("apply_failure_main_thread() requires ModelEntrypoint")
        CloseCoreRuntimeWork.emit_generic_error(
            model_entrypoint,
            source="CloseCoreRuntimeWork",
            message=str(error),
            error=error,
        )
