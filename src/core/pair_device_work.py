"""
Worker / main-thread split for device pairing: ADB I/O on a worker, bus emit on the UI thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.adb import AdbClient, AdbClientException
from core.devices import Phone, apply_phone_ro_serial_enrichment
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

    ``paired_ro_serialno`` is raw stdout from ``adb shell getprop ro.serialno`` on the
    worker; ``apply_main_thread`` applies ``hardware_serial`` / ``stable_key`` there.
    """

    success_phone: Phone | None = None
    failure: DeviceConnectionFailedPayload | None = None
    ro_serialno: str = ""


def _ro_serial_after_pair(adb_client: AdbClient, phone: Phone | None) -> str:
    """Read ``ro.serialno`` on the worker when the handset is usable for shell I/O."""
    if phone is None:
        return ""
    state = (phone.descriptor.state or "").strip().casefold()
    if state != "device":
        return ""
    return adb_client.get_ro_serialno(phone)


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
        ro_serial = _ro_serial_after_pair(adb_client, phone)
        return PairDeviceOutcome(
            success_phone=phone, failure=None, ro_serialno=ro_serial
        )
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
                ro_serial = _ro_serial_after_pair(adb_client, phone)
                return PairDeviceOutcome(
                    success_phone=phone,
                    failure=None,
                    ro_serialno=ro_serial,
                )
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
        apply_phone_ro_serial_enrichment(
            outcome.success_phone,
            outcome.ro_serialno,
        )
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
