"""
Tests for faker-backed mock ADB (no real adb binary; not marked ``@pytest.mark.adb``).
"""

from __future__ import annotations

from typing import Any

import pytest

from core import ADB_BINARY_BUILD_NUMBER, ADB_BINARY_BUILD_VERSION, ADB_BINARY_VERSION
from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.adb.command import ADBCommandParser, AdbCommands
from core.entrypoint import ModelEntrypoint
from core.signals import CoreSignal, CoreSignals

pytestmark = [pytest.mark.mock_adb]


def test_mock_server_reports_mdns_available() -> None:
    server = MockAdbServer(state=MockAdbState(seed=808, initial_devices=1))
    assert server.mdns_available is True


def test_mock_server_mdns_check_output_matches_parser() -> None:
    server = MockAdbServer(state=MockAdbState(seed=809, initial_devices=1))
    result = server._execute(AdbCommands.MDNS_CHECK.value)

    assert ADBCommandParser.MDNS_CHECK.parse(result.output) is True


def test_mock_server_binary_version_output_matches_parser() -> None:
    server = MockAdbServer(state=MockAdbState(seed=810, initial_devices=1))
    result = server._execute(AdbCommands.GET_BINARY_VERSION.value)
    parsed = ADBCommandParser.GET_BINARY_VERSION.parse(result.output)

    assert parsed.version == ADB_BINARY_VERSION
    assert parsed.build_version == ADB_BINARY_BUILD_VERSION
    assert parsed.build_number == ADB_BINARY_BUILD_NUMBER
    assert str(parsed.path) == "/mock/adb"


def test_model_entrypoint_startup_mock_returns_outcome_without_emitting() -> None:
    model_entrypoint = ModelEntrypoint(use_mock_adb=True)
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


def test_mock_server_restart_repopulates_devices() -> None:
    state = MockAdbState(seed=7, initial_devices=2)
    server = MockAdbServer(state=state)
    assert len(server.paired_devices) == 2
    server.restart()
    assert len(server.paired_devices) == 2
