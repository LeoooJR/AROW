"""
Tests for src/core/adb.py: ADB server commands (start-server, kill-server) only.
Success and error cases, with pytest markers.
"""

from __future__ import annotations

import subprocess
from collections import OrderedDict
from pathlib import Path

import pytest

from core.adb import (
    AdbBinary,
    AdbCommand,
    AdbCommandResult,
    AdbCommandResultStatus,
    AdbCommands,
    AdbServer,
)
from core.devices import Phone, PhoneRepository
from core.exceptions import AdbServerException

pytestmark = [pytest.mark.adb, pytest.mark.adb_server]


# --- Fixtures ---


@pytest.fixture
def adb_binary(adb_binary_path: Path) -> AdbBinary:
    """AdbBinary pointing to the real ADB executable."""
    return AdbBinary(path=adb_binary_path)


@pytest.fixture
def invalid_adb_binary() -> AdbBinary:
    """AdbBinary pointing to a non-existent path (for error tests)."""
    return AdbBinary(path=Path("/nonexistent/path/to/adb"))


@pytest.fixture
def server(adb_binary: AdbBinary) -> AdbServer:
    """Build an AdbServer instance without triggering __init__ side effects."""
    server = object.__new__(AdbServer)
    server.binary = adb_binary
    server._history = OrderedDict()
    server.paired_devices = PhoneRepository()
    return server


def _completed_process(
    argv: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


# --- Start server: success ---


class TestAdbServerStartSuccess:
    """ADB start-server success cases."""

    def test_server_init_calls_restart(
        self, adb_binary: AdbBinary, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AdbServer.__init__ delegates startup to restart()."""
        called: list[AdbBinary] = []

        def fake_restart(self: AdbServer) -> None:
            called.append(self.binary)

        monkeypatch.setattr(AdbServer, "restart", fake_restart)
        server = AdbServer(adb_binary)
        assert server.binary == adb_binary
        assert called == [adb_binary]

    def test_server_start_adds_known_devices(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """start() records the command result and stores known devices."""
        phone = Phone(id="abc123", name="device:Pixel", state="device")

        def fake_execute(command: AdbCommand) -> AdbCommandResult:
            result = AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="",
                error="",
                return_code=0,
            )
            server.add_to_history(command, result)
            return result

        monkeypatch.setattr(server, "_execute", fake_execute)
        monkeypatch.setattr(server, "get_known_devices", lambda: [phone])
        server.start()
        assert server.paired_devices.get("abc123") is phone
        last_result = server.get_last_command_result()
        assert last_result.status == AdbCommandResultStatus.SUCCESS


# --- Kill server: success ---


class TestAdbServerKillSuccess:
    """ADB kill-server success cases."""

    def test_server_kill_success(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Killing the ADB server with a valid binary succeeds."""

        def fake_execute(command: AdbCommand) -> AdbCommandResult:
            result = AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="",
                error="",
                return_code=0,
            )
            server.add_to_history(command, result)
            return result

        monkeypatch.setattr(server, "_execute", fake_execute)
        server.stop()
        last_cmd, last_result = server.get_last_from_history()
        assert last_cmd == AdbCommands.KILL_SERVER.value
        assert last_result.status == AdbCommandResultStatus.SUCCESS

    def test_server_execute_kill_returns_success_status(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Execute kill-server returns a result with SUCCESS status."""

        def fake_run(
            argv: list[str], capture_output: bool, text: bool
        ) -> subprocess.CompletedProcess[str]:
            return _completed_process(argv, returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = server._execute(AdbCommands.KILL_SERVER.value)
        assert result.status == AdbCommandResultStatus.SUCCESS
        assert result.return_code == 0


# --- Start server: error ---


class TestAdbServerStartError:
    """ADB start-server error cases."""

    def test_server_start_fails_when_binary_missing(
        self, invalid_adb_binary: AdbBinary
    ) -> None:
        """Starting the server with a non-existent binary raises AdbServerException."""
        with pytest.raises(
            AdbServerException,
            match="Failed to run ADB binary /nonexistent/path/to/adb",
        ):
            AdbServer(invalid_adb_binary)

    def test_execute_start_server_fails_when_binary_missing(
        self, invalid_adb_binary: AdbBinary
    ) -> None:
        """Execute start-server with invalid binary raises AdbServerException."""
        # Build server without calling restart (avoid __init__ restart)
        server = object.__new__(AdbServer)
        server.binary = invalid_adb_binary
        server._history = OrderedDict()
        server.paired_devices = PhoneRepository()
        with pytest.raises(
            AdbServerException, match="Failed to run ADB binary|Failed to execute"
        ):
            server._execute(AdbCommands.START_SERVER.value)


# --- Kill server: error ---


class TestAdbServerKillError:
    """ADB kill-server error cases."""

    def test_execute_kill_server_fails_when_binary_missing(
        self, invalid_adb_binary: AdbBinary
    ) -> None:
        """Execute kill-server with invalid binary raises AdbServerException."""
        server = object.__new__(AdbServer)
        server.binary = invalid_adb_binary
        server._history = OrderedDict()
        server.paired_devices = PhoneRepository()
        with pytest.raises(
            AdbServerException, match="Failed to run ADB binary|Failed to execute"
        ):
            server._execute(AdbCommands.KILL_SERVER.value)


# --- Execute result shape ---


class TestAdbServerExecuteResult:
    """ADB server _execute() return value and history."""

    def test_execute_start_server_returns_result_with_output(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Execute start-server returns AdbCommandResult with expected fields."""

        def fake_run(
            argv: list[str], capture_output: bool, text: bool
        ) -> subprocess.CompletedProcess[str]:
            return _completed_process(
                argv,
                returncode=0,
                stdout="daemon started successfully\n",
                stderr="",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = server._execute(AdbCommands.START_SERVER.value)
        assert result.status == AdbCommandResultStatus.SUCCESS
        assert result.return_code == 0
        assert result.phone is None
        assert result.time is not None
        assert "daemon started successfully" in result.output

    def test_execute_kill_server_adds_to_history(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Execute kill-server adds an entry to history."""

        def fake_run(
            argv: list[str], capture_output: bool, text: bool
        ) -> subprocess.CompletedProcess[str]:
            return _completed_process(argv, returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        server._execute(AdbCommands.KILL_SERVER.value)
        assert len(server.history) >= 1
        server._execute(AdbCommands.START_SERVER.value)
        assert len(server.history) >= 2

    def test_get_known_devices_skips_malformed_output(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_known_devices ignores blank and malformed lines."""
        output = "\n".join(
            [
                "List of devices attached",
                "abc123 device product:model model:pixel device:Pixel transport_id:1",
                "malformed line",
                "",
            ]
        )

        def fake_execute(_command: AdbCommand) -> AdbCommandResult:
            return AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output=output,
                error="",
                return_code=0,
            )

        monkeypatch.setattr(server, "_execute", fake_execute)
        devices = server.get_known_devices()
        assert [device.descriptor.id for device in devices] == ["abc123"]
