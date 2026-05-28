"""
Unit tests for Tenacity-backed ADB subprocess retries (no real adb device required).
"""

from __future__ import annotations

import subprocess
from collections import OrderedDict
from pathlib import Path

import pytest
from tenacity import stop_after_attempt, wait_none

from core.adb import (
    AdbBinary,
    AdbClient,
    AdbCommand,
    AdbCommands,
    AdbServer,
    _AdbRetryProfile,
    _is_retryable_adb_exception,
    _retry_profile_for,
)
from core.devices import PhoneRepository
from core.exceptions import AdbClientException, AdbServerException


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
        "core.adb._retry_profile_for",
        _fast_profile,
    )
    client = AdbClient(AdbBinary(path=Path("/mock/adb")))
    return client


@pytest.fixture
def adb_server(monkeypatch: pytest.MonkeyPatch) -> AdbServer:
    """AdbServer built without __init__ side effects and fast retry profile."""
    monkeypatch.setattr(
        "core.adb._retry_profile_for",
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
        assert result.return_code == 0
        assert result.output == "ok\n"

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
        with pytest.raises(AdbClientException, match="wrong pairing code"):
            adb_client._execute(
                AdbCommands.PAIR.value,
                None,
                ["127.0.0.1:5555", "000000"],
            )
        assert calls["count"] == 1

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
        with pytest.raises(AdbClientException, match="timed out"):
            adb_client._execute(AdbCommands.GET_DEVICES.value)
        assert calls["count"] == 3


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
        with pytest.raises(AdbServerException, match="unauthorized"):
            adb_server._execute(AdbCommands.GET_DEVICES.value)
        assert calls["count"] == 1


class TestRetryProfiles:
    """Sanity checks for command-specific retry boundaries."""

    def test_pair_profile_has_wider_window_than_shell(self) -> None:
        pair = _retry_profile_for(AdbCommands.PAIR.value, scope="client")
        shell = _retry_profile_for(AdbCommands.GET_SERIAL_NO.value, scope="client")
        assert pair.timeout_seconds >= shell.timeout_seconds

    def test_kill_server_profile_is_minimal(self) -> None:
        kill = _retry_profile_for(AdbCommands.KILL_SERVER.value, scope="server")
        start = _retry_profile_for(AdbCommands.START_SERVER.value, scope="server")
        assert kill.timeout_seconds <= start.timeout_seconds
