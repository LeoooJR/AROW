"""
Tests for faker-backed mock ADB (no real adb binary; not marked ``@pytest.mark.adb``).
"""

from __future__ import annotations

import pytest

from core import ADB_BINARY_BUILD_NUMBER, ADB_BINARY_BUILD_VERSION, ADB_BINARY_VERSION
from core.adb import AdbClientException, ADBCommandParser, AdbCommands
from core.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices import Phone
from core.models import CoreRuntimeModel
from core.signals import (
    AdbServerStartedPayload,
    CoreSignal,
    DeviceAuthentificationFailedPayload,
    DeviceAuthentificationSucceededPayload,
    DevicesUpdatedPayload,
)
from core.work import startup_work
from core.work.authentificate_device_work import (
    AuthenticateDeviceWork,
    AuthentificateDeviceOutcome,
)
from core.work.startup_work import StartupCoreRuntimeWork, StartupOutcome

pytestmark = [pytest.mark.mock_adb]


class RestartCountingMockAdbServer(MockAdbServer):
    """Mock server variant that records lifecycle retries."""

    def __init__(self, *, state: MockAdbState) -> None:
        self.restart_calls = 0
        super().__init__(state=state)

    def restart(self) -> None:
        self.restart_calls += 1
        super().restart()


class ProtocolFaultOnceMockAdbClient(MockAdbClient):
    """Mock client variant that simulates a transient protocol fault on first pair."""

    def __init__(self, *, state: MockAdbState) -> None:
        super().__init__(state=state)
        self.pair_calls = 0

    def pair(self, ip: str, port: int, association_code: str) -> Phone:
        self.pair_calls += 1
        if self.pair_calls == 1:
            raise AdbClientException("protocol fault: connection reset")
        return super().pair(ip, port, association_code)


class AlwaysFailingMockAdbClient(MockAdbClient):
    """Mock client variant that simulates a non-retryable pairing failure."""

    def __init__(self, *, state: MockAdbState) -> None:
        super().__init__(state=state)
        self.pair_calls = 0

    def pair(self, ip: str, port: int, association_code: str) -> Phone:
        self.pair_calls += 1
        raise AdbClientException("wrong pairing code")


class KnownDevicesCountingMockAdbServer(MockAdbServer):
    """Mock server variant that counts ADB device list calls."""

    def __init__(self, *, state: MockAdbState) -> None:
        self.get_known_devices_calls = 0
        super().__init__(state=state)

    def get_known_devices(self) -> list[Phone]:
        self.get_known_devices_calls += 1
        return super().get_known_devices()


def test_startup_mock_enriches_devices() -> None:
    outcome = StartupCoreRuntimeWork(use_mock_adb=True).run()
    assert outcome.adb_server is not None
    assert outcome.adb_client is not None
    assert len(outcome.devices) >= 1
    phone = outcome.devices[0]
    assert phone.descriptor.manufacturer.strip()
    assert phone.descriptor.os.strip()
    assert phone.descriptor.android_api_level is not None


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


def test_core_runtime_model_startup_mock_returns_outcome_without_emitting() -> None:
    model = CoreRuntimeModel(use_mock_adb=True)
    emitted: list[tuple[CoreSignal, object]] = []
    model._signal_bus.emit = lambda signal, payload: emitted.append((signal, payload))

    outcome = model.startup()

    assert isinstance(outcome.adb_server, MockAdbServer)
    assert isinstance(outcome.adb_client, MockAdbClient)
    assert model.adb_server is None
    assert emitted == []
    assert outcome.devices
    assert outcome.devices[0].descriptor.manufacturer.strip()


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


def test_mock_pair_then_enrich() -> None:
    state = MockAdbState(seed=12345, initial_devices=1)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    outcome = AuthenticateDeviceWork(
        adb_server=server,
        adb_client=client,
        ip="10.20.30.40",
        port=37777,
        association_code="000000",
    ).run()
    assert outcome.failure is None
    assert outcome.success_phone is not None
    p = outcome.success_phone
    assert p.descriptor.state == "device"
    assert p.descriptor.manufacturer.strip()
    assert p.descriptor.hardware_serial.strip()


def test_mock_authenticate_retries_protocol_fault_then_enriches_success() -> None:
    state = MockAdbState(seed=222, initial_devices=0)
    server = RestartCountingMockAdbServer(state=state)
    client = ProtocolFaultOnceMockAdbClient(state=state)
    restart_calls_after_init = server.restart_calls

    outcome = AuthenticateDeviceWork(
        adb_server=server,
        adb_client=client,
        ip="10.30.40.50",
        port=40404,
        association_code="111111",
    ).run()

    assert client.pair_calls == 2
    assert server.restart_calls == restart_calls_after_init + 1
    assert outcome.failure is None
    assert outcome.success_phone is not None
    assert outcome.success_phone.descriptor.manufacturer.strip()
    assert outcome.success_phone.descriptor.hardware_serial.strip()


def test_mock_authenticate_non_protocol_failure_does_not_retry() -> None:
    state = MockAdbState(seed=333, initial_devices=0)
    server = RestartCountingMockAdbServer(state=state)
    client = AlwaysFailingMockAdbClient(state=state)
    restart_calls_after_init = server.restart_calls

    outcome = AuthenticateDeviceWork(
        adb_server=server,
        adb_client=client,
        ip="10.30.40.51",
        port=40405,
        association_code="222222",
    ).run()

    assert client.pair_calls == 1
    assert server.restart_calls == restart_calls_after_init
    assert outcome.success_phone is None
    assert outcome.failure is not None
    assert outcome.failure.reason == "wrong pairing code"
    assert outcome.failure.ip == "10.30.40.51"
    assert outcome.failure.port == 40405
    assert outcome.failure.association_code == "222222"


def test_authenticate_apply_success_adds_phone_and_emits_signal() -> None:
    state = MockAdbState(seed=444, initial_devices=0)
    server = MockAdbServer(state=state)
    model = CoreRuntimeModel()
    model._adb_server = server
    phone = Phone(id="paired-phone", state="device")
    emitted: list[tuple[CoreSignal, object]] = []
    model._signal_bus.emit = lambda signal, payload: emitted.append((signal, payload))

    AuthenticateDeviceWork.apply_main_thread(
        model, AuthentificateDeviceOutcome(success_phone=phone, failure=None)
    )

    assert server.paired_devices.get("paired-phone") is phone
    assert emitted == [
        (
            CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED,
            DeviceAuthentificationSucceededPayload(phone=phone),
        )
    ]


def test_authenticate_apply_failure_emits_without_adding_phone() -> None:
    state = MockAdbState(seed=555, initial_devices=0)
    server = MockAdbServer(state=state)
    model = CoreRuntimeModel()
    model._adb_server = server
    failure = DeviceAuthentificationFailedPayload(
        ip="10.30.40.52",
        port=40406,
        association_code="333333",
        reason="wrong pairing code",
    )
    emitted: list[tuple[CoreSignal, object]] = []
    model._signal_bus.emit = lambda signal, payload: emitted.append((signal, payload))

    AuthenticateDeviceWork.apply_main_thread(
        model, AuthentificateDeviceOutcome(success_phone=None, failure=failure)
    )

    assert len(server.paired_devices) == 0
    assert emitted == [(CoreSignal.DEVICE_AUTHENTIFICATION_FAILED, failure)]


def test_mock_server_restart_repopulates_devices() -> None:
    state = MockAdbState(seed=7, initial_devices=2)
    server = MockAdbServer(state=state)
    assert len(server.paired_devices) == 2
    server.restart()
    assert len(server.paired_devices) == 2
