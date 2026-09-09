from __future__ import annotations

import datetime

# ADB is an external binary; execution is centralized below with list argv and no shell.
import subprocess  # nosec B404
from collections import OrderedDict
from dataclasses import replace

from core.adb.binary import AdbBinary
from core.adb.command import (
    ADB_HISTORY_MAX_ENTRIES,
    AdbCommandInvocation,
    AdbCommandResult,
    AdbCommandResultStatus,
    AdbCommands,
    AdbCommandSpec,
    _log_safe_argv,
    _log_safe_command_line,
    _log_safe_output_preview,
    _redacted_log_value,
)
from core.adb.exceptions import AdbClientException
from core.adb.parser import ShellEnrichmentProperties, parse_device_state_from_listing
from core.adb.retry import (
    adb_status_from_process,
    adb_status_from_timeout,
    execute_with_adb_retry,
    raise_client_for_result,
    timeout_seconds_for,
)
from core.devices.phone import Phone
from core.geo.location import Location
from logger import logger


class AdbClient:
    """Client to execute adb commands."""

    def __init__(self, binary: AdbBinary):
        self.binary = binary
        self._history: OrderedDict[
            datetime.datetime, tuple[AdbCommandSpec[object], AdbCommandResult]
        ] = OrderedDict()

    @property
    def history(
        self,
    ) -> OrderedDict[
        datetime.datetime, tuple[AdbCommandSpec[object], AdbCommandResult]
    ]:
        """Get the history of the adb client."""
        return self._history

    @history.setter
    def history(
        self,
        history: OrderedDict[
            datetime.datetime, tuple[AdbCommandSpec[object], AdbCommandResult]
        ],
    ) -> None:
        """Set the history of the adb client."""
        self._history = history

    @history.deleter
    def history(self) -> None:
        """Delete the history of the adb client."""
        self._history.clear()

    def add_to_history(
        self, command: AdbCommandSpec[object], result: AdbCommandResult
    ) -> None:
        """Add to the history of the adb client."""
        self._history[datetime.datetime.now()] = (command, result)
        self._prune_history()

    def _prune_history(self) -> None:
        """Keep newest client history entries by dropping oldest entries first."""
        while len(self._history) > ADB_HISTORY_MAX_ENTRIES:
            self._history.popitem(last=False)

    def remove_from_history(self, command: AdbCommandSpec[object]) -> None:
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
        command = AdbCommands.STATUS
        try:
            result = self._execute(command.invoke(), phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            raise AdbClientException(
                f"Failed to get device state for {phone.descriptor.id}: {exc}"
            ) from exc
        state = command.parse(result.output or "")
        if not state:
            raise AdbClientException(
                f"Empty device state from get-state for {phone.descriptor.id}"
            )
        return state

    def pair(self, ip: str, port: int, association_code: str) -> Phone:
        """
        Pair with a device and return a ``Phone`` parsed from adb output (``guid=`` id).
        """
        command = AdbCommands.PAIR
        try:
            result = self._execute(command.invoke(f"{ip}:{port}", association_code))
        except AdbClientException:
            raise
        raise_client_for_result(command, result)
        combined = f"{result.output or ''}\n{result.error or ''}".strip()
        phone = command.parse(combined)
        if phone is None:
            snippet = combined if len(combined) <= 500 else combined[:500] + "…"
            raise AdbClientException(
                "Unparseable adb pair output (expected 'Successfully paired to … [guid=…]'): "
                f"{snippet}"
            )
        return phone

    def devices(self) -> list[Phone]:
        """Get the devices."""
        command = AdbCommands.GET_DEVICES
        try:
            result = self._execute(command.invoke())
        except AdbClientException:
            raise
        raise_client_for_result(command, result)
        return command.parse(result.output or "")

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
        command = AdbCommands.SEND_NOTIFICATION
        try:
            result = self._execute(
                command.invoke("-t", title, "-m", message),
                phone,
            )
        except AdbClientException:
            raise
        raise_client_for_result(command, result)
        return command.parse(result.output or "")

    def enable_location_services(self) -> None:
        raise NotImplementedError("Enabling location services is not implemented")

    def disable_location_services(self) -> None:
        raise NotImplementedError("Disabling location services is not implemented")

    def set_mock_location(self, location: Location) -> None:
        """Define a fake GPS location."""
        raise NotImplementedError("Setting a mock location is not implemented")

    def get_ro_serialno(self, phone: Phone) -> str:
        """
        Read ``ro.serialno`` on the device: ``adb -s <id> shell getprop ro.serialno``.

        Returns stripped stdout or empty string on failure.
        """
        command = AdbCommands.GET_SERIAL_NO
        try:
            result = self._execute(command.invoke(), phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.debug(
                "Device serial property could not be read",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = command.parse(result.output or "")
        if not parsed:
            return ""
        out = parsed.strip()
        if not out:
            return ""
        logger.debug(
            "Device serial property read",
            device_id=phone.descriptor.id,
            serial_len=len(out),
        )
        return out

    def get_device_name_prop(self, phone: Phone) -> str:
        """
        ``adb -s <id> shell getprop device_name``. Returns stripped value or ``""`` on failure.
        """
        command = AdbCommands.GET_DEVICE_NAME
        try:
            result = self._execute(command.invoke(), phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.debug(
                "Device name property could not be read",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = command.parse(result.output or "")
        return (parsed or "").strip()

    def get_android_release(self, phone: Phone) -> str:
        """
        ``ro.build.version.release`` — Android version string (e.g. ``"15"``).
        """
        command = AdbCommands.GET_ANDROID_VERSION
        try:
            result = self._execute(command.invoke(), phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.debug(
                "Android release property could not be read",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = command.parse(result.output or "")
        return (parsed or "").strip()

    def get_product_manufacturer(self, phone: Phone) -> str:
        """``ro.product.manufacturer``."""
        command = AdbCommands.GET_MANUFACTURER
        try:
            result = self._execute(command.invoke(), phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.debug(
                "Device manufacturer property could not be read",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = command.parse(result.output or "")
        return (parsed or "").strip()

    def get_product_model(self, phone: Phone) -> str:
        """``ro.product.model`` (commercial model string)."""
        command = AdbCommands.GET_PRODUCT_MODEL
        try:
            result = self._execute(command.invoke(), phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.debug(
                "Device model property could not be read",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = command.parse(result.output or "")
        return (parsed or "").strip()

    def get_android_sdk_api_level(self, phone: Phone) -> int | None:
        """``ro.build.version.sdk`` as integer API level, or ``None`` if unreadable."""
        command = AdbCommands.GET_SDK_VERSION
        try:
            result = self._execute(command.invoke(), phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.debug(
                "Android SDK property could not be read",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return None
        return command.parse(result.output or "")

    def get_shell_enrichment_properties(
        self, phone: Phone
    ) -> ShellEnrichmentProperties:
        """
        Fetch shell-backed device enrichment properties in one ADB round trip.

        Returns empty-string/``None`` values when the command fails so refresh paths can
        preserve the existing best-effort enrichment behavior.
        """
        command = AdbCommands.GET_SHELL_ENRICHMENT_PROPERTIES
        try:
            result = self._execute(command.invoke(), phone)
            raise_client_for_result(command, result)
        except AdbClientException as exc:
            logger.warning(
                "Device shell properties could not be enriched",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return command.parse("")
        return command.parse(result.output or "")

    def _execute(
        self,
        invocation: AdbCommandInvocation[object],
        phone: Phone | None = None,
    ) -> AdbCommandResult:
        """
        Execute a command with Tenacity-backed retries on transient subprocess failures.
        """
        command = invocation.spec
        phone_id = phone.descriptor.id if phone else None

        def _attempt(timeout_seconds: float) -> AdbCommandResult:
            return self._run_once(
                invocation,
                phone=phone,
                timeout_seconds=timeout_seconds,
            )

        try:
            result = execute_with_adb_retry(
                command,
                scope="client",
                phone_id=phone_id,
                attempt=_attempt,
            )
        except AdbClientException as exc:
            if phone is None:
                raise
            diagnostic = self._diagnose_phone_reference(phone, command)
            raise AdbClientException(f"{exc}; {diagnostic}") from exc

        if phone is None or result.status == AdbCommandResultStatus.SUCCESS:
            self.add_to_history(command, result)
            return result

        diagnostic = self._diagnose_phone_reference(phone, command)
        original_detail = (result.error or result.output or result.status.name).strip()
        result_with_diagnostic = replace(
            result, error=f"{original_detail}; {diagnostic}"
        )
        self.add_to_history(command, result_with_diagnostic)
        return result_with_diagnostic

    def _run_once(
        self,
        invocation: AdbCommandInvocation[object],
        *,
        phone: Phone | None,
        timeout_seconds: float,
    ) -> AdbCommandResult:
        """Run one bounded ADB subprocess attempt without applying retry policy."""
        command = invocation.spec
        phone_id = phone.descriptor.id if phone else None
        argv = invocation.argv(self.binary.path, device_id=phone_id)
        logger.debug(
            "ADB client command started",
            adb_path=str(self.binary.path),
            command=command.argv[0],
            phone_id=_redacted_log_value(phone_id),
            argv=_log_safe_argv(invocation, self.binary.path, device_id=phone_id),
            command_line=_log_safe_command_line(
                invocation, self.binary.path, device_id=phone_id
            ),
            timeout_s=timeout_seconds,
        )
        try:
            # ADB execution uses list argv, no shell, and a bounded timeout.
            completed = subprocess.run(  # nosec B603
                argv,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            error = f"timed out after {timeout_seconds}s"
            logger.debug(
                "ADB client command timed out",
                adb_path=str(self.binary.path),
                command=command.argv[0],
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
                f"Failed to execute command: {command.argv}"
            ) from exc
        except OSError as exc:
            raise AdbClientException(
                f"Failed to run ADB binary {self.binary.path}"
            ) from exc
        logger.debug(
            "ADB client command completed",
            adb_path=str(self.binary.path),
            command=command.argv[0],
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

    def _diagnose_phone_reference(
        self, phone: Phone, failed_command: AdbCommandSpec[object]
    ) -> str:
        """Check once whether a failed command's target remains listed by ADB."""
        devices_command = AdbCommands.GET_DEVICES
        try:
            result = self._run_once(
                devices_command.invoke(),
                phone=None,
                timeout_seconds=timeout_seconds_for(devices_command),
            )
        except AdbClientException:
            logger.warning(
                "ADB client failure device reference could not be checked",
                command=failed_command.argv[0],
                phone_id=_redacted_log_value(phone.descriptor.id),
                device_reference="unknown",
                probe_status="EXCEPTION",
            )
            return (
                "target device reference could not be determined "
                "(ADB device-list check raised an exception)"
            )

        self.add_to_history(devices_command, result)
        if result.status != AdbCommandResultStatus.SUCCESS:
            logger.warning(
                "ADB client failure device reference could not be checked",
                command=failed_command.argv[0],
                phone_id=_redacted_log_value(phone.descriptor.id),
                device_reference="unknown",
                probe_status=result.status.name,
            )
            return (
                "target device reference could not be determined "
                f"(ADB device-list check returned {result.status.name})"
            )

        state = parse_device_state_from_listing(
            result.output or "",
            phone.descriptor.id,
        )
        if state is None:
            logger.warning(
                "ADB client failure target device is no longer listed",
                command=failed_command.argv[0],
                phone_id=_redacted_log_value(phone.descriptor.id),
                device_reference="missing",
            )
            return "target device is no longer listed by ADB"

        logger.warning(
            "ADB client failure target device remains listed",
            command=failed_command.argv[0],
            phone_id=_redacted_log_value(phone.descriptor.id),
            device_reference="present",
            device_state=state,
        )
        return f"target device remains listed by ADB with state {state!r}"
