from __future__ import annotations

import datetime

# ADB is an external binary; execution is centralized below with list argv and no shell.
import subprocess  # nosec B404
from collections import OrderedDict

from tenacity import (
    Retrying,
    retry_if_exception,
    retry_if_result,
)

from core.adb.binary import AdbBinary
from core.adb.command import (
    ADB_HISTORY_MAX_ENTRIES,
    AdbCommand,
    ADBCommandParser,
    AdbCommandResult,
    AdbCommands,
    ShellEnrichmentProperties,
    _is_retryable_adb_exception,
    _is_retryable_adb_result,
    _log_safe_argv,
    _log_safe_command_line,
    _log_safe_output_preview,
    _redacted_log_value,
    adb_status_from_process,
    adb_status_from_timeout,
    make_adb_retry_after,
    make_adb_retry_before,
    raise_client_for_result,
    retry_profile_for,
    return_last_adb_retry_outcome,
)
from core.adb.exceptions import AdbClientException
from core.devices.phone import Phone
from core.geo.location import Location
from logger import logger


class AdbClient:
    """Client to execute adb commands."""

    def __init__(self, binary: AdbBinary):
        self.binary = binary
        self._history: OrderedDict[
            datetime.datetime, tuple[AdbCommand, AdbCommandResult]
        ] = OrderedDict()

    @property
    def history(
        self,
    ) -> OrderedDict[datetime.datetime, tuple[AdbCommand, AdbCommandResult]]:
        """Get the history of the adb client."""
        return self._history

    @history.setter
    def history(
        self,
        history: OrderedDict[datetime.datetime, tuple[AdbCommand, AdbCommandResult]],
    ) -> None:
        """Set the history of the adb client."""
        self._history = history

    @history.deleter
    def history(self) -> None:
        """Delete the history of the adb client."""
        self._history.clear()

    def add_to_history(self, command: AdbCommand, result: AdbCommandResult) -> None:
        """Add to the history of the adb client."""
        self._history[datetime.datetime.now()] = (command, result)
        self._prune_history()

    def _prune_history(self) -> None:
        """Keep newest client history entries by dropping oldest entries first."""
        while len(self._history) > ADB_HISTORY_MAX_ENTRIES:
            self._history.popitem(last=False)

    def remove_from_history(self, command: AdbCommand) -> None:
        """Remove from the history of the adb client."""
        self._history = OrderedDict(
            (time, entry)
            for time, entry in self._history.items()
            if entry[0] != command
        )

    def status(self, phone: Phone) -> str:
        """
        Read the ADB connection state of a specific device via ``adb -s <id> get-state``.
        """
        command = AdbCommands.STATUS.value
        try:
            result = self._execute(command, phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            raise AdbClientException(
                f"Failed to get device state for {phone.descriptor.id}: {exc}"
            ) from exc
        state = (result.output or "").strip()
        if not state:
            raise AdbClientException(
                f"Empty device state from get-state for {phone.descriptor.id}"
            )
        return state

    def pair(self, ip: str, port: int, association_code: str) -> Phone:
        """
        Pair with a device and return a ``Phone`` parsed from adb output (``guid=`` id).
        """
        command = AdbCommands.PAIR.value
        try:
            result = self._execute(command, None, [f"{ip}:{port}", association_code])
        except AdbClientException:
            raise
        raise_client_for_result(command, result)
        combined = f"{result.output or ''}\n{result.error or ''}".strip()
        phone = ADBCommandParser.PAIR.parse(combined)
        if phone is None:
            snippet = combined if len(combined) <= 500 else combined[:500] + "…"
            raise AdbClientException(
                "Unparseable adb pair output (expected 'Successfully paired to … [guid=…]'): "
                f"{snippet}"
            )
        return phone

    def devices(self) -> list[Phone]:
        """Get the devices."""
        command = AdbCommands.GET_DEVICES.value
        try:
            result = self._execute(command, None)
        except AdbClientException:
            raise
        raise_client_for_result(command, result)
        return ADBCommandParser.GET_DEVICES.parse(result.output or "")

    def send_notification(self, phone: Phone, title: str, message: str) -> bool:
        """
        Send a notification to the device.

        Args:
            phone: The phone to target.
            title: The title of the notification
            message: The message of the notification

        Returns:
            bool: True if the notification was sent successfully, False otherwise
        """
        command = AdbCommands.SEND_NOTIFICATION.value
        try:
            result = self._execute(command, phone, ["-t", title, "-m", message])
        except AdbClientException:
            raise
        raise_client_for_result(command, result)
        return ADBCommandParser.SEND_NOTIFICATION.parse(result.output or "")

    def enable_location_services(self) -> None:
        pass

    def disable_location_services(self) -> None:
        pass

    def set_mock_location(self, location: Location) -> None:
        """Define a fake GPS location."""
        pass

    def get_ro_serialno(self, phone: Phone) -> str:
        """
        Read ``ro.serialno`` on the device: ``adb -s <id> shell getprop ro.serialno``.

        Returns stripped stdout or empty string on failure.
        """
        command = AdbCommands.GET_SERIAL_NO.value
        try:
            result = self._execute(command, phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.serialno",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_SERIAL_NO.parse(result.output or "")
        if not parsed:
            return ""
        out = parsed.strip()
        if not out:
            return ""
        logger.debug(
            "AdbClient: ro.serialno read",
            device_id=phone.descriptor.id,
            serial_len=len(out),
        )
        return out

    def get_device_name_prop(self, phone: Phone) -> str:
        """
        ``adb -s <id> shell getprop device_name``. Returns stripped value or ``""`` on failure.
        """
        command = AdbCommands.GET_DEVICE_NAME.value
        try:
            result = self._execute(command, phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read device_name",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_DEVICE_NAME.parse(result.output or "")
        return (parsed or "").strip()

    def get_android_release(self, phone: Phone) -> str:
        """
        ``ro.build.version.release`` — Android version string (e.g. ``"15"``).
        """
        command = AdbCommands.GET_ANDROID_VERSION.value
        try:
            result = self._execute(command, phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.build.version.release",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_ANDROID_VERSION.parse(result.output or "")
        return (parsed or "").strip()

    def get_product_manufacturer(self, phone: Phone) -> str:
        """``ro.product.manufacturer``."""
        command = AdbCommands.GET_MANUFACTURER.value
        try:
            result = self._execute(command, phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.product.manufacturer",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_MANUFACTURER.parse(result.output or "")
        return (parsed or "").strip()

    def get_product_model(self, phone: Phone) -> str:
        """``ro.product.model`` (commercial model string)."""
        command = AdbCommands.GET_PRODUCT_MODEL.value
        try:
            result = self._execute(command, phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.product.model",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_PRODUCT_MODEL.parse(result.output or "")
        return (parsed or "").strip()

    def get_android_sdk_api_level(self, phone: Phone) -> int | None:
        """``ro.build.version.sdk`` as integer API level, or ``None`` if unreadable."""
        command = AdbCommands.GET_SDK_VERSION.value
        try:
            result = self._execute(command, phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.build.version.sdk",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return None
        return ADBCommandParser.GET_SDK_VERSION.parse(result.output or "")

    def get_shell_enrichment_properties(
        self, phone: Phone
    ) -> ShellEnrichmentProperties:
        """
        Fetch shell-backed device enrichment properties in one ADB round trip.

        Returns empty-string/``None`` values when the command fails so refresh paths can
        preserve the existing best-effort enrichment behavior.
        """
        command = AdbCommands.GET_SHELL_ENRICHMENT_PROPERTIES.value
        try:
            result = self._execute(command, phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read shell enrichment properties",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ADBCommandParser.GET_SHELL_ENRICHMENT_PROPERTIES.parse("")
        return ADBCommandParser.GET_SHELL_ENRICHMENT_PROPERTIES.parse(
            result.output or ""
        )

    def _execute(
        self,
        command: AdbCommand,
        phone: Phone | None = None,
        positional_arguments: list[str] | None = None,
    ) -> AdbCommandResult:
        """
        Execute a command with Tenacity-backed retries on transient subprocess failures.
        """
        positional_arguments = positional_arguments or []
        argv: list[str] = [str(self.binary.path)]
        if phone is not None:
            argv.extend(["-s", phone.descriptor.id])
        argv.extend([command.command, *command.args, *positional_arguments])
        phone_id = phone.descriptor.id if phone else None
        profile = retry_profile_for(command, scope="client")

        def _attempt() -> AdbCommandResult:
            logger.debug(
                "AdbClient: executing command",
                adb_path=str(self.binary.path),
                command=command.command,
                phone_id=_redacted_log_value(phone_id),
                argv=_log_safe_argv(command, argv),
                command_line=_log_safe_command_line(command, argv),
                timeout_s=profile.timeout_seconds,
            )
            try:
                # ADB execution uses list argv, no shell, and bounded timeouts.
                completed = subprocess.run(  # nosec B603
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=profile.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                error = f"timed out after {profile.timeout_seconds}s"
                logger.debug(
                    "AdbClient: command timed out",
                    adb_path=str(self.binary.path),
                    command=command.command,
                    phone_id=_redacted_log_value(phone_id),
                    error=error,
                )
                return AdbCommandResult(
                    status=adb_status_from_timeout(),
                    phone=phone,
                    time=datetime.datetime.now(),
                    output=exc.output or "",
                    error=error,
                    return_code=1,
                )
            except subprocess.CalledProcessError as exc:
                raise AdbClientException(
                    f"Failed to execute command: {command.command} {command.args}"
                ) from exc
            except OSError as exc:
                raise AdbClientException(
                    f"Failed to run ADB binary {self.binary.path}"
                ) from exc
            logger.debug(
                "AdbClient: command completed",
                adb_path=str(self.binary.path),
                command=command.command,
                return_code=completed.returncode,
                stdout=_log_safe_output_preview(completed.stdout.strip(), command),
                stderr=_log_safe_output_preview(completed.stderr.strip(), command),
            )
            return AdbCommandResult(
                status=adb_status_from_process(
                    return_code=completed.returncode,
                    output=completed.stdout or "",
                    error=completed.stderr or "",
                ),
                phone=phone,
                time=datetime.datetime.now(),
                output=completed.stdout or "",
                error=completed.stderr or "",
                return_code=completed.returncode,
            )

        retryer = Retrying(
            stop=profile.stop,
            wait=profile.wait,
            retry=retry_if_exception(_is_retryable_adb_exception)
            | retry_if_result(_is_retryable_adb_result),
            reraise=True,
            before=make_adb_retry_before(
                scope="client", command_name=command.command, phone_id=phone_id
            ),
            after=make_adb_retry_after(
                scope="client", command_name=command.command, phone_id=phone_id
            ),
            retry_error_callback=return_last_adb_retry_outcome,
        )
        result = retryer(_attempt)
        self.add_to_history(command, result)
        return result
