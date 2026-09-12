"""
Worker / main-thread split for device pairing: ADB I/O on a worker, bus emit on the UI thread.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import ClassVar, cast

from core.adb.client import AdbClient
from core.adb.exceptions import AdbClientException, AdbServerException
from core.adb.server import AdbServer
from core.devices.phone import Phone
from core.entrypoint_protocol import CoreSignalEmitter, DeviceRegistrationEntrypoint
from core.exceptions import CoreException
from core.signals import (
    CoreSignals,
    DeviceAuthentificationFailedPayload,
    DeviceAuthentificationSucceededPayload,
)
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from core.work.helper import device_endpoint_is_paired, preflight
from core.work.refresh_known_devices_work import enrich_phones_with_adb_shell_properties
from logger import logger


class DeviceAuthentificationError(CoreException):
    """Pairing failed; propagates to AsyncRunner ``on_failed`` for user-facing reporting."""

    def __init__(
        self,
        *,
        ip: str,
        port: int,
        association_code: str,
        reason: str,
    ) -> None:
        """Initialize a device-pairing failure.

        Args:
            ip: Requested device IPv4 address.
            port: Requested pairing port.
            association_code: Requested pairing code.
            reason: Human-readable failure reason.
        """
        self.ip = ip
        self.port = port
        self.association_code = association_code
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class AuthentificateDeviceOutcome(CoreRuntimeWorkOutcome):
    """
    Success result of :meth:`AuthenticateDeviceWork.run` (worker).

    On success, ``run`` already applies shell enrichment to ``success_phone``;
    :meth:`AuthenticateDeviceWork.apply_main_thread` emits on the core bus.
    Failures raise :class:`DeviceAuthentificationError` instead of returning an outcome.
    """

    success_phone: Phone


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
    Pair over ADB on a worker; emit success from the main thread only.

    ``adb_server`` is used for retry (e.g. ``restart`` after protocol fault); server and
    client mirror :class:`~core.entrypoint.ModelEntrypoint` at job submit time.
    """

    def __init__(
        self,
        adb_server: AdbServer | None,
        adb_client: AdbClient | None,
        ip: str,
        port: int,
        association_code: str,
    ) -> None:
        """Initialize a device-pairing work item.

        Args:
            adb_server: Active server used for preflight and retry.
            adb_client: Active client used to pair the device.
            ip: Device IPv4 address.
            port: Device pairing port.
            association_code: Six-digit wireless pairing code.
        """
        self.adb_server: AdbServer | None = adb_server
        self.adb_client: AdbClient | None = adb_client
        self.ip: str = ip
        self.port: int = port
        self.association_code: str = association_code

    @staticmethod
    def _preflight_error(work: object) -> DeviceAuthentificationError:
        if not isinstance(work, AuthenticateDeviceWork):
            return DeviceAuthentificationError(
                ip="",
                port=0,
                association_code="",
                reason="ADB runtime preflight failed",
            )
        reason = (
            "Device with this IP address and port is already paired"
            if device_endpoint_is_paired(work)
            else "ADB runtime preflight failed"
        )
        return DeviceAuthentificationError(
            ip=work.ip,
            port=work.port,
            association_code=work.association_code,
            reason=reason,
        )

    @preflight(
        check_server_started=True,
        check_client_created=True,
        check_device_not_paired=True,
        check_network_available=True,
        check_mdns_available=True,
        error_to_raise=_preflight_error,
    )
    def run(self) -> AuthentificateDeviceOutcome:
        """
        Validate pairing inputs, pair over ADB, and enrich the paired phone
        (AsyncRunner worker thread).

        Invalid IP, port, or association code raises
        :class:`DeviceAuthentificationError` without calling ADB. On
        :class:`~core.adb.exceptions.AdbClientException`, if the message contains
        ``"protocol fault"`` (case-insensitive) and ``adb_server`` is set, the server
        is restarted and pairing plus enrichment are retried once. Shell enrichment after
        a successful pair is best-effort (failures are swallowed inside the client).
        User-facing failure reporting happens in the controller ``on_failed`` callback.

        Returns:
            AuthentificateDeviceOutcome: ``success_phone`` after pairing and enrichment.

        Raises:
            DeviceAuthentificationError: Validation failure or pairing/retry failure.
            Exception: Any unexpected failure outside the documented pairing path
            propagates to AsyncRunner.
        """
        adb_server = cast(AdbServer, self.adb_server)
        adb_client = cast(AdbClient, self.adb_client)
        ip, port, association_code = self.ip, self.port, self.association_code
        validation_failure = PairingInputValidator.validate(ip, port, association_code)
        if validation_failure is not None:
            logger.debug(
                "Device pairing input validation failed",
                ip=ip,
                port=port,
                reason=validation_failure,
            )
            raise DeviceAuthentificationError(
                ip=ip,
                port=port,
                association_code=association_code,
                reason=validation_failure,
            )
        try:
            phone = adb_client.pair(ip, port, association_code)
            enrich_phones_with_adb_shell_properties(adb_client, [phone])
            return AuthentificateDeviceOutcome(success_phone=phone)
        except AdbClientException as error:
            error_message: str = str(error)
            logger.debug(
                "Device pairing attempt failed",
                ip=ip,
                port=port,
                error=error_message,
            )
            if "protocol fault" in error_message.lower() and adb_server is not None:
                try:
                    adb_server.restart()
                    logger.info(
                        "ADB server restarted after a pairing protocol fault",
                        ip=ip,
                        port=port,
                    )
                    phone = adb_client.pair(ip, port, association_code)
                    enrich_phones_with_adb_shell_properties(adb_client, [phone])
                    return AuthentificateDeviceOutcome(success_phone=phone)
                except (AdbClientException, AdbServerException) as retry_error:
                    logger.debug(
                        "Device pairing retry failed after ADB server restart",
                        ip=ip,
                        port=port,
                        error=str(retry_error),
                    )
                    raise DeviceAuthentificationError(
                        ip=ip,
                        port=port,
                        association_code=association_code,
                        reason=str(retry_error),
                    ) from retry_error
            raise DeviceAuthentificationError(
                ip=ip,
                port=port,
                association_code=association_code,
                reason=error_message,
            ) from error

    @staticmethod
    def apply_main_thread(
        model_entrypoint: CoreSignalEmitter,
        outcome: AuthentificateDeviceOutcome,
    ) -> None:
        """Emit successful authentification on the core bus (Qt main thread only)."""
        registration_entrypoint = cast(DeviceRegistrationEntrypoint, model_entrypoint)
        logger.info(
            "Device paired",
            device_id=outcome.success_phone.id,
            device_name=outcome.success_phone.name,
        )
        registration_entrypoint.register_paired_device(outcome.success_phone)
        registration_entrypoint.emit_core_signal(
            CoreSignals.DEVICE_AUTHENTIFICATION_SUCCEEDED,
            DeviceAuthentificationSucceededPayload(
                device=outcome.success_phone.serialize(json_compatible=False),
            ),
        )

    @staticmethod
    def apply_failure_main_thread(
        model_entrypoint: CoreSignalEmitter, error: BaseException
    ) -> None:
        """Emit a typed pairing failure or a generic core error.

        Args:
            model_entrypoint: Main-thread signal-emission boundary.
            error: Worker failure to translate.
        """
        if isinstance(error, DeviceAuthentificationError):
            logger.warning(
                "Device pairing failed",
                ip=error.ip,
                port=error.port,
                association_code=error.association_code,
                reason=error.reason,
            )
            model_entrypoint.emit_core_signal(
                CoreSignals.DEVICE_AUTHENTIFICATION_FAILED,
                DeviceAuthentificationFailedPayload(
                    ip=error.ip,
                    port=error.port,
                    association_code=error.association_code,
                    reason=error.reason,
                ),
            )
            return
        AuthenticateDeviceWork.emit_generic_error(
            model_entrypoint,
            source="AuthenticateDeviceWork",
            message=str(error),
            error=error,
        )
