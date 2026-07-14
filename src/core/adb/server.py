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
    AdbCommandResultStatus,
    AdbCommands,
    _is_retryable_adb_exception,
    _is_retryable_adb_result,
    _log_safe_argv,
    _log_safe_command_line,
    _log_safe_output_preview,
    adb_status_from_process,
    adb_status_from_timeout,
    make_adb_retry_after,
    make_adb_retry_before,
    raise_server_for_result,
    retry_profile_for,
    return_last_adb_retry_outcome,
)
from core.adb.exceptions import AdbClientException, AdbServerException
from core.devices.phone import Phone, PhoneRepository
from logger import logger


class AdbServer:
    """ADB Server."""

    def __init__(self, binary: AdbBinary):
        self.binary = binary
        self._history: OrderedDict[
            datetime.datetime, tuple[AdbCommand, AdbCommandResult]
        ] = OrderedDict()
        self._paired_devices: PhoneRepository = PhoneRepository()
        self._mdns_available: bool = False
        self.start()
        self.refresh_mdns_availability()

    @property
    def history(
        self,
    ) -> OrderedDict[datetime.datetime, tuple[AdbCommand, AdbCommandResult]]:
        """Get the history of the adb server."""
        return self._history

    @history.setter
    def history(
        self,
        history: OrderedDict[datetime.datetime, tuple[AdbCommand, AdbCommandResult]],
    ) -> None:
        """Set the history of the adb server."""
        self._history = history

    @history.deleter
    def history(self) -> None:
        """Delete the history of the adb server."""
        self._history.clear()

    def add_to_history(self, command: AdbCommand, result: AdbCommandResult) -> None:
        """Add to the history of the adb server."""
        self._history[datetime.datetime.now()] = (command, result)
        self._prune_history()

    def _prune_history(self) -> None:
        """Keep newest server history entries by dropping oldest entries first."""
        while len(self._history) > ADB_HISTORY_MAX_ENTRIES:
            self._history.popitem(last=False)

    def remove_from_history(self, command: AdbCommand) -> None:
        """Remove from the history of the adb server."""
        self._history = OrderedDict(
            (time, entry)
            for time, entry in self._history.items()
            if entry[0] != command
        )

    def get_last_command_time(self) -> datetime.datetime:
        """Get the time of the last command."""
        return next(reversed(self.history))

    def get_last_from_history(self) -> tuple[AdbCommand, AdbCommandResult]:
        """Get the last command and result."""
        return self.history[self.get_last_command_time()]

    def get_last_command(self) -> AdbCommand:
        """Get the last command."""
        return self.get_last_from_history()[0]

    def get_last_command_result(self) -> AdbCommandResult:
        """Get the last command result."""
        return self.get_last_from_history()[1]

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
                "AdbServer: failed to set working device",
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

    def start(self) -> None:
        """Start the adb server."""
        command = AdbCommands.START_SERVER.value
        result = self._execute(command)
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to start adb server: {result}")
        # Get known devices
        for device in self.get_known_devices():
            self._paired_devices.add(device)

    def stop(self) -> None:
        """Stop the adb server."""
        command = AdbCommands.KILL_SERVER.value
        result = self._execute(command)
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
    def get_binary_version(cls, binary: AdbBinary) -> AdbBinary:
        """
        Read ADB binary metadata without constructing or starting the ADB server.
        """
        command = AdbCommands.GET_BINARY_VERSION.value
        argv = [str(binary.path), command.command, *command.args]
        profile = retry_profile_for(command, scope="server")
        logger.debug(
            "AdbServer: reading ADB binary version",
            adb_path=str(binary.path),
            argv=_log_safe_argv(command, argv),
            command_line=_log_safe_command_line(command, argv),
            timeout_s=profile.timeout_seconds,
        )
        try:
            # Version preflight uses list argv, no shell, and a bounded timeout.
            completed = subprocess.run(  # nosec B603
                argv,
                capture_output=True,
                text=True,
                timeout=profile.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdbServerException(
                f"Failed to read ADB binary version: timed out after {profile.timeout_seconds}s"
            ) from exc
        except OSError as exc:
            raise AdbServerException(f"Failed to run ADB binary {binary.path}") from exc
        result = AdbCommandResult(
            status=adb_status_from_process(
                return_code=completed.returncode,
                output=completed.stdout or "",
                error=completed.stderr or "",
            ),
            output=completed.stdout or "",
            error=completed.stderr or "",
            return_code=completed.returncode,
        )
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(
                f"Failed to read ADB binary version: {result.status.name}"
            )
        parsed = ADBCommandParser.GET_BINARY_VERSION.parse(result.output or "")
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
        command = AdbCommands.MDNS_CHECK.value
        try:
            result = self._execute(command)
        except AdbServerException as exc:
            logger.warning(
                "AdbServer: failed to check mDNS availability",
                error=str(exc),
            )
            self._mdns_available = False
            return self._mdns_available
        if result.status != AdbCommandResultStatus.SUCCESS:
            logger.warning(
                "AdbServer: mDNS availability check returned non-success",
                status=result.status.name,
                return_code=result.return_code,
                stdout=_log_safe_output_preview(result.output, command),
                stderr=_log_safe_output_preview(result.error, command),
            )
            self._mdns_available = False
            return self._mdns_available
        self._mdns_available = ADBCommandParser.MDNS_CHECK.parse(result.output or "")
        logger.debug(
            "AdbServer: mDNS availability refreshed", available=self._mdns_available
        )
        return self._mdns_available

    def is_server_running(self) -> bool:
        """
        Return the last known server lifecycle state without issuing a new ADB command.

        Preflight checks call this method before operations such as refresh/pair/close.
        Using ``adb start-server`` here would mutate daemon state during a read-only guard,
        so this method only inspects the recorded lifecycle command history.
        """
        for command, result in reversed(self.history.values()):
            if command == AdbCommands.KILL_SERVER.value:
                return result.status == AdbCommandResultStatus.ERROR
            if command == AdbCommands.START_SERVER.value:
                return result.status == AdbCommandResultStatus.SUCCESS
        logger.warning("AdbServer: server running state unknown (no lifecycle history)")
        return False

    def get_known_devices(self) -> list[Phone]:
        """Get the known devices."""
        command = AdbCommands.GET_DEVICES.value
        try:
            result = self._execute(command)
            raise_server_for_result(command, result)
        except AdbServerException as e:
            raise AdbClientException(f"Failed to get known devices: {e}") from e
        return ADBCommandParser.GET_DEVICES.parse(result.output or "")

    def _execute(self, command: AdbCommand) -> AdbCommandResult:
        """
        Execute a command with Tenacity-backed retries on transient subprocess failures.
        """
        argv: list[str] = [str(self.binary.path), command.command, *command.args]
        profile = retry_profile_for(command, scope="server")

        def _attempt() -> AdbCommandResult:
            logger.debug(
                "AdbServer: executing command",
                adb_path=str(self.binary.path),
                command=command.command,
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
                    "AdbServer: command timed out",
                    adb_path=str(self.binary.path),
                    command=command.command,
                    error=error,
                )
                return AdbCommandResult(
                    status=adb_status_from_timeout(),
                    phone=None,
                    time=datetime.datetime.now(),
                    output=exc.output or "",
                    error=error,
                    return_code=1,
                )
            except subprocess.CalledProcessError as exc:
                raise AdbServerException(
                    f"Failed to execute command: {command.command} {command.args}"
                ) from exc
            except OSError as exc:
                raise AdbServerException(
                    f"Failed to run ADB binary {self.binary.path}"
                ) from exc
            logger.debug(
                "AdbServer: command completed",
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
                phone=None,
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
                scope="server", command_name=command.command, phone_id=None
            ),
            after=make_adb_retry_after(
                scope="server", command_name=command.command, phone_id=None
            ),
            retry_error_callback=return_last_adb_retry_outcome,
        )
        result = retryer(_attempt)
        self.add_to_history(command, result)
        return result
