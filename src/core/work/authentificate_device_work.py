"""
Worker / main-thread split for device pairing: ADB I/O on a worker, bus emit on the UI thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.adb import AdbClient, AdbClientException, AdbServer, AdbServerException
from core.devices import Phone
from core.signals import (
    CoreSignal,
    DeviceAuthentificationFailedPayload,
    DeviceAuthentificationSucceededPayload,
)
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from core.work.refresh_known_devices_work import enrich_phones_with_adb_shell_properties
from logger import logger

if TYPE_CHECKING:
    from core.models import CoreRuntimeModel


@dataclass(frozen=True, slots=True)
class AuthentificateDeviceOutcome(CoreRuntimeWorkOutcome):
    """
    Result of :meth:`AuthenticateDeviceWork.run` (worker).

    On success, ``run`` already applies ``ro.serialno`` enrichment to ``success_phone``
    (shared object); :meth:`AuthenticateDeviceWork.apply_main_thread` only emits on the core bus.
    """

    success_phone: Phone | None = None
    failure: DeviceAuthentificationFailedPayload | None = None


def _ro_serial_after_pair(adb_client: AdbClient, phone: Phone | None) -> str:
    """Read ``ro.serialno`` on the worker when the handset is usable for shell I/O."""
    if phone is None:
        return ""
    state = (phone.descriptor.state or "").strip().casefold()
    if state != "device":
        return ""
    return adb_client.get_ro_serialno(phone)


class AuthenticateDeviceWork(CoreRuntimeWork[AuthentificateDeviceOutcome]):
    """
    Pair over ADB on a worker; emit success/failure from the main thread only.

    ``adb_server`` is used for retry (e.g. ``restart`` after protocol fault); server and
    client mirror :class:`~core.models.CoreRuntimeModel` at job submit time.
    """

    def __init__(
        self,
        adb_server: AdbServer,
        adb_client: AdbClient,
        ip: str,
        port: int,
        association_code: str,
    ) -> None:
        self.adb_server: AdbServer = adb_server
        self.adb_client: AdbClient = adb_client
        self.ip: str = ip
        self.port: int = port
        self.association_code: str = association_code

    def run(self) -> AuthentificateDeviceOutcome:
        """Authentificate a device over ADB (worker thread). Does not touch the core signal bus."""
        adb_server = self.adb_server
        adb_client = self.adb_client
        ip, port, association_code = self.ip, self.port, self.association_code
        try:
            phone = adb_client.pair(ip, port, association_code)
            enrich_phones_with_adb_shell_properties(adb_client, [phone])
            return AuthentificateDeviceOutcome(success_phone=phone, failure=None)
        except AdbClientException as error:
            error_message: str = str(error)
            logger.warning(
                "CoreRuntimeModel: device pairing failed (first attempt)",
                ip=ip,
                port=port,
                error=error_message,
            )
            if "protocol fault" in error_message.lower() and adb_server is not None:
                try:
                    adb_server.restart()
                    logger.info(
                        "CoreRuntimeModel: ADB server restarted after protocol fault",
                        ip=ip,
                        port=port,
                    )
                    phone = adb_client.pair(ip, port, association_code)
                    enrich_phones_with_adb_shell_properties(adb_client, [phone])
                    return AuthentificateDeviceOutcome(
                        success_phone=phone, failure=None
                    )
                except (AdbClientException, AdbServerException) as retry_error:
                    logger.warning(
                        "CoreRuntimeModel: authentification retry failed after ADB server restart",
                        ip=ip,
                        port=port,
                        error=str(retry_error),
                    )
            return AuthentificateDeviceOutcome(
                success_phone=None,
                failure=DeviceAuthentificationFailedPayload(
                    ip=ip,
                    port=port,
                    association_code=association_code,
                    reason=error_message,
                ),
            )

    @staticmethod
    def apply_main_thread(
        model: CoreRuntimeModel, outcome: AuthentificateDeviceOutcome
    ) -> None:
        """Emit authentification outcome on the core bus (Qt main thread only)."""
        from core.models import CoreRuntimeModel as _CoreRuntimeModel

        if not isinstance(model, _CoreRuntimeModel):
            raise TypeError("apply_main_thread() requires CoreRuntimeModel")
        if outcome.failure is not None:
            model._signal_bus.emit(
                CoreSignal.DEVICE_AUTHENTIFICATION_FAILED,
                outcome.failure,
            )
            return
        if outcome.success_phone is not None:
            if model._adb_server is not None:
                model._adb_server.paired_devices.add(outcome.success_phone)
            model._signal_bus.emit(
                CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED,
                DeviceAuthentificationSucceededPayload(phone=outcome.success_phone),
            )
            return
        logger.warning(
            "CoreRuntimeModel: authentificate device apply skipped (empty outcome)",
        )
