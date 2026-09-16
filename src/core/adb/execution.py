"""Shared ADB command execution orchestration and transport boundary."""

from __future__ import annotations

import datetime

# ADB is an external binary; the concrete transport uses list argv and no shell.
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from core.adb.binary import AdbBinary
from core.adb.command import (
    AdbCommandInvocation,
    AdbCommandResult,
    AdbCommandResultStatus,
    _log_safe_argv,
    _log_safe_command_line,
    _log_safe_output_preview,
    _redacted_log_value,
)
from core.adb.exceptions import AdbClientException, AdbException, AdbServerException
from core.adb.retry import (
    adb_status_from_process,
    adb_status_from_timeout,
    execute_with_adb_retry,
    timeout_seconds_for,
)
from core.devices.phone import Phone
from logger import logger

AdbTransportScope = Literal["client", "server"]


@dataclass(frozen=True, slots=True)
class AdbTransportResult:
    """Raw process-shaped output returned by an ADB transport."""

    output: str = ""
    error: str = ""
    return_code: int = 0


class AdbTransportFailure(Exception):
    """Internal transport failure translated at the execution boundary."""


class AdbTransport(Protocol):
    """Backend capable of performing one bounded ADB command attempt."""

    log_label: str

    def run(
        self,
        invocation: AdbCommandInvocation[object],
        *,
        binary_path: Path,
        scope: AdbTransportScope,
        phone: Phone | None,
        timeout_seconds: float,
    ) -> AdbTransportResult:
        """Perform one attempt and return process-shaped output."""


class SubprocessAdbTransport:
    """Execute ADB through the local subprocess boundary."""

    log_label = "ADB"

    def run(
        self,
        invocation: AdbCommandInvocation[object],
        *,
        binary_path: Path,
        scope: AdbTransportScope,
        phone: Phone | None,
        timeout_seconds: float,
    ) -> AdbTransportResult:
        """Execute one ADB subprocess attempt.

        Args:
            invocation: Bound command invocation to execute.
            binary_path: Filesystem path of the ADB binary.
            scope: Client or server scope, unused by this transport.
            phone: Optional target phone for device-scoped commands.
            timeout_seconds: Maximum subprocess duration in seconds.

        Returns:
            Captured subprocess output and return code.

        Raises:
            subprocess.TimeoutExpired: If the command exceeds its timeout.
            OSError: If the subprocess cannot be started.
        """
        del scope
        argv = invocation.argv(
            binary_path,
            device_id=phone.descriptor.id if phone is not None else None,
        )
        completed = subprocess.run(  # nosec B603
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return AdbTransportResult(
            output=completed.stdout or "",
            error=completed.stderr or "",
            return_code=completed.returncode,
        )


class AdbCommandExecutor:
    """Run ADB invocations through one retry, logging, and result pipeline."""

    def __init__(
        self,
        binary: AdbBinary,
        *,
        transport: AdbTransport | None = None,
    ) -> None:
        """Initialize an executor for a binary and transport.

        Args:
            binary: ADB binary metadata used for command execution.
            transport: Command transport, or ``None`` for subprocess execution.
        """
        self._binary = binary
        self._transport = transport or SubprocessAdbTransport()

    @property
    def binary(self) -> AdbBinary:
        """Return the binary bound to this executor."""
        return self._binary

    @property
    def transport(self) -> AdbTransport:
        """Return the transport bound to this executor."""
        return self._transport

    def execute(
        self,
        invocation: AdbCommandInvocation[object],
        *,
        scope: AdbTransportScope,
        phone: Phone | None = None,
    ) -> AdbCommandResult:
        """Execute an invocation using its declared retry policy."""

        def _attempt(timeout_seconds: float) -> AdbCommandResult:
            return self._execute_once(
                invocation,
                scope=scope,
                phone=phone,
                timeout_seconds=timeout_seconds,
            )

        return execute_with_adb_retry(
            invocation.spec,
            scope=scope,
            phone_id=phone.descriptor.id if phone is not None else None,
            attempt=_attempt,
        )

    def execute_once(
        self,
        invocation: AdbCommandInvocation[object],
        *,
        scope: AdbTransportScope,
        phone: Phone | None = None,
    ) -> AdbCommandResult:
        """Execute exactly one invocation attempt without applying retries."""
        return self._execute_once(
            invocation,
            scope=scope,
            phone=phone,
            timeout_seconds=timeout_seconds_for(invocation.spec),
        )

    def _execute_once(
        self,
        invocation: AdbCommandInvocation[object],
        *,
        scope: AdbTransportScope,
        phone: Phone | None,
        timeout_seconds: float,
    ) -> AdbCommandResult:
        command = invocation.spec
        phone_id = phone.descriptor.id if phone is not None else None
        event_prefix = f"{self._transport.log_label} {scope} command"
        logger.debug(
            f"{event_prefix} started",
            adb_path=str(self._binary.path),
            command=command.argv[0],
            phone_id=_redacted_log_value(phone_id),
            argv=_log_safe_argv(
                invocation,
                self._binary.path,
                device_id=phone_id,
            ),
            command_line=_log_safe_command_line(
                invocation,
                self._binary.path,
                device_id=phone_id,
            ),
            timeout_s=timeout_seconds,
        )
        try:
            completed = self._transport.run(
                invocation,
                binary_path=self._binary.path,
                scope=scope,
                phone=phone,
                timeout_seconds=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            error = f"timed out after {timeout_seconds}s"
            logger.debug(
                f"{event_prefix} timed out",
                adb_path=str(self._binary.path),
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
            raise self._exception_for_scope(
                scope,
                f"Failed to execute command: {command.argv}",
            ) from exc
        except OSError as exc:
            raise self._exception_for_scope(
                scope,
                f"Failed to run ADB binary {self._binary.path}",
            ) from exc
        except AdbTransportFailure as exc:
            raise self._exception_for_scope(scope, str(exc)) from exc

        logger.debug(
            f"{event_prefix} completed",
            adb_path=str(self._binary.path),
            command=command.argv[0],
            phone_id=_redacted_log_value(phone_id),
            return_code=completed.return_code,
            stdout=_log_safe_output_preview(completed.output.strip(), command),
            stderr=_log_safe_output_preview(completed.error.strip(), command),
        )
        return AdbCommandResult(
            status=adb_status_from_process(
                return_code=completed.return_code,
                output=completed.output,
                error=completed.error,
            ),
            phone=phone,
            time=datetime.datetime.now(),
            output=completed.output,
            error=completed.error,
            return_code=completed.return_code,
        )

    @staticmethod
    def _exception_for_scope(scope: AdbTransportScope, message: str) -> AdbException:
        if scope == "client":
            return AdbClientException(message)
        return AdbServerException(message)
