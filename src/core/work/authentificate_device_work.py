"""
Worker / main-thread split for device pairing: ADB I/O on a worker, bus emit on the UI thread.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from core.adb.client import AdbClient
from core.adb.exceptions import AdbClientException, AdbServerException
from core.adb.server import AdbServer
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
    from core.entrypoint import ModelEntrypoint


@dataclass(frozen=True, slots=True)
class AuthentificateDeviceOutcome(CoreRuntimeWorkOutcome):
    """
    Result of :meth:`AuthenticateDeviceWork.run` (worker).

    On success, ``run`` already applies ``ro.serialno`` enrichment to ``success_phone``
    (shared object); :meth:`AuthenticateDeviceWork.apply_main_thread` only emits on the core bus.
    """

    success_phone: Phone | None = None
    failure: DeviceAuthentificationFailedPayload | None = None


class PairingInputValidator:
    """Core-side validation rules for ADB wireless pairing inputs."""

    ASSOCIATION_CODE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[0-9]{6}$")
    PORT_MIN: ClassVar[int] = 1
    PORT_MAX: ClassVar[int] = 65535

    @classmethod
    def validate(cls, ip: str, port: int, association_code: str) -> str | None:
        """Return a failure reason for invalid pairing input, otherwise ``None``."""
        try:
            ipaddress.IPv4Address(ip)
        except (ipaddress.AddressValueError, ValueError):
            return "Invalid IPv4 address"
        if isinstance(port, bool) or not isinstance(port, int):
            return "Invalid port number"
        if not cls.PORT_MIN <= port <= cls.PORT_MAX:
            return "Invalid port range"
        if cls.ASSOCIATION_CODE_PATTERN.fullmatch(association_code) is None:
            return "Invalid association code"
        return None


class AuthenticateDeviceWork(CoreRuntimeWork[AuthentificateDeviceOutcome]):
    """
    Pair over ADB on a worker; emit success/failure from the main thread only.

    ``adb_server`` is used for retry (e.g. ``restart`` after protocol fault); server and
    client mirror :class:`~core.entrypoint.ModelEntrypoint` at job submit time.
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
        """
        Validate pairing inputs, pair over ADB, and enrich the paired phone
        (AsyncRunner worker thread).

        Invalid IP, port, or association code returns a failure outcome without
        calling ADB. On :class:`~core.adb.exceptions.AdbClientException`, if the
        message contains ``"protocol fault"`` (case-insensitive) and
        ``adb_server`` is set, the server is restarted and pairing plus
        enrichment are retried once. Shell enrichment after a successful pair is
        best-effort (failures are swallowed inside the client). This method does
        not touch the core signal bus; :meth:`apply_main_thread` emits success or
        failure.

        Returns:
            AuthentificateDeviceOutcome: On success, ``success_phone`` is set and
            ``failure`` is ``None``. On validation or handled pairing failure,
            ``success_phone`` is ``None`` and ``failure`` carries
            :class:`~core.signals.DeviceAuthentificationFailedPayload` with a
            user-facing ``reason``. After a failed protocol-fault retry, ``reason``
            is the **first** attempt's error message, not the retry error.

        Raises:
            None: Validation failures and handled
            :class:`~core.adb.exceptions.AdbClientException` /
            :class:`~core.adb.exceptions.AdbServerException` from pairing or
            retry are converted into a failure outcome.
            Exception: Any exception other than :class:`~core.adb.exceptions.AdbClientException`
            on the first ``pair``/enrichment attempt, or any non-ADB exception
            during ``adb_server.restart()``, propagates to AsyncRunner.
        """
        adb_server = self.adb_server
        adb_client = self.adb_client
        ip, port, association_code = self.ip, self.port, self.association_code
        validation_failure = PairingInputValidator.validate(ip, port, association_code)
        if validation_failure is not None:
            logger.warning(
                "ModelEntrypoint: device pairing input validation failed",
                ip=ip,
                port=port,
                reason=validation_failure,
            )
            return AuthentificateDeviceOutcome(
                success_phone=None,
                failure=DeviceAuthentificationFailedPayload(
                    ip=ip,
                    port=port,
                    association_code=association_code,
                    reason=validation_failure,
                ),
            )
        try:
            phone = adb_client.pair(ip, port, association_code)
            enrich_phones_with_adb_shell_properties(adb_client, [phone])
            return AuthentificateDeviceOutcome(success_phone=phone, failure=None)
        except AdbClientException as error:
            error_message: str = str(error)
            logger.warning(
                "ModelEntrypoint: device pairing failed (first attempt)",
                ip=ip,
                port=port,
                error=error_message,
            )
            if "protocol fault" in error_message.lower() and adb_server is not None:
                try:
                    adb_server.restart()
                    logger.info(
                        "ModelEntrypoint: ADB server restarted after protocol fault",
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
                        "ModelEntrypoint: authentification retry failed after ADB server restart",
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
        model_entrypoint: ModelEntrypoint, outcome: AuthentificateDeviceOutcome
    ) -> None:
        """Emit authentification outcome on the core bus (Qt main thread only)."""
        from core.entrypoint import ModelEntrypoint as _ModelEntrypoint

        if not isinstance(model_entrypoint, _ModelEntrypoint):
            raise TypeError("apply_main_thread() requires ModelEntrypoint")
        if outcome.failure is not None:
            model_entrypoint._signal_bus.emit(
                CoreSignal.DEVICE_AUTHENTIFICATION_FAILED,
                outcome.failure,
            )
            return
        if outcome.success_phone is not None:
            if model_entrypoint._adb_server is not None:
                model_entrypoint._adb_server.paired_devices.add(outcome.success_phone)
            model_entrypoint._signal_bus.emit(
                CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED,
                DeviceAuthentificationSucceededPayload(phone=outcome.success_phone),
            )
            return
        logger.warning(
            "ModelEntrypoint: authentificate device apply skipped (empty outcome)",
        )
