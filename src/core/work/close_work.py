from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.adb.exceptions import AdbServerException
from core.adb.server import AdbServer
from core.signals import AdbServerStoppedPayload, CoreSignal
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from logger import logger

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint


def _stop_adb_server(adb_server: AdbServer) -> bool:
    """
    Stop the ADB server and remove the instance from entrypoint state.
    """
    if adb_server is not None:
        stopped_binary = adb_server.binary
        adb_path = str(stopped_binary.path)
        try:
            adb_server.stop()
        except AdbServerException as e:
            logger.error(
                "ModelEntrypoint: Failed to stop ADB server",
                error=str(e),
            )
            return False
        logger.info(
            "ModelEntrypoint: ADB server stopped",
            adb_path=adb_path,
        )
        return True
    else:
        logger.warning(
            "ModelEntrypoint: ADB server stop skipped (not running)",
        )
        return False


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

        Delegates to :func:`_stop_adb_server`, which calls
        :meth:`~core.adb.server.AdbServer.stop` when a server instance is
        provided. :meth:`apply_main_thread` clears entrypoint server state and
        emits ``ADB_SERVER_STOPPED`` only when stop succeeded.

        Returns:
            CloseOutcome: ``adb_server`` set to the stopped server instance when
            :func:`_stop_adb_server` reports success; ``adb_server=None`` when
            stop was skipped (no server) or :class:`~core.adb.exceptions.AdbServerException`
            was caught and logged.

        Raises:
            None: :class:`~core.adb.exceptions.AdbServerException` from
            :meth:`~core.adb.server.AdbServer.stop` is caught inside
            :func:`_stop_adb_server` and converted to ``adb_server=None``.
            Exception: Any non-:class:`~core.adb.exceptions.AdbServerException`
            raised by the server object or stop path propagates to AsyncRunner.
        """
        if _stop_adb_server(self._adb_server):
            return CloseOutcome(adb_server=self._adb_server)
        else:
            return CloseOutcome(adb_server=None)

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
