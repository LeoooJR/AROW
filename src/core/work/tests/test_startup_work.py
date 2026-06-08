from __future__ import annotations

import os
from pathlib import Path

import pytest

from core import ADB_BINARY_BUILD_NUMBER, ADB_BINARY_BUILD_VERSION, ADB_BINARY_VERSION
from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.adb.binary import AdbBinary
from core.devices import Phone
from core.models import CoreRuntimeModel
from core.signals import AdbServerStartedPayload, CoreSignal, DevicesUpdatedPayload
from core.work import startup_work
from core.work.startup_work import StartupCoreRuntimeWork, StartupOutcome


class KnownDevicesCountingMockAdbServer(MockAdbServer):
    """Mock server variant that counts ADB device list calls."""

    def __init__(self, *, state: MockAdbState) -> None:
        self.get_known_devices_calls = 0
        super().__init__(state=state)

    def get_known_devices(self) -> list[Phone]:
        self.get_known_devices_calls += 1
        return super().get_known_devices()


def test_ensure_adb_binary_executable_passes_for_executable_file(
    tmp_path: Path,
) -> None:
    adb_path = tmp_path / "adb"
    adb_path.write_text("#!/bin/sh\n", encoding="utf-8")
    adb_path.chmod(0o700)

    startup_work._ensure_adb_binary_executable(adb_path)


def test_ensure_adb_binary_executable_raises_for_non_executable_file(
    tmp_path: Path,
) -> None:
    adb_path = tmp_path / "adb"
    adb_path.write_text("#!/bin/sh\n", encoding="utf-8")
    adb_path.chmod(0o600)

    if os.access(adb_path, os.X_OK):
        pytest.skip("Platform reports the fixture file as executable")

    with pytest.raises(PermissionError, match="ADB binary is not executable"):
        startup_work._ensure_adb_binary_executable(adb_path)


def test_start_adb_server_checks_binary_before_constructing_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adb_path = tmp_path / "adb"
    adb_path.write_text("#!/bin/sh\n", encoding="utf-8")
    calls: list[str] = []

    class FakeAdbServer:
        def __init__(self, binary: AdbBinary) -> None:
            calls.append("construct")
            self.binary = binary
            self.paired_devices: list[Phone] = []

        @classmethod
        def get_binary_version(cls, binary: AdbBinary) -> AdbBinary:
            calls.append("version")
            return AdbBinary(
                path=binary.path,
                version=ADB_BINARY_VERSION,
                build_version=ADB_BINARY_BUILD_VERSION,
                build_number=ADB_BINARY_BUILD_NUMBER,
            )

    def fake_ensure(path: Path) -> None:
        assert path == adb_path
        calls.append("ensure")

    monkeypatch.setattr(startup_work, "_resolve_adb_binary_path", lambda: adb_path)
    monkeypatch.setattr(startup_work, "_ensure_adb_binary_executable", fake_ensure)
    monkeypatch.setattr(startup_work, "AdbServer", FakeAdbServer)

    server = startup_work._start_adb_server()

    assert isinstance(server, FakeAdbServer)
    assert calls == ["ensure", "version", "construct"]


def test_start_adb_server_rejects_binary_version_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adb_path = tmp_path / "adb"
    adb_path.write_text("#!/bin/sh\n", encoding="utf-8")
    constructed: list[AdbBinary] = []

    class FakeAdbServer:
        def __init__(self, binary: AdbBinary) -> None:
            constructed.append(binary)

        @classmethod
        def get_binary_version(cls, binary: AdbBinary) -> AdbBinary:
            return AdbBinary(
                path=binary.path,
                version="Android Debug Bridge version 9.9.9",
                build_version=ADB_BINARY_BUILD_VERSION,
                build_number=ADB_BINARY_BUILD_NUMBER,
            )

    monkeypatch.setattr(startup_work, "_resolve_adb_binary_path", lambda: adb_path)
    monkeypatch.setattr(
        startup_work, "_ensure_adb_binary_executable", lambda _path: None
    )
    monkeypatch.setattr(startup_work, "AdbServer", FakeAdbServer)

    with pytest.raises(RuntimeError, match="Failed to start ADB server") as exc_info:
        startup_work._start_adb_server()

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "frozen metadata" in str(exc_info.value.__cause__)
    assert constructed == []


def test_startup_mock_enriches_devices() -> None:
    outcome = StartupCoreRuntimeWork(use_mock_adb=True).run()
    assert outcome.adb_server is not None
    assert outcome.adb_client is not None
    assert len(outcome.devices) >= 1
    phone = outcome.devices[0]
    assert phone.descriptor.manufacturer.strip()
    assert phone.descriptor.os.strip()
    assert phone.descriptor.android_api_level is not None


def test_startup_reuses_server_paired_devices_after_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = MockAdbState(seed=909, initial_devices=2)
    server = KnownDevicesCountingMockAdbServer(state=state)
    client = MockAdbClient(state=state)
    assert server.get_known_devices_calls == 1

    monkeypatch.setattr(startup_work, "_start_adb_server", lambda: server)
    monkeypatch.setattr(startup_work, "_create_adb_client", lambda: client)

    outcome = StartupCoreRuntimeWork(use_mock_adb=False).run()

    assert server.get_known_devices_calls == 1
    assert outcome.devices == list(server.paired_devices)
    assert len(outcome.devices) == 2
    assert all(phone.descriptor.manufacturer.strip() for phone in outcome.devices)


def test_startup_apply_binds_mock_runtime_and_emits_startup_signals() -> None:
    state = MockAdbState(seed=111, initial_devices=1)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    devices = server.get_known_devices()
    model = CoreRuntimeModel()
    emitted: list[tuple[CoreSignal, object]] = []
    model._signal_bus.emit = lambda signal, payload: emitted.append((signal, payload))

    StartupCoreRuntimeWork.apply_main_thread(
        model,
        StartupOutcome(adb_server=server, adb_client=client, devices=devices),
    )

    assert model.adb_server is server
    assert model._adb_client is client
    assert emitted == [
        (
            CoreSignal.ADB_SERVER_STARTED,
            AdbServerStartedPayload(adb_binary=server.binary),
        ),
        (CoreSignal.DEVICES_UPDATED, DevicesUpdatedPayload(devices=devices)),
    ]
