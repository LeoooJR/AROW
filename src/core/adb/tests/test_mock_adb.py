"""
Tests for faker-backed mock ADB (no real adb binary; not marked ``@pytest.mark.adb``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from application_paths import APPLICATION_PATHS, ApplicationPaths
from core import ADB_BINARY_BUILD_NUMBER, ADB_BINARY_BUILD_VERSION, ADB_BINARY_VERSION
from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.adb.command import AdbCommands, AdbCommandSpec, AdbRetryPolicy
from core.adb.exceptions import AdbClientException
from core.entrypoint import ModelEntrypoint
from core.signals import CoreSignal, CoreSignals

pytestmark = [pytest.mark.mock_adb]


def test_mock_server_reports_mdns_available() -> None:
    server = MockAdbServer(state=MockAdbState(seed=808, initial_devices=1))
    assert server.mdns_available is True


def test_mock_runtime_defaults_use_centralized_binary_path() -> None:
    state = MockAdbState(seed=807, initial_devices=1)

    assert MockAdbServer(state=state).binary.path == APPLICATION_PATHS.mock_adb_binary
    assert MockAdbClient(state=state).binary.path == APPLICATION_PATHS.mock_adb_binary


def test_mock_server_mdns_check_output_matches_parser() -> None:
    server = MockAdbServer(state=MockAdbState(seed=809, initial_devices=1))
    result = server._execute(AdbCommands.MDNS_CHECK.invoke())

    assert AdbCommands.MDNS_CHECK.parse(result.output) is True


def test_mock_server_binary_version_output_matches_parser() -> None:
    server = MockAdbServer(state=MockAdbState(seed=810, initial_devices=1))
    result = server._execute(AdbCommands.GET_BINARY_VERSION.invoke())
    parsed = AdbCommands.GET_BINARY_VERSION.parse(result.output)

    assert parsed.version == ADB_BINARY_VERSION
    assert parsed.build_version == ADB_BINARY_BUILD_VERSION
    assert parsed.build_number == ADB_BINARY_BUILD_NUMBER
    assert str(parsed.path) == "/mock/adb"


def test_model_entrypoint_startup_mock_returns_outcome_without_emitting(
    monkeypatch, tmp_path: Path
) -> None:
    paths = ApplicationPaths(
        application_dir=tmp_path,
        config_dir=tmp_path / "config",
        source_dir=APPLICATION_PATHS.source_dir,
        platform=APPLICATION_PATHS.platform,
    )
    model_entrypoint = ModelEntrypoint(use_mock_adb=True, paths=paths)
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    outcome = model_entrypoint.startup()

    assert isinstance(outcome.adb_server, MockAdbServer)
    assert isinstance(outcome.adb_client, MockAdbClient)
    assert model_entrypoint.adb_server is None
    assert emitted == []
    assert outcome.devices
    assert outcome.devices[0].descriptor.manufacturer.strip()


@pytest.mark.parametrize(
    ("use_mock_adb", "environment_value"),
    [(True, None), (False, "true")],
    ids=["cli-option", "environment-override"],
)
def test_model_entrypoint_mock_startup_ignores_unsupported_real_adb_platform(
    use_mock_adb: bool,
    environment_value: str | None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if environment_value is None:
        monkeypatch.delenv("AROW_USE_MOCK_ADB", raising=False)
    else:
        monkeypatch.setenv("AROW_USE_MOCK_ADB", environment_value)
    paths = ApplicationPaths(
        application_dir=tmp_path,
        config_dir=tmp_path / "config",
        source_dir=tmp_path / "src",
        platform="freebsd",
    )

    outcome = ModelEntrypoint(
        use_mock_adb=use_mock_adb,
        paths=paths,
    ).startup()

    assert isinstance(outcome.adb_server, MockAdbServer)
    assert isinstance(outcome.adb_client, MockAdbClient)
    assert outcome.adb_server.binary.path == paths.mock_adb_binary
    assert outcome.adb_client.binary.path == paths.mock_adb_binary


def test_mock_server_restart_repopulates_devices() -> None:
    state = MockAdbState(seed=7, initial_devices=2)
    server = MockAdbServer(state=state)
    assert len(server.paired_devices) == 2
    server.restart()
    assert len(server.paired_devices) == 2


def test_mock_notification_succeeds_through_public_client_api() -> None:
    state = MockAdbState(seed=811, initial_devices=1)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    phone = next(iter(server.paired_devices))

    assert client.send_notification(phone, "Private title", "Private message") is True


def test_mock_rejects_unregistered_spec_with_known_argv() -> None:
    client = MockAdbClient(state=MockAdbState(seed=812, initial_devices=1))
    lookalike = AdbCommandSpec(
        name="UNREGISTERED_DEVICES_LOOKALIKE",
        description="Not the canonical devices specification",
        argv=AdbCommands.GET_DEVICES.argv,
        parser=AdbCommands.GET_DEVICES.parser,
        retry_policy=AdbRetryPolicy.DAEMON,
    )

    with pytest.raises(AdbClientException, match="Unsupported mock ADB client"):
        client._execute(lookalike.invoke())
