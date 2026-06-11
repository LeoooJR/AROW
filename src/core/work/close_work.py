from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.adb.exceptions import AdbServerException
from core.adb.server import AdbServer
from core.signals import AdbServerStoppedPayload, CoreSignal
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from logger import logger

if TYPE_CHECKING:
    from core.models import CoreRuntimeModel


def _stop_adb_server(adb_server: AdbServer) -> bool:
    """
    Stop the ADB server and remove the instance from model state.
    """
    if adb_server is not None:
        stopped_binary = adb_server.binary
        adb_path = str(stopped_binary.path)
        try:
            adb_server.stop()
        except AdbServerException as e:
            logger.error(
                "CoreRuntimeModel: Failed to stop ADB server",
                error=str(e),
            )
            return False
        logger.info(
            "CoreRuntimeModel: ADB server stopped",
            adb_path=adb_path,
        )
        return True
    else:
        logger.warning(
            "CoreRuntimeModel: ADB server stop skipped (not running)",
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
        Execute close steps that may block (AsyncRunner worker thread).
        """
        if _stop_adb_server(self._adb_server):
            return CloseOutcome(adb_server=self._adb_server)
        else:
            return CloseOutcome(adb_server=None)

    @staticmethod
    def apply_main_thread(model: CoreRuntimeModel, result: CloseOutcome) -> None:
        """
        Apply the result of the close job to the model in the main thread.
        """
        from core.models import CoreRuntimeModel as _CoreRuntimeModel

        if not isinstance(model, _CoreRuntimeModel):
            raise TypeError("apply_main_thread() requires CoreRuntimeModel")
        if result.adb_server is None:
            logger.warning(
                "CoreRuntimeModel: close apply skipped stop signal (no stopped server)",
            )
            return
        model._adb_server = None
        model._signal_bus.emit(
            CoreSignal.ADB_SERVER_STOPPED,
            AdbServerStoppedPayload(adb_binary=result.adb_server.binary),
        )
