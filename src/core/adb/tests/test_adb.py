"""
Tests for core.adb.server: ADB server commands (start-server, kill-server) only.
Success and error cases, with pytest markers.
"""

from __future__ import annotations

import datetime
import subprocess
import time
from collections import OrderedDict
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import core.adb.binary as adb_binary_module
from core import ADB_BINARY_BUILD_NUMBER, ADB_BINARY_BUILD_VERSION, ADB_BINARY_VERSION
from core.adb.binary import AdbBinary
from core.adb.client import AdbClient
from core.adb.command import (
    ADB_HISTORY_MAX_ENTRIES,
    AdbCommandInvocation,
    AdbCommandResult,
    AdbCommandResultStatus,
    AdbCommands,
    AdbCommandSpec,
    AdbRetryPolicy,
    _log_safe_argv,
    _log_safe_command_line,
    _log_safe_output_preview,
)
from core.adb.exceptions import AdbServerException
from core.adb.server import AdbServer
from core.devices.phone import Phone, PhoneRepository
from core.geo.location import Location

pytestmark = [pytest.mark.adb, pytest.mark.adb_server]


# --- Fixtures ---


class TestAdbCommandSpecification:
    """Canonical command specifications and invocations."""

    def test_specification_is_immutable_and_hashable(self) -> None:
        command = AdbCommands.GET_DEVICES

        assert command.argv == ("devices", "-l")
        assert hash(command) == hash(command)
        with pytest.raises(FrozenInstanceError):
            setattr(command, "argv", ("devices",))

    def test_invocation_builds_complete_argv(self, adb_binary_path: Path) -> None:
        invocation = AdbCommands.SEND_NOTIFICATION.invoke(
            "-t", "Train ready", "-m", "Board now"
        )

        assert invocation.argv(adb_binary_path, device_id="device-123") == [
            str(adb_binary_path),
            "-s",
            "device-123",
            "shell",
            "cmd",
            "notification",
            "post",
            "-n",
            "ARROW",
            "-t",
            "Train ready",
            "-m",
            "Board now",
        ]
        assert AdbCommands.GET_DEVICES.invoke().argv(adb_binary_path) == [
            str(adb_binary_path),
            "devices",
            "-l",
        ]

    def test_catalog_exposes_typed_specifications(self) -> None:
        command = AdbCommands.PAIR

        assert isinstance(command, AdbCommandSpec)
        assert command.retry_policy is AdbRetryPolicy.PAIR
        assert isinstance(
            command.invoke("10.0.0.2:41000", "123456"), AdbCommandInvocation
        )


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
    server._mdns_available = False
    server._network_available = False
    return server


def _completed_process(
    argv: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


# --- Start server: success ---


class TestAdbServerStartSuccess:
    """ADB start-server success cases."""

    def test_server_init_calls_start_then_refreshes_mdns(
        self, adb_binary: AdbBinary, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AdbServer.__init__ starts gently before refreshing advisory mDNS state."""
        calls: list[str] = []

        def fake_start(self: AdbServer) -> None:
            calls.append("start")

        def fake_refresh_mdns_availability(self: AdbServer) -> bool:
            calls.append("refresh_mdns_availability")
            self._mdns_available = True
            return self._mdns_available

        def fake_refresh_network_availability(self: AdbServer) -> bool:
            calls.append("refresh_network_availability")
            self._network_available = True
            return self._network_available

        monkeypatch.setattr(AdbServer, "start", fake_start)
        monkeypatch.setattr(
            AdbServer,
            "refresh_mdns_availability",
            fake_refresh_mdns_availability,
        )
        monkeypatch.setattr(
            AdbServer,
            "refresh_network_availability",
            fake_refresh_network_availability,
        )
        server = AdbServer(adb_binary)
        assert server.binary == adb_binary
        assert calls == [
            "start",
            "refresh_mdns_availability",
            "refresh_network_availability",
        ]
        assert server.mdns_available is True
        assert server.network_available is True

    def test_server_start_adds_known_devices(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """start() records the command result and stores known devices."""
        phone = Phone(id="abc123", name="device:Pixel", state="device")

        def fake_execute(
            invocation: AdbCommandInvocation[object],
        ) -> AdbCommandResult:
            result = AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="",
                error="",
                return_code=0,
            )
            server.add_to_history(invocation.spec, result)
            return result

        monkeypatch.setattr(server, "_execute", fake_execute)
        monkeypatch.setattr(server, "get_known_devices", lambda: [phone])
        server.start()
        assert server.paired_devices.get("abc123") is phone
        last_result = server.get_last_command_result()
        assert last_result.status == AdbCommandResultStatus.SUCCESS

    def test_refresh_mdns_availability_sets_property_on_success(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """refresh_mdns_availability stores and returns a parsed success signal."""

        def fake_execute(
            _invocation: AdbCommandInvocation[object],
        ) -> AdbCommandResult:
            return AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="mdns daemon version [Openscreen discovery 0.0.0]\n",
                error="",
                return_code=0,
            )

        monkeypatch.setattr(server, "_execute", fake_execute)

        assert server.refresh_mdns_availability() is True
        assert server.mdns_available is True

    def test_refresh_mdns_availability_noops_startup_on_failure(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """mDNS preflight failures are advisory and leave availability false."""

        def fake_execute(
            _invocation: AdbCommandInvocation[object],
        ) -> AdbCommandResult:
            return AdbCommandResult(
                status=AdbCommandResultStatus.ERROR,
                output="",
                error="mdns unavailable",
                return_code=1,
            )

        server._mdns_available = True
        monkeypatch.setattr(server, "_execute", fake_execute)

        assert server.refresh_mdns_availability() is False
        assert server.mdns_available is False

    def test_refresh_mdns_availability_handles_execute_exception(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """mDNS preflight exceptions are advisory and leave availability false."""

        def fake_execute(
            _invocation: AdbCommandInvocation[object],
        ) -> AdbCommandResult:
            raise AdbServerException("mdns check failed")

        server._mdns_available = True
        monkeypatch.setattr(server, "_execute", fake_execute)

        assert server.refresh_mdns_availability() is False
        assert server.mdns_available is False

    def test_refresh_network_availability_updates_cached_property(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "core.adb.server.resolve_network_identity",
            lambda: ("192.168.1.10", True),
        )

        assert server.refresh_network_availability() is True
        assert server.network_available is True

    def test_refresh_network_availability_clears_previous_state(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        server._network_available = True
        monkeypatch.setattr(
            "core.adb.server.resolve_network_identity",
            lambda: ("127.0.0.1", False),
        )

        assert server.refresh_network_availability() is False
        assert server.network_available is False


class TestAdbServerHealthProbe:
    """Server-running checks should read lifecycle history without new ADB side effects."""

    def test_is_server_running_true_after_successful_start(
        self, server: AdbServer
    ) -> None:
        server.add_to_history(
            AdbCommands.START_SERVER,
            AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="",
                error="",
                return_code=0,
            ),
        )
        assert server.is_server_running() is True

    def test_is_server_running_false_after_successful_stop(
        self, server: AdbServer
    ) -> None:
        server.add_to_history(
            AdbCommands.START_SERVER,
            AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="",
                error="",
                return_code=0,
            ),
        )
        server.add_to_history(
            AdbCommands.KILL_SERVER,
            AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="",
                error="",
                return_code=0,
            ),
        )
        assert server.is_server_running() is False

    def test_is_server_running_false_without_lifecycle_history(
        self, server: AdbServer
    ) -> None:
        assert server.is_server_running() is False


class TestAdbClientDeviceStatus:
    """Device ``adb get-state`` belongs on the client, not the server."""

    def test_client_status_returns_trimmed_device_state(
        self, adb_binary: AdbBinary, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.adb.client import AdbClient

        client = AdbClient(adb_binary)
        phone = Phone(id="abc123", state="device")

        def fake_execute(
            invocation: AdbCommandInvocation[object],
            target_phone: Phone | None = None,
        ) -> AdbCommandResult:
            assert target_phone is phone
            assert invocation.spec is AdbCommands.STATUS
            return AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="device\n",
                error="",
                return_code=0,
                phone=target_phone,
            )

        monkeypatch.setattr(client, "_execute", fake_execute)
        assert client.status(phone) == "device"

    def test_status_command_describes_device_state_not_server(self) -> None:
        status = AdbCommands.STATUS
        assert status.argv == ("get-state",)
        assert "device" in status.description.casefold()
        assert "server" not in status.name.casefold()


class TestAdbClientUnsupportedLocationOperations:
    """Unimplemented location operations must fail explicitly."""

    def test_enable_location_services_raises(self, adb_binary: AdbBinary) -> None:
        client = AdbClient(adb_binary)

        with pytest.raises(NotImplementedError, match="not implemented"):
            client.enable_location_services()

    def test_disable_location_services_raises(self, adb_binary: AdbBinary) -> None:
        client = AdbClient(adb_binary)

        with pytest.raises(NotImplementedError, match="not implemented"):
            client.disable_location_services()

    def test_set_mock_location_raises(self, adb_binary: AdbBinary) -> None:
        client = AdbClient(adb_binary)

        with pytest.raises(NotImplementedError, match="not implemented"):
            client.set_mock_location(Location(lat=48.8566, lon=2.3522))


class TestAdbBinaryDefaults:
    """Bundled ADB binary metadata defaults."""

    def test_adb_binary_path_default_is_resolved_lazily(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        expected_path = Path("/resolved/adb")
        resolutions: list[Path] = []

        class FakeApplicationPaths:
            @property
            def adb_binary(self) -> Path:
                resolutions.append(expected_path)
                return expected_path

        monkeypatch.setattr(
            adb_binary_module,
            "APPLICATION_PATHS",
            FakeApplicationPaths(),
        )

        explicit = AdbBinary(path=Path("/mock/adb"))
        assert explicit.path == Path("/mock/adb")
        assert resolutions == []

        defaulted = AdbBinary()
        assert defaulted.path == expected_path
        assert resolutions == [expected_path]

    def test_adb_binary_defaults_use_frozen_project_metadata(self) -> None:
        binary = AdbBinary()
        assert binary.version == "Android Debug Bridge version 1.0.41"
        assert binary.build_version == "36.0.0-13206524"
        assert binary.build_number == 13206524
        assert binary.build_date is None

    def test_adb_binary_equality_uses_frozen_metadata_identity(self) -> None:
        first = AdbBinary(path=Path("/mock/adb"))
        second = AdbBinary(path=Path("/different/adb"))
        assert first == second

    def test_adb_binary_equality_detects_metadata_mismatch(self) -> None:
        expected = AdbBinary(path=Path("/mock/adb"))
        actual = AdbBinary(
            path=Path("/mock/adb"),
            version="Android Debug Bridge version 9.9.9",
        )
        assert actual != expected


class TestAdbServerBinaryVersion:
    """ADB binary version preflight behavior."""

    def test_get_binary_version_executes_without_constructing_server(
        self, adb_binary: AdbBinary, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(
            argv: list[str], capture_output: bool, text: bool, timeout: float
        ) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            return _completed_process(
                argv,
                returncode=0,
                stdout=(
                    f"{ADB_BINARY_VERSION}\n"
                    f"Version {ADB_BINARY_BUILD_VERSION}\n"
                    f"Installed as {adb_binary.path}\n"
                    "Running on Darwin 25.5.0 (arm64)\n"
                ),
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        parsed = AdbServer.get_binary_version(adb_binary)

        assert calls == [[str(adb_binary.path), "--version"]]
        assert parsed.version == ADB_BINARY_VERSION
        assert parsed.build_version == ADB_BINARY_BUILD_VERSION
        assert parsed.build_number == ADB_BINARY_BUILD_NUMBER
        assert parsed.path == adb_binary.path

    def test_get_binary_version_raises_on_non_success(
        self, adb_binary: AdbBinary, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(
            argv: list[str], capture_output: bool, text: bool, timeout: float
        ) -> subprocess.CompletedProcess[str]:
            return _completed_process(
                argv,
                returncode=1,
                stdout="",
                stderr="cannot read version",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(
            AdbServerException, match="Failed to read ADB binary version"
        ):
            AdbServer.get_binary_version(adb_binary)


# --- Kill server: success ---


class TestAdbServerKillSuccess:
    """ADB kill-server success cases."""

    def test_server_kill_success(
        self, server: AdbServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Killing the ADB server with a valid binary succeeds."""

        def fake_execute(
            invocation: AdbCommandInvocation[object],
        ) -> AdbCommandResult:
            result = AdbCommandResult(
                status=AdbCommandResultStatus.SUCCESS,
                output="",
                error="",
                return_code=0,
            )
            server.add_to_history(invocation.spec, result)
            return result

        monkeypatch.setattr(server, "_execute", fake_execute)
        server.stop()
        last_cmd, last_result = server.get_last_from_history()
        assert last_cmd == AdbCommands.KILL_SERVER
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
        result = server._execute(AdbCommands.KILL_SERVER.invoke())
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
            server._execute(AdbCommands.START_SERVER.invoke())


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
            server._execute(AdbCommands.KILL_SERVER.invoke())


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
        result = server._execute(AdbCommands.START_SERVER.invoke())
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
        server._execute(AdbCommands.KILL_SERVER.invoke())
        assert len(server.history) >= 1
        server._execute(AdbCommands.START_SERVER.invoke())
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

        def fake_execute(
            _invocation: AdbCommandInvocation[object],
        ) -> AdbCommandResult:
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
                    (AdbCommands.START_SERVER, start_result),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 1),
                    (AdbCommands.KILL_SERVER, kill_result),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 2),
                    (AdbCommands.START_SERVER, start_result),
                ),
            ]
        )

        server.remove_from_history(AdbCommands.START_SERVER)

        assert list(server.history.values()) == [(AdbCommands.KILL_SERVER, kill_result)]

    def test_remove_from_history_noops_when_absent(self, server: AdbServer) -> None:
        """remove_from_history does not raise when no entry matches the command."""
        result = AdbCommandResult(status=AdbCommandResultStatus.SUCCESS)
        server.history = OrderedDict(
            [
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 0),
                    (AdbCommands.KILL_SERVER, result),
                )
            ]
        )

        server.remove_from_history(AdbCommands.START_SERVER)

        assert list(server.history.values()) == [(AdbCommands.KILL_SERVER, result)]

    def test_server_history_is_capped_to_recent_entries(
        self, server: AdbServer
    ) -> None:
        """Server history keeps newest entries only."""
        for _ in range(ADB_HISTORY_MAX_ENTRIES + 3):
            server.add_to_history(
                AdbCommands.START_SERVER,
                AdbCommandResult(status=AdbCommandResultStatus.SUCCESS),
            )

        assert len(server.history) == ADB_HISTORY_MAX_ENTRIES


class TestAdbClientHistory:
    """ADB client history behavior mirrors server history behavior."""

    def test_client_history_is_capped_to_recent_entries(
        self, adb_binary: AdbBinary
    ) -> None:
        client = AdbClient(adb_binary)

        for _ in range(ADB_HISTORY_MAX_ENTRIES + 3):
            client.add_to_history(
                AdbCommands.GET_DEVICES,
                AdbCommandResult(status=AdbCommandResultStatus.SUCCESS),
            )

        assert len(client.history) == ADB_HISTORY_MAX_ENTRIES

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
                    (AdbCommands.GET_DEVICES, devices_result),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 1),
                    (AdbCommands.PAIR, pair_result),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 2),
                    (AdbCommands.GET_DEVICES, devices_result),
                ),
            ]
        )

        client.remove_from_history(AdbCommands.GET_DEVICES)

        assert list(client.history.values()) == [(AdbCommands.PAIR, pair_result)]

    def test_client_remove_from_history_noops_when_absent(
        self, adb_binary: AdbBinary
    ) -> None:
        client = AdbClient(adb_binary)
        result = AdbCommandResult(status=AdbCommandResultStatus.SUCCESS)
        client.history = OrderedDict(
            [
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 0),
                    (AdbCommands.PAIR, result),
                )
            ]
        )

        client.remove_from_history(AdbCommands.GET_DEVICES)

        assert list(client.history.values()) == [(AdbCommands.PAIR, result)]


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
        calls: list[tuple[AdbCommandInvocation[object], Phone | None]] = []

        def fake_execute(
            invocation: AdbCommandInvocation[object],
            phone_arg: Phone | None = None,
        ) -> AdbCommandResult:
            calls.append((invocation, phone_arg))
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
                AdbCommands.SEND_NOTIFICATION.invoke(
                    "-t", "Hello there", "-m", "it's ready"
                ),
                phone,
            )
        ]


class TestAdbLogRedaction:
    """Log-only ADB command redaction helpers."""

    def test_pairing_code_is_redacted_from_log_safe_argv(self) -> None:
        invocation = AdbCommands.PAIR.invoke("10.0.0.2:41000", "123456")
        safe = _log_safe_argv(invocation, Path("/adb"))
        assert "123456" not in safe
        assert safe == ["/adb", "pair", "10.0.0.2:41000", "<redacted>"]

    def test_device_id_is_redacted_from_log_safe_command_line(self) -> None:
        safe_line = _log_safe_command_line(
            AdbCommands.GET_SERIAL_NO.invoke(),
            Path("/adb"),
            device_id="adb-secret-device._adb-tls-connect._tcp",
        )
        assert "adb-secret-device" not in safe_line
        assert "<redacted>" in safe_line

    def test_notification_payload_is_redacted_from_log_safe_argv(self) -> None:
        invocation = AdbCommands.SEND_NOTIFICATION.invoke(
            "-t", "Private title", "-m", "Private message"
        )
        safe = _log_safe_argv(invocation, Path("/adb"), device_id="device-1")
        assert "device-1" not in safe
        assert "Private title" not in safe
        assert "Private message" not in safe
        assert safe[safe.index("-t") + 1] == "<redacted>"
        assert safe[safe.index("-m") + 1] == "<redacted>"

    def test_sensitive_output_preview_is_redacted(self) -> None:
        output = "adb-secret-device device product:x model:y device:z transport_id:1"
        assert _log_safe_output_preview(output, AdbCommands.GET_DEVICES) == (
            "<redacted>"
        )
