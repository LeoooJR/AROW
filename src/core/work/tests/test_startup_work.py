from __future__ import annotations

import os
from pathlib import Path

import pytest

from core import ADB_BINARY_BUILD_NUMBER, ADB_BINARY_BUILD_VERSION, ADB_BINARY_VERSION
from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.adb.binary import AdbBinary
from core.devices import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import AdbServerStartedPayload, CoreSignal, DevicesUpdatedPayload
from core.simulation import Simulation, SimulationRepository
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


@pytest.fixture(autouse=True)
def _patch_application_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep startup and entrypoint simulation persistence inside pytest tmp_path."""
    monkeypatch.setattr(
        startup_work,
        "get_or_create_application_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "core.entrypoint.get_or_create_application_dir",
        lambda: tmp_path,
    )


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

    with pytest.raises(RuntimeError, match="frozen metadata"):
        startup_work._start_adb_server()

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


def test_startup_run_loads_persisted_simulations_for_paired_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(startup_work, "mock_adb_seed_from_env", lambda: 111)
    first_outcome = StartupCoreRuntimeWork(use_mock_adb=True).run()
    phone = first_outcome.devices[0]
    repository = SimulationRepository(
        startup_work.get_or_create_application_dir() / "simulations"
    )
    simulation = Simulation(id="sim-1", device=phone, active=True)
    repository.add(simulation)
    repository.write_all()

    second_outcome = StartupCoreRuntimeWork(use_mock_adb=True).run()

    assert len(second_outcome.simulations) == 1
    assert second_outcome.simulations[0].id == "sim-1"
    loaded_phone = second_outcome.simulations[0].device
    assert loaded_phone is not None
    assert loaded_phone.id == phone.id
    assert second_outcome.adb_server is not None
    paired_from_outcome = {
        paired_phone.id: paired_phone
        for paired_phone in second_outcome.adb_server.paired_devices
    }
    assert loaded_phone is paired_from_outcome[phone.id]


def test_startup_apply_binds_mock_runtime_and_emits_startup_signals() -> None:
    state = MockAdbState(seed=111, initial_devices=1)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    devices = server.get_known_devices()
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal, object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    StartupCoreRuntimeWork.apply_main_thread(
        model_entrypoint,
        StartupOutcome(adb_server=server, adb_client=client, devices=devices),
    )

    assert model_entrypoint.adb_server is server
    assert model_entrypoint._adb_client is client
    assert emitted == [
        (
            CoreSignal.ADB_SERVER_STARTED,
            AdbServerStartedPayload(adb_binary=server.binary),
        ),
        (CoreSignal.DEVICES_UPDATED, DevicesUpdatedPayload(devices=devices)),
    ]


def test_startup_apply_restores_persisted_simulations() -> None:
    phone = Phone(id="device-1", state="device", model="Pixel")
    simulation = Simulation(id="sim-1", device=phone, active=True)
    state = MockAdbState(seed=111, initial_devices=1)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    devices = server.get_known_devices()
    model_entrypoint = ModelEntrypoint()

    StartupCoreRuntimeWork.apply_main_thread(
        model_entrypoint,
        StartupOutcome(
            adb_server=server,
            adb_client=client,
            devices=devices,
            simulations=[simulation],
        ),
    )

    restored = model_entrypoint._simulations.get("sim-1")
    assert restored is simulation
    assert restored is not None
    assert restored.device is phone
    assert restored.active is True
