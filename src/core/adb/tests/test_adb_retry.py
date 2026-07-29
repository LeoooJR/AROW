"""
Unit tests for Tenacity-backed ADB subprocess retries (no real adb device required).
"""

from __future__ import annotations

import subprocess
from collections import OrderedDict
from pathlib import Path

import pytest
from tenacity import stop_after_attempt, wait_none

from core.adb.binary import AdbBinary
from core.adb.client import AdbClient
from core.adb.command import (
    AdbCommand,
    AdbCommandResult,
    AdbCommandResultStatus,
    AdbCommands,
)
from core.adb.exceptions import AdbClientException, AdbServerException
from core.adb.retry import (
    _AdbRetryProfile,
    _is_retryable_adb_exception,
    retry_profile_for,
)
from core.adb.server import AdbServer
from core.devices.phone import Phone, PhoneRepository


def _fast_profile(command: AdbCommand, *, scope: str) -> _AdbRetryProfile:
    """Deterministic retry profile for tests: three attempts, no sleep."""
    cmd = command.command
    if cmd == "pair":
        timeout_seconds = 15.0
    elif cmd == "kill-server":
        timeout_seconds = 5.0
    elif cmd in ("start-server", "get-state", "devices"):
        timeout_seconds = 10.0
    else:
        timeout_seconds = 8.0
    return _AdbRetryProfile(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        timeout_seconds=timeout_seconds,
    )


@pytest.fixture
def adb_client(monkeypatch: pytest.MonkeyPatch) -> AdbClient:
    """AdbClient with a dummy binary path and fast retry profile."""
    monkeypatch.setattr(
        "core.adb.retry.retry_profile_for",
        _fast_profile,
    )
    client = AdbClient(AdbBinary(path=Path("/mock/adb")))
    return client


@pytest.fixture
def adb_server(monkeypatch: pytest.MonkeyPatch) -> AdbServer:
    """AdbServer built without __init__ side effects and fast retry profile."""
    monkeypatch.setattr(
        "core.adb.retry.retry_profile_for",
        _fast_profile,
    )
    server = object.__new__(AdbServer)
    server.binary = AdbBinary(path=Path("/mock/adb"))
    server._history = OrderedDict()
    server.paired_devices = PhoneRepository()
    return server


def _completed_process(
    argv: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


class TestIsRetryableAdbException:
    """Predicate tests for transient vs permanent ADB failures."""

    @pytest.mark.parametrize(
        "message",
        [
            "protocol fault: connection reset",
            "device offline",
            "daemon not running",
            "connection refused",
            "timed out after 8.0s",
        ],
    )
    def test_retryable_messages(self, message: str) -> None:
        assert _is_retryable_adb_exception(AdbClientException(message)) is True
        assert _is_retryable_adb_exception(AdbServerException(message)) is True

    @pytest.mark.parametrize(
        "message",
        [
            "wrong pairing code",
            "unauthorized",
            "permission denied",
            "failed to authenticate",
        ],
    )
    def test_permanent_messages(self, message: str) -> None:
        assert _is_retryable_adb_exception(AdbClientException(message)) is False

    def test_oserror_is_not_retryable(self) -> None:
        assert (
            _is_retryable_adb_exception(OSError("No such file or directory")) is False
        )

    def test_missing_binary_message_is_not_retryable(self) -> None:
        exc = AdbClientException("Failed to run ADB binary /mock/adb")
        assert _is_retryable_adb_exception(exc) is False


class TestAdbClientExecuteRetry:
    """Retry integration for AdbClient._execute via monkeypatched subprocess.run."""

    def test_targeted_success_does_not_probe_devices(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            return _completed_process(argv, returncode=0, stdout="Pixel\n")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = adb_client._execute(
            AdbCommands.GET_PRODUCT_MODEL.value,
            Phone(id="abc123", state="device"),
        )

        assert result.status == AdbCommandResultStatus.SUCCESS
        assert len(calls) == 1
        assert calls[0][1:3] == ["-s", "abc123"]

    def test_transient_failure_retries_then_succeeds(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls["count"] += 1
            if calls["count"] < 3:
                return _completed_process(
                    argv,
                    returncode=1,
                    stderr="protocol fault: connection reset",
                )
            return _completed_process(argv, returncode=0, stdout="ok\n")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = adb_client._execute(AdbCommands.GET_DEVICES.value)
        assert calls["count"] == 3
        assert result.status == AdbCommandResultStatus.SUCCESS
        assert result.return_code == 0
        assert result.output == "ok\n"

    def test_targeted_transient_exhaustion_probes_once_and_reports_state(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            if argv[1] == "devices":
                return _completed_process(
                    argv,
                    returncode=0,
                    stdout="List of devices attached\nabc123 offline\n",
                )
            return _completed_process(
                argv,
                returncode=1,
                stderr="device offline",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = adb_client._execute(
            AdbCommands.GET_PRODUCT_MODEL.value,
            Phone(id="abc123", state="device"),
        )

        assert result.status == AdbCommandResultStatus.TRANSIENT_ERROR
        assert len(calls) == 4
        assert sum(argv[1] == "devices" for argv in calls) == 1
        assert "device offline" in result.error
        assert (
            "target device remains listed by ADB with state 'offline'" in result.error
        )
        assert [entry[0] for entry in adb_client.history.values()] == [
            AdbCommands.GET_PRODUCT_MODEL.value,
            AdbCommands.GET_DEVICES.value,
        ]

    def test_targeted_terminal_failure_probes_once_and_reports_state(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            if argv[1] == "devices":
                return _completed_process(
                    argv,
                    returncode=0,
                    stdout="List of devices attached\nabc123 unauthorized\n",
                )
            return _completed_process(
                argv,
                returncode=1,
                stderr="permission denied",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = adb_client._execute(
            AdbCommands.SEND_NOTIFICATION.value,
            Phone(id="abc123", state="device"),
            ["-t", "Title", "-m", "Message"],
        )

        assert result.status == AdbCommandResultStatus.ERROR
        assert len(calls) == 2
        assert "permission denied" in result.error
        assert (
            "target device remains listed by ADB with state 'unauthorized'"
            in result.error
        )

    def test_public_client_exception_includes_device_diagnostic(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            if argv[1] == "devices":
                return _completed_process(
                    argv,
                    returncode=0,
                    stdout="List of devices attached\nabc123 unauthorized\n",
                )
            return _completed_process(
                argv,
                returncode=1,
                stderr="permission denied",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(
            AdbClientException,
            match="target device remains listed by ADB with state 'unauthorized'",
        ):
            adb_client.status(Phone(id="abc123", state="device"))

    def test_targeted_failure_reports_device_is_no_longer_listed(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            if argv[1] == "devices":
                return _completed_process(
                    argv,
                    returncode=0,
                    stdout=(
                        "List of devices attached\n"
                        "another-device device product:x model:y device:z "
                        "transport_id:1\n"
                    ),
                )
            return _completed_process(
                argv,
                returncode=1,
                stderr="permission denied",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = adb_client._execute(
            AdbCommands.GET_PRODUCT_MODEL.value,
            Phone(id="abc123", state="device"),
        )

        assert "target device is no longer listed by ADB" in result.error
        assert "another-device" not in result.error

    def test_failed_device_probe_does_not_mask_original_failure(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            if argv[1] == "devices":
                return _completed_process(
                    argv,
                    returncode=1,
                    stderr="unauthorized",
                )
            return _completed_process(
                argv,
                returncode=1,
                stderr="permission denied",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = adb_client._execute(
            AdbCommands.GET_PRODUCT_MODEL.value,
            Phone(id="abc123", state="device"),
        )

        assert len(calls) == 2
        assert result.status == AdbCommandResultStatus.ERROR
        assert result.error.startswith("permission denied")
        assert (
            "target device reference could not be determined "
            "(ADB device-list check returned ERROR)" in result.error
        )

    def test_permanent_failure_is_not_retried(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls["count"] += 1
            return _completed_process(argv, returncode=1, stderr="wrong pairing code")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = adb_client._execute(
            AdbCommands.PAIR.value,
            None,
            ["127.0.0.1:5555", "000000"],
        )
        assert calls["count"] == 1
        assert result.status == AdbCommandResultStatus.ERROR
        assert result.error == "wrong pairing code"

    def test_oserror_is_not_retried(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls["count"] += 1
            raise OSError("No such file or directory")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(AdbClientException, match="Failed to run ADB binary"):
            adb_client._execute(AdbCommands.GET_DEVICES.value)
        assert calls["count"] == 1

    def test_targeted_oserror_preserves_exception_chain_after_failed_probe(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls["count"] += 1
            raise OSError("No such file or directory")

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(AdbClientException) as exc_info:
            adb_client._execute(
                AdbCommands.GET_PRODUCT_MODEL.value,
                Phone(id="abc123", state="device"),
            )

        assert calls["count"] == 2
        assert "Failed to run ADB binary" in str(exc_info.value)
        assert "target device reference could not be determined" in str(exc_info.value)
        original_error = exc_info.value.__cause__
        assert isinstance(original_error, AdbClientException)
        assert isinstance(original_error.__cause__, OSError)

    def test_timeout_is_retried_then_reraises(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls["count"] += 1
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = adb_client._execute(AdbCommands.GET_DEVICES.value)
        assert calls["count"] == 3
        assert result.status == AdbCommandResultStatus.TIMEOUT
        assert "timed out" in result.error

    def test_pair_raises_from_non_success_result(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_execute(
            command: AdbCommand,
            phone: Phone | None = None,
            positional_arguments: list[str] | None = None,
        ) -> AdbCommandResult:
            return AdbCommandResult(
                status=AdbCommandResultStatus.ERROR,
                output="",
                error="wrong pairing code",
                return_code=1,
            )

        monkeypatch.setattr(adb_client, "_execute", fake_execute)
        with pytest.raises(AdbClientException, match="wrong pairing code"):
            adb_client.pair("127.0.0.1", 5555, "000000")

    def test_shell_getter_returns_empty_from_non_success_result(
        self, adb_client: AdbClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_execute(command: AdbCommand, phone: Phone) -> AdbCommandResult:
            return AdbCommandResult(
                status=AdbCommandResultStatus.TRANSIENT_ERROR,
                output="",
                error="device offline",
                return_code=1,
            )

        monkeypatch.setattr(adb_client, "_execute", fake_execute)
        assert adb_client.get_product_model(Phone(id="abc123", state="device")) == ""


class TestAdbServerExecuteRetry:
    """Retry integration for AdbServer._execute via monkeypatched subprocess.run."""

    def test_transient_failure_retries_then_succeeds(
        self, adb_server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls["count"] += 1
            if calls["count"] < 2:
                return _completed_process(
                    argv, returncode=1, stderr="daemon not running"
                )
            return _completed_process(
                argv, returncode=0, stdout="daemon started successfully\n"
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = adb_server._execute(AdbCommands.START_SERVER.value)
        assert calls["count"] == 2
        assert result.status == AdbCommandResultStatus.SUCCESS
        assert result.return_code == 0
        assert "daemon started successfully" in result.output

    def test_permanent_failure_is_not_retried(
        self, adb_server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls["count"] += 1
            return _completed_process(argv, returncode=1, stderr="unauthorized")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = adb_server._execute(AdbCommands.GET_DEVICES.value)
        assert calls["count"] == 1
        assert result.status == AdbCommandResultStatus.ERROR
        assert result.error == "unauthorized"

    def test_retryable_failure_exhaustion_returns_transient_error(
        self, adb_server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}

        def fake_run(
            argv: list[str],
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            calls["count"] += 1
            return _completed_process(argv, returncode=1, stderr="device offline")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = adb_server._execute(AdbCommands.GET_DEVICES.value)
        assert calls["count"] == 3
        assert result.status == AdbCommandResultStatus.TRANSIENT_ERROR
        assert result.error == "device offline"


class TestRetryProfiles:
    """Sanity checks for command-specific retry boundaries."""

    def test_pair_profile_has_wider_window_than_shell(self) -> None:
        pair = retry_profile_for(AdbCommands.PAIR.value, scope="client")
        shell = retry_profile_for(AdbCommands.GET_SERIAL_NO.value, scope="client")
        assert pair.timeout_seconds >= shell.timeout_seconds

    def test_kill_server_profile_is_minimal(self) -> None:
        kill = retry_profile_for(AdbCommands.KILL_SERVER.value, scope="server")
        start = retry_profile_for(AdbCommands.START_SERVER.value, scope="server")
        assert kill.timeout_seconds <= start.timeout_seconds
