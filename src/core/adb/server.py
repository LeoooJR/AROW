from __future__ import annotations

import datetime

from core.adb.binary import AdbBinary
from core.adb.command import (
    AdbCommandInvocation,
    AdbCommandResult,
    AdbCommandResultStatus,
    AdbCommands,
    AdbCommandSpec,
    _log_safe_output_preview,
)
from core.adb.exceptions import AdbClientException, AdbServerException
from core.adb.execution import AdbCommandExecutor
from core.adb.history import (
    AdbCommandHistory,
    AdbCommandHistoryEntries,
    AdbCommandHistoryManager,
)
from core.adb.retry import (
    raise_server_for_result,
)
from core.devices.phone import Phone, PhoneRepository
from core.network import resolve_network_identity
from logger import logger


class AdbServer:
    """Side-effect-free ADB daemon facade with explicit lifecycle operations."""

    def __init__(self, binary: AdbBinary) -> None:
        self._executor = self._create_executor(binary)
        self._history_manager = AdbCommandHistoryManager()
        self._paired_devices: PhoneRepository = PhoneRepository()
        self._mdns_available: bool = False
        self._network_available: bool = False

    @property
    def binary(self) -> AdbBinary:
        """Return the ADB binary used by this server."""
        return self._executor.binary

    def _create_executor(self, binary: AdbBinary) -> AdbCommandExecutor:
        """Create the command executor owned by this server."""
        return AdbCommandExecutor(binary)

    @property
    def history(self) -> AdbCommandHistory:
        """Get the history of the adb server."""
        return self._history_manager.history

    @history.setter
    def history(
        self,
        history: AdbCommandHistoryEntries,
    ) -> None:
        """Set the history of the adb server."""
        self._history_manager.replace(history)

    @history.deleter
    def history(self) -> None:
        """Delete the history of the adb server."""
        self._history_manager.clear()

    def add_to_history(
        self, command: AdbCommandSpec[object], result: AdbCommandResult
    ) -> None:
        """Add to the history of the adb server."""
        self._history_manager.add(command, result)

    def remove_from_history(self, command: AdbCommandSpec[object]) -> None:
        """Remove from the history of the adb server."""
        self._history_manager.remove(command)

    def get_last_command_time(self) -> datetime.datetime:
        """Get the time of the last command."""
        return self._history_manager.latest_time()

    def get_last_from_history(
        self,
    ) -> tuple[AdbCommandSpec[object], AdbCommandResult]:
        """Get the last command and result."""
        return self._history_manager.latest_entry()

    def get_last_command(self) -> AdbCommandSpec[object]:
        """Get the last command."""
        return self._history_manager.latest_command()

    def get_last_command_result(self) -> AdbCommandResult:
        """Get the last command result."""
        return self._history_manager.latest_result()

    @property
    def paired_devices(self) -> PhoneRepository:
        """Get the paired devices."""
        return self._paired_devices

    @paired_devices.setter
    def paired_devices(self, paired_devices: PhoneRepository) -> None:
        """Set the paired devices."""
        self._paired_devices = paired_devices

    @paired_devices.deleter
    def paired_devices(self) -> None:
        """Delete the paired devices."""
        self._paired_devices.clear()

    def set_working_device(self, device: Phone) -> None:
        """Set the working device."""
        try:
            self._paired_devices.working_device = device
        except ValueError as e:
            logger.error(
                "ADB working device could not be set",
                error=str(e),
                device_id=device.id,
            )
            raise e

    def get_working_device(self) -> Phone | None:
        """Get the working device."""
        return self._paired_devices.working_device

    def clear_working_device(self) -> None:
        """Clear the working device."""
        self._paired_devices.working_device = None

    @property
    def mdns_available(self) -> bool:
        """Get whether ADB reports mDNS discovery as available."""
        return self._mdns_available

    @property
    def network_available(self) -> bool:
        """Get whether the host has a usable non-loopback IPv4 route."""
        return self._network_available

    def start(self) -> None:
        """Start the ADB daemon without performing discovery or capability probes."""
        command = AdbCommands.START_SERVER
        result = self._execute(command.invoke())
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to start adb server: {result}")

    def stop(self) -> None:
        """Stop the adb server."""
        command = AdbCommands.KILL_SERVER
        result = self._execute(command.invoke())
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to stop adb server: {result}")

    def restart(self) -> None:
        """Restart the adb server."""
        try:
            self.stop()
            self.start()
        except AdbServerException:
            raise

    @classmethod
    def get_binary_version(
        cls,
        binary: AdbBinary,
    ) -> AdbBinary:
        """
        Read ADB binary metadata without constructing or starting the ADB server.
        """
        command = AdbCommands.GET_BINARY_VERSION
        command_executor = AdbCommandExecutor(binary)
        result = command_executor.execute_once(
            command.invoke(),
            scope="server",
        )
        if result.status is AdbCommandResultStatus.TIMEOUT:
            raise AdbServerException(
                f"Failed to read ADB binary version: {result.error}"
            )
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(
                f"Failed to read ADB binary version: {result.status.name}"
            )
        parsed = command.parse(result.output or "")
        if not parsed.version or not parsed.build_version:
            raise AdbServerException(
                "Failed to parse ADB binary version from --version output"
            )
        return parsed

    def refresh_mdns_availability(self) -> bool:
        """
        Refresh and return whether ADB mDNS discovery is available.

        This preflight is advisory: startup should continue even when the check is
        unsupported, returns an unknown output shape, or fails on the host.
        """
        command = AdbCommands.MDNS_CHECK
        try:
            result = self._execute(command.invoke())
        except AdbServerException as exc:
            logger.warning(
                "ADB mDNS availability could not be checked",
                error=str(exc),
            )
            self._mdns_available = False
            return self._mdns_available
        if result.status != AdbCommandResultStatus.SUCCESS:
            logger.warning(
                "ADB mDNS availability check returned a non-success result",
                status=result.status.name,
                return_code=result.return_code,
                stdout=_log_safe_output_preview(result.output, command),
                stderr=_log_safe_output_preview(result.error, command),
            )
            self._mdns_available = False
            return self._mdns_available
        self._mdns_available = command.parse(result.output or "")
        logger.debug("ADB mDNS availability refreshed", available=self._mdns_available)
        return self._mdns_available

    def refresh_network_availability(self) -> bool:
        """Refresh and return whether the host has a usable IPv4 network route."""
        _ip, self._network_available = resolve_network_identity()
        logger.debug(
            "Host network availability refreshed",
            available=self._network_available,
        )
        return self._network_available

    def is_server_running(self) -> bool:
        """
        Return the last known server lifecycle state without issuing a new ADB command.

        Preflight checks call this method before operations such as refresh/pair/close.
        Using ``adb start-server`` here would mutate daemon state during a read-only guard,
        so this method only inspects the recorded lifecycle command history.
        """
        for command, result in self._history_manager.entries_newest_first():
            if command == AdbCommands.KILL_SERVER:
                return result.status == AdbCommandResultStatus.ERROR
            if command == AdbCommands.START_SERVER:
                return result.status == AdbCommandResultStatus.SUCCESS
        logger.warning("ADB server state is unknown because lifecycle history is empty")
        return False

    def get_known_devices(self) -> list[Phone]:
        """Get the known devices."""
        command = AdbCommands.GET_DEVICES
        try:
            result = self._execute(command.invoke())
            raise_server_for_result(command, result)
        except AdbServerException as e:
            raise AdbClientException(f"Failed to get known devices: {e}") from e
        return command.parse(result.output or "")

    def _execute(self, invocation: AdbCommandInvocation[object]) -> AdbCommandResult:
        """
        Execute a command with Tenacity-backed retries on transient subprocess failures.
        """
        command = invocation.spec
        result = self._executor.execute(
            invocation,
            scope="server",
        )
        self.add_to_history(command, result)
        return result
