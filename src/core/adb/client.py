from __future__ import annotations

from dataclasses import replace

from core.adb.binary import AdbBinary
from core.adb.command import (
    AdbCommandInvocation,
    AdbCommandResult,
    AdbCommandResultStatus,
    AdbCommands,
    AdbCommandSpec,
    _redacted_log_value,
)
from core.adb.exceptions import AdbClientException
from core.adb.execution import AdbCommandExecutor
from core.adb.history import (
    AdbCommandHistory,
    AdbCommandHistoryEntries,
    AdbCommandHistoryManager,
)
from core.adb.parser import ShellEnrichmentProperties, parse_device_state_from_listing
from core.adb.retry import raise_client_for_result
from core.devices.phone import Phone
from core.geo.location import Location
from logger import logger


class AdbClient:
    """Client to execute adb commands."""

    def __init__(self, binary: AdbBinary) -> None:
        """Initialize the client for an ADB binary.

        Args:
            binary: ADB binary metadata used for command execution.
        """
        self._executor = self._create_executor(binary)
        self._history_manager = AdbCommandHistoryManager()

    @property
    def binary(self) -> AdbBinary:
        """Return the ADB binary used by this client."""
        return self._executor.binary

    def _create_executor(self, binary: AdbBinary) -> AdbCommandExecutor:
        """Create the command executor owned by this client."""
        return AdbCommandExecutor(binary)

    @property
    def history(self) -> AdbCommandHistory:
        """Get the history of the adb client."""
        return self._history_manager.history

    @history.setter
    def history(
        self,
        history: AdbCommandHistoryEntries,
    ) -> None:
        """Set the history of the adb client."""
        self._history_manager.replace(history)

    @history.deleter
    def history(self) -> None:
        """Delete the history of the adb client."""
        self._history_manager.clear()

    def add_to_history(
        self, command: AdbCommandSpec[object], result: AdbCommandResult
    ) -> None:
        """Add to the history of the adb client."""
        self._history_manager.add(command, result)

    def remove_from_history(self, command: AdbCommandSpec[object]) -> None:
        """Remove from the history of the adb client."""
        self._history_manager.remove(command)

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
        """Enable Android location services.

        Raises:
            NotImplementedError: Always; location-service control is unavailable.
        """
        raise NotImplementedError("Enabling location services is not implemented")

    def disable_location_services(self) -> None:
        """Disable Android location services.

        Raises:
            NotImplementedError: Always; location-service control is unavailable.
        """
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
        try:
            result = self._executor.execute(
                invocation,
                scope="client",
                phone=phone,
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

    def _diagnose_phone_reference(
        self, phone: Phone, failed_command: AdbCommandSpec[object]
    ) -> str:
        """Check once whether a failed command's target remains listed by ADB."""
        devices_command = AdbCommands.GET_DEVICES
        try:
            result = self._executor.execute_once(
                devices_command.invoke(),
                scope="client",
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
