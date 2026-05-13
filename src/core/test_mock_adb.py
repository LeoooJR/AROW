"""
Tests for faker-backed mock ADB (no real adb binary; not marked ``@pytest.mark.adb``).
"""

from __future__ import annotations

from core.adb import AdbClientException, MockAdbClient, MockAdbServer, MockAdbState
from core.devices import Phone
from core.models import CoreRuntimeModel
from core.signals import (
    AdbServerStartedPayload,
    CoreSignal,
    DeviceAuthentificationFailedPayload,
    DeviceAuthentificationSucceededPayload,
    DevicesUpdatedPayload,
)
from core.work.authentificate_device_work import (
    AuthenticateDeviceWork,
    AuthentificateDeviceOutcome,
)
from core.work.startup_work import StartupCoreRuntimeWork, StartupOutcome


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


def test_startup_mock_enriches_devices() -> None:
    outcome = StartupCoreRuntimeWork(use_mock_adb=True).run()
    assert outcome.adb_server is not None
    assert outcome.adb_client is not None
    assert len(outcome.devices) >= 1
    phone = outcome.devices[0]
    assert phone.descriptor.manufacturer.strip()
    assert phone.descriptor.os.strip()
    assert phone.descriptor.android_api_level is not None


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
