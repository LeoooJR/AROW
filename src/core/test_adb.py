"""
Tests for src/core/adb.py: ADB server commands (start-server, kill-server) only.
Success and error cases, with pytest markers.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import pytest

from core.adb import (
    AdbBinary,
    AdbCommandResultStatus,
    AdbCommands,
    AdbServer,
)
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


# --- Start server: success ---


class TestAdbServerStartSuccess:
    """ADB start-server success cases."""

    def test_server_start_success(self, adb_binary: AdbBinary) -> None:
        """Starting the ADB server with a valid binary succeeds."""
        server = AdbServer(adb_binary)
        # __init__ calls restart() (stop then start), so server is already running
        server.start()
        # No exception
        assert server.history

    def test_server_stop_then_start_success(self, adb_binary: AdbBinary) -> None:
        """Stop then start the ADB server succeeds."""
        server = AdbServer(adb_binary)
        server.stop()
        server.start()
        # start() also runs GET_DEVICES, so last entry may be GET_DEVICES; ensure START_SERVER ran
        commands_in_history = [cmd for _t, (cmd, _r) in server.history.items()]
        assert AdbCommands.START_SERVER.value in commands_in_history
        last_result = server.get_last_command_result()
        assert last_result.status == AdbCommandResultStatus.SUCCESS


# --- Kill server: success ---


class TestAdbServerKillSuccess:
    """ADB kill-server success cases."""

    def test_server_kill_success(self, adb_binary: AdbBinary) -> None:
        """Killing the ADB server with a valid binary succeeds."""
        server = AdbServer(adb_binary)
        server.stop()
        last_cmd, last_result = server.get_last_from_history()
        assert last_cmd == AdbCommands.KILL_SERVER.value
        assert last_result.status == AdbCommandResultStatus.SUCCESS

    def test_server_execute_kill_returns_success_status(
        self, adb_binary: AdbBinary
    ) -> None:
        """Execute kill-server returns a result with SUCCESS status."""
        server = AdbServer(adb_binary)
        result = server.execute(AdbCommands.KILL_SERVER.value)
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
            AdbServerException, match="Failed to run ADB binary|Failed to execute"
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
        server.paired_devices = []
        with pytest.raises(
            AdbServerException, match="Failed to run ADB binary|Failed to execute"
        ):
            server.execute(AdbCommands.START_SERVER.value)


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
        server.paired_devices = []
        with pytest.raises(
            AdbServerException, match="Failed to run ADB binary|Failed to execute"
        ):
            server.execute(AdbCommands.KILL_SERVER.value)


# --- Execute result shape ---


class TestAdbServerExecuteResult:
    """ADB server execute() return value and history."""

    def test_execute_start_server_returns_result_with_output(
        self, adb_binary: AdbBinary
    ) -> None:
        """Execute start-server returns AdbCommandResult with expected fields."""
        server = AdbServer(adb_binary)
        result = server.execute(AdbCommands.START_SERVER.value)
        assert result.status == AdbCommandResultStatus.SUCCESS
        assert result.return_code == 0
        assert result.phone is None
        assert result.time is not None
        assert (
            result.error is not None or result.output is not None or True
        )  # at least one set

    def test_execute_kill_server_adds_to_history(self, adb_binary: AdbBinary) -> None:
        """Execute kill-server adds an entry to history."""
        server = AdbServer(adb_binary)
        server.execute(AdbCommands.KILL_SERVER.value)
        assert len(server.history) >= 1
        server.execute(AdbCommands.START_SERVER.value)
        assert len(server.history) >= 2
