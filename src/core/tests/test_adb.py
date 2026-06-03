"""
Tests for src/core/adb.py: ADB server commands (start-server, kill-server) only.
Success and error cases, with pytest markers.
"""

from __future__ import annotations

import datetime
import subprocess
import time
from collections import OrderedDict
from pathlib import Path

import pytest

from core.adb import (
    _ADB_HISTORY_MAX_ENTRIES,
    AdbBinary,
    AdbClient,
    AdbCommand,
    AdbCommandResult,
    AdbCommandResultStatus,
    AdbCommands,
    AdbServer,
    _log_safe_argv,
    _log_safe_command_line,
    _log_safe_output_preview,
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

    def test_server_init_calls_start(
        self, adb_binary: AdbBinary, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AdbServer.__init__ gently delegates startup to start()."""
        called: list[AdbBinary] = []

        def fake_start(self: AdbServer) -> None:
            called.append(self.binary)

        monkeypatch.setattr(AdbServer, "start", fake_start)
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


class TestAdbBinaryDefaults:
    """Bundled ADB binary metadata defaults."""

    def test_adb_binary_defaults_use_frozen_project_metadata(self) -> None:
        binary = AdbBinary()
        assert binary.version == "Android Debug Bridge version 1.0.41"
        assert binary.build_version == "36.0.0-13206524"
        assert binary.build_number == 13206524
        assert binary.build_date is None


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
            argv: list[str], capture_output: bool, text: bool, timeout: float
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
            argv: list[str], capture_output: bool, text: bool, timeout: float
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
            argv: list[str], capture_output: bool, text: bool, timeout: float
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

    def test_remove_from_history_removes_matching_commands(
        self, server: AdbServer
    ) -> None:
        """remove_from_history removes all entries matching the given command."""
        start_result = AdbCommandResult(status=AdbCommandResultStatus.SUCCESS)
        kill_result = AdbCommandResult(status=AdbCommandResultStatus.SUCCESS)
        server.history = OrderedDict(
            [
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 0),
                    (AdbCommands.START_SERVER.value, start_result),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 1),
                    (AdbCommands.KILL_SERVER.value, kill_result),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 2),
                    (AdbCommands.START_SERVER.value, start_result),
                ),
            ]
        )

        server.remove_from_history(AdbCommands.START_SERVER.value)

        assert list(server.history.values()) == [
            (AdbCommands.KILL_SERVER.value, kill_result)
        ]

    def test_remove_from_history_noops_when_absent(self, server: AdbServer) -> None:
        """remove_from_history does not raise when no entry matches the command."""
        result = AdbCommandResult(status=AdbCommandResultStatus.SUCCESS)
        server.history = OrderedDict(
            [
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 0),
                    (AdbCommands.KILL_SERVER.value, result),
                )
            ]
        )

        server.remove_from_history(AdbCommands.START_SERVER.value)

        assert list(server.history.values()) == [
            (AdbCommands.KILL_SERVER.value, result)
        ]

    def test_server_history_is_capped_to_recent_entries(
        self, server: AdbServer
    ) -> None:
        """Server history keeps newest entries only."""
        for _ in range(_ADB_HISTORY_MAX_ENTRIES + 3):
            server.add_to_history(
                AdbCommands.START_SERVER.value,
                AdbCommandResult(status=AdbCommandResultStatus.SUCCESS),
            )

        assert len(server.history) == _ADB_HISTORY_MAX_ENTRIES


class TestAdbClientHistory:
    """ADB client history behavior mirrors server history behavior."""

    def test_client_history_is_capped_to_recent_entries(
        self, adb_binary: AdbBinary
    ) -> None:
        client = AdbClient(adb_binary)

        for _ in range(_ADB_HISTORY_MAX_ENTRIES + 3):
            client.add_to_history(
                AdbCommands.GET_DEVICES.value,
                AdbCommandResult(status=AdbCommandResultStatus.SUCCESS),
            )

        assert len(client.history) == _ADB_HISTORY_MAX_ENTRIES

    def test_client_remove_from_history_removes_matching_commands(
        self, adb_binary: AdbBinary
    ) -> None:
        client = AdbClient(adb_binary)
        devices_result = AdbCommandResult(status=AdbCommandResultStatus.SUCCESS)
        pair_result = AdbCommandResult(status=AdbCommandResultStatus.SUCCESS)
        client.history = OrderedDict(
            [
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 0),
                    (AdbCommands.GET_DEVICES.value, devices_result),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 1),
                    (AdbCommands.PAIR.value, pair_result),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 2),
                    (AdbCommands.GET_DEVICES.value, devices_result),
                ),
            ]
        )

        client.remove_from_history(AdbCommands.GET_DEVICES.value)

        assert list(client.history.values()) == [(AdbCommands.PAIR.value, pair_result)]

    def test_client_remove_from_history_noops_when_absent(
        self, adb_binary: AdbBinary
    ) -> None:
        client = AdbClient(adb_binary)
        result = AdbCommandResult(status=AdbCommandResultStatus.SUCCESS)
        client.history = OrderedDict(
            [
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 0),
                    (AdbCommands.PAIR.value, result),
                )
            ]
        )

        client.remove_from_history(AdbCommands.GET_DEVICES.value)

        assert list(client.history.values()) == [(AdbCommands.PAIR.value, result)]


class TestAdbCommandResultDefaults:
    """Default result values."""

    def test_time_uses_default_factory(self) -> None:
        """Separate default result instances get independent timestamps."""
        first = AdbCommandResult()
        time.sleep(0.001)
        second = AdbCommandResult()
        assert first.time < second.time


class TestAdbClientSendNotification:
    """ADB notification command construction."""

    def test_send_notification_targets_phone_and_keeps_raw_argv(
        self, adb_binary: AdbBinary, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Notification title/message are passed as argv values, not shell-quoted."""
        client = AdbClient(adb_binary)
        phone = Phone(id="abc123", name="Pixel", state="device")
        calls: list[tuple[AdbCommand, Phone | None, list[str] | None]] = []

        def fake_execute(
            command: AdbCommand,
            phone_arg: Phone | None = None,
            positional_arguments: list[str] | None = None,
        ) -> AdbCommandResult:
            calls.append((command, phone_arg, positional_arguments))
            return AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="posting:\n",
                error="",
                return_code=0,
            )

        monkeypatch.setattr(client, "_execute", fake_execute)

        assert client.send_notification(phone, "Hello there", "it's ready") is True
        assert calls == [
            (
                AdbCommands.SEND_NOTIFICATION.value,
                phone,
                ["-t", "Hello there", "-m", "it's ready"],
            )
        ]


class TestAdbLogRedaction:
    """Log-only ADB command redaction helpers."""

    def test_pairing_code_is_redacted_from_log_safe_argv(self) -> None:
        argv = ["/adb", "pair", "10.0.0.2:41000", "123456"]
        safe = _log_safe_argv(AdbCommands.PAIR.value, argv)
        assert "123456" not in safe
        assert safe == ["/adb", "pair", "10.0.0.2:41000", "<redacted>"]

    def test_device_id_is_redacted_from_log_safe_command_line(self) -> None:
        argv = [
            "/adb",
            "-s",
            "adb-secret-device._adb-tls-connect._tcp",
            "shell",
            "getprop",
            "ro.serialno",
        ]
        safe_line = _log_safe_command_line(AdbCommands.GET_SERIAL_NO.value, argv)
        assert "adb-secret-device" not in safe_line
        assert "<redacted>" in safe_line

    def test_notification_payload_is_redacted_from_log_safe_argv(self) -> None:
        argv = [
            "/adb",
            "-s",
            "device-1",
            "shell",
            "cmd",
            "notification",
            "post",
            "-n",
            "ARROW",
            "-t",
            "Private title",
            "-m",
            "Private message",
        ]
        safe = _log_safe_argv(AdbCommands.SEND_NOTIFICATION.value, argv)
        assert "device-1" not in safe
        assert "Private title" not in safe
        assert "Private message" not in safe
        assert safe[safe.index("-t") + 1] == "<redacted>"
        assert safe[safe.index("-m") + 1] == "<redacted>"

    def test_sensitive_output_preview_is_redacted(self) -> None:
        output = "adb-secret-device device product:x model:y device:z transport_id:1"
        assert _log_safe_output_preview(output, AdbCommands.GET_DEVICES.value) == (
            "<redacted>"
        )
