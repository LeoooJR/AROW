"""Tests for shared ADB command execution orchestration."""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from core.adb.binary import AdbBinary
from core.adb.client import AdbClient
from core.adb.command import AdbCommandInvocation, AdbCommandResultStatus, AdbCommands
from core.adb.exceptions import AdbClientException, AdbServerException
from core.adb.execution import (
    AdbCommandExecutor,
    AdbTransportResult,
    AdbTransportScope,
)
from core.adb.server import AdbServer
from core.devices.phone import Phone


class ScriptedTransport:
    """Deterministic transport double that records executor inputs."""

    log_label = "Test ADB"

    def __init__(self, *outcomes: AdbTransportResult | BaseException) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[
            tuple[
                AdbCommandInvocation[object],
                Path,
                AdbTransportScope,
                Phone | None,
                float,
            ]
        ] = []

    def run(
        self,
        invocation: AdbCommandInvocation[object],
        *,
        binary_path: Path,
        scope: AdbTransportScope,
        phone: Phone | None,
        timeout_seconds: float,
    ) -> AdbTransportResult:
        self.calls.append((invocation, binary_path, scope, phone, timeout_seconds))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_execute_once_delegates_complete_context_and_builds_result() -> None:
    transport = ScriptedTransport(
        AdbTransportResult(output="device\n", error="", return_code=0)
    )
    binary = AdbBinary(path=Path("/mock/adb"))
    executor = AdbCommandExecutor(binary=binary, transport=transport)
    phone = Phone(id="device-123", state="device")
    invocation = AdbCommands.STATUS.invoke()

    result = executor.execute_once(invocation, scope="client", phone=phone)

    assert result.status is AdbCommandResultStatus.SUCCESS
    assert result.output == "device\n"
    assert result.phone is phone
    assert transport.calls == [(invocation, binary.path, "client", phone, 10.0)]


def test_facade_constructors_do_not_accept_an_executor() -> None:
    assert "executor" not in inspect.signature(AdbClient).parameters
    assert "executor" not in inspect.signature(AdbServer).parameters


def test_execute_once_classifies_timeout_without_retrying() -> None:
    invocation = AdbCommands.GET_DEVICES.invoke()
    timeout = subprocess.TimeoutExpired(
        cmd=invocation.argv(Path("/mock/adb")),
        timeout=10.0,
        output="partial output",
    )
    transport = ScriptedTransport(timeout)
    executor = AdbCommandExecutor(
        binary=AdbBinary(path=Path("/mock/adb")), transport=transport
    )

    result = executor.execute_once(invocation, scope="server")

    assert result.status is AdbCommandResultStatus.TIMEOUT
    assert result.output == "partial output"
    assert result.error == "timed out after 10.0s"
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("scope", "expected_exception"),
    [("client", AdbClientException), ("server", AdbServerException)],
)
def test_execute_once_translates_oserror_for_scope(
    scope: AdbTransportScope,
    expected_exception: type[AdbClientException] | type[AdbServerException],
) -> None:
    transport = ScriptedTransport(OSError("missing"))
    executor = AdbCommandExecutor(
        binary=AdbBinary(path=Path("/mock/adb")), transport=transport
    )

    with pytest.raises(expected_exception, match="Failed to run ADB binary /mock/adb"):
        executor.execute_once(AdbCommands.GET_DEVICES.invoke(), scope=scope)


def test_execute_once_translates_called_process_error() -> None:
    invocation = AdbCommands.GET_DEVICES.invoke()
    transport = ScriptedTransport(
        subprocess.CalledProcessError(
            returncode=1,
            cmd=invocation.argv(Path("/mock/adb")),
        )
    )
    executor = AdbCommandExecutor(
        binary=AdbBinary(path=Path("/mock/adb")), transport=transport
    )

    with pytest.raises(AdbServerException, match="Failed to execute command"):
        executor.execute_once(invocation, scope="server")


def test_execute_retries_transient_results() -> None:
    transport = ScriptedTransport(
        AdbTransportResult(output="", error="device offline", return_code=1),
        AdbTransportResult(output="ready\n", error="", return_code=0),
    )
    executor = AdbCommandExecutor(
        binary=AdbBinary(path=Path("/mock/adb")), transport=transport
    )

    result = executor.execute(AdbCommands.GET_DEVICES.invoke(), scope="server")

    assert result.status is AdbCommandResultStatus.SUCCESS
    assert result.output == "ready\n"
    assert len(transport.calls) == 2
