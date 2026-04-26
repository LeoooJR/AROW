"""
Worker / main-thread split for device pairing: ADB I/O on a worker, bus emit on the UI thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.adb import AdbClientException
from core.devices import Phone
from core.signals import (
    CoreSignal,
    DeviceConnectionFailedPayload,
    DeviceConnectionSucceededPayload,
)
from logger import logger

if TYPE_CHECKING:
    from core.models import CoreRuntimeModel


@dataclass(frozen=True, slots=True)
class PairDeviceOutcome:
    """
    Result of ``run`` (worker). Apply on the main thread with ``apply_main_thread`` only.
    """

    success_phone: Phone | None = None
    failure: DeviceConnectionFailedPayload | None = None


def run(
    model: CoreRuntimeModel,
    ip: str,
    port: int,
    association_code: str,
) -> PairDeviceOutcome:
    """
    Pair over ADB (call from a worker thread). Does not touch the core signal bus.
    """
    from core.models import CoreRuntimeModel as _CoreRuntimeModel

    if not isinstance(model, _CoreRuntimeModel):
        raise TypeError("run() requires CoreRuntimeModel")
    adb_client = model.get_adb_client()
    try:
        phone = adb_client.pair(ip, port, association_code)
        return PairDeviceOutcome(success_phone=phone, failure=None)
    except AdbClientException as error:
        error_message: str = str(error)
        logger.warning(
            "CoreRuntimeModel: device pairing failed (first attempt)",
            ip=ip,
            port=port,
            error=error_message,
        )
        if "protocol fault" in error_message.lower():
            try:
                if model._adb_server is not None:
                    model._adb_server.restart()
                else:
                    model.start_adb_server()
                logger.info(
                    "CoreRuntimeModel: ADB server restarted after protocol fault",
                    ip=ip,
                    port=port,
                )
                phone = adb_client.pair(ip, port, association_code)
                return PairDeviceOutcome(success_phone=phone, failure=None)
            except AdbClientException as retry_error:
                logger.warning(
                    "CoreRuntimeModel: pairing retry failed after restart",
                    ip=ip,
                    port=port,
                    error=str(retry_error),
                )
        return PairDeviceOutcome(
            success_phone=None,
            failure=DeviceConnectionFailedPayload(
                ip=ip, port=port, association_code=association_code
            ),
        )


def apply_main_thread(model: CoreRuntimeModel, outcome: PairDeviceOutcome) -> None:
    """
    Emit pairing outcome on the core bus (call from the Qt main thread only).
    """
    from core.models import CoreRuntimeModel as _CoreRuntimeModel

    if not isinstance(model, _CoreRuntimeModel):
        raise TypeError("apply_main_thread() requires CoreRuntimeModel")
    if outcome.success_phone is not None:
        model._signal_bus.emit(
            CoreSignal.DEVICE_CONNECTION_SUCCEEDED,
            DeviceConnectionSucceededPayload(phone=outcome.success_phone),
        )
        return
    if outcome.failure is not None:
        model._signal_bus.emit(
            CoreSignal.DEVICE_CONNECTION_FAILED,
            outcome.failure,
        )
        return
    logger.warning(
        "CoreRuntimeModel: pair device apply skipped (empty outcome)",
    )
