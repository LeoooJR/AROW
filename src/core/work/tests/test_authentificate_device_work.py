from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.adb.binary import AdbBinary
from core.adb.exceptions import AdbClientException
from core.devices import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignal,
    CoreSignals,
    DeviceAuthentificationFailedPayload,
    DeviceAuthentificationSucceededPayload,
    ErrorRaisedPayload,
)
from core.work.authentificate_device_work import (
    AuthenticateDeviceWork,
    AuthentificateDeviceOutcome,
    DeviceAuthentificationError,
    PairingInputValidator,
)


@dataclass
class PairCall:
    ip: str
    port: int
    association_code: str


class FakeAdbClient:
    def __init__(self) -> None:
        self.pair_calls: list[PairCall] = []
        self.binary = AdbBinary(path=Path("/mock/adb"))

    def pair(self, ip: str, port: int, association_code: str) -> Phone:
        self.pair_calls.append(PairCall(ip, port, association_code))
        return Phone(id="mock-phone", state="device")

    def get_shell_enrichment_properties(
        self, phone: Phone
    ) -> dict[str, str | int | None]:
        return {
            "manufacturer": "Google",
            "model": "Pixel 8",
            "device_name": "Workbench",
            "android_release": "15",
            "sdk": 35,
            "ro_serialno": "SERIAL123",
        }


class FakeAdbServer:
    def __init__(self) -> None:
        self.restart_calls = 0

    def restart(self) -> None:
        self.restart_calls += 1

    def is_server_running(self) -> bool:
        return True

    def refresh_mdns_availability(self) -> bool:
        return True


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


@pytest.mark.parametrize("ip", ["", "not-an-ip", "192.168.1", "999.168.1.1"])
def test_pairing_input_validator_rejects_invalid_ipv4(ip: str) -> None:
    assert PairingInputValidator.validate(ip, 37777, "123456") == "Invalid IPv4 address"


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_pairing_input_validator_rejects_invalid_port_range(port: int) -> None:
    assert PairingInputValidator.validate("192.168.1.10", port, "123456") == (
        "Invalid port range"
    )


def test_pairing_input_validator_rejects_invalid_port_number() -> None:
    assert PairingInputValidator.validate("192.168.1.10", True, "123456") == (
        "Invalid port number"
    )


@pytest.mark.parametrize("association_code", ["", "12345", "1234567", "12a456"])
def test_pairing_input_validator_rejects_invalid_association_code(
    association_code: str,
) -> None:
    assert PairingInputValidator.validate("192.168.1.10", 37777, association_code) == (
        "Invalid association code"
    )


def test_authenticate_work_invalid_input_raises_without_adb_pair_or_restart() -> None:
    server = FakeAdbServer()
    client = FakeAdbClient()

    with pytest.raises(DeviceAuthentificationError) as exc_info:
        AuthenticateDeviceWork(
            adb_server=server,  # type: ignore[arg-type]
            adb_client=client,  # type: ignore[arg-type]
            ip="999.168.1.1",
            port=37777,
            association_code="123456",
        ).run()

    error = exc_info.value
    assert error.ip == "999.168.1.1"
    assert error.port == 37777
    assert error.association_code == "123456"
    assert error.reason == "Invalid IPv4 address"
    assert client.pair_calls == []
    assert server.restart_calls == 0


def test_authenticate_work_valid_input_pairs_and_returns_success() -> None:
    server = FakeAdbServer()
    client = FakeAdbClient()

    outcome = AuthenticateDeviceWork(
        adb_server=server,  # type: ignore[arg-type]
        adb_client=client,  # type: ignore[arg-type]
        ip="192.168.1.10",
        port=37777,
        association_code="123456",
    ).run()

    assert outcome.success_phone.descriptor.id == "mock-phone"
    assert client.pair_calls == [PairCall("192.168.1.10", 37777, "123456")]
    assert server.restart_calls == 0


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
    assert outcome.success_phone.descriptor.manufacturer.strip()
    assert outcome.success_phone.descriptor.hardware_serial.strip()


def test_mock_authenticate_non_protocol_failure_raises() -> None:
    state = MockAdbState(seed=333, initial_devices=0)
    server = RestartCountingMockAdbServer(state=state)
    client = AlwaysFailingMockAdbClient(state=state)
    restart_calls_after_init = server.restart_calls

    with pytest.raises(DeviceAuthentificationError) as exc_info:
        AuthenticateDeviceWork(
            adb_server=server,
            adb_client=client,
            ip="10.30.40.51",
            port=40405,
            association_code="222222",
        ).run()

    error = exc_info.value
    assert client.pair_calls == 1
    assert server.restart_calls == restart_calls_after_init
    assert error.reason == "wrong pairing code"
    assert error.ip == "10.30.40.51"
    assert error.port == 40405
    assert error.association_code == "222222"


def test_authenticate_apply_failure_emits_device_authentification_failed() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    error = DeviceAuthentificationError(
        ip="10.30.40.52",
        port=40406,
        association_code="333333",
        reason="wrong pairing code",
    )

    AuthenticateDeviceWork.apply_failure_main_thread(model_entrypoint, error)

    assert emitted == [
        (
            CoreSignals.DEVICE_AUTHENTIFICATION_FAILED,
            DeviceAuthentificationFailedPayload(
                ip="10.30.40.52",
                port=40406,
                association_code="333333",
                reason="wrong pairing code",
            ),
        )
    ]


def test_authenticate_apply_failure_emits_error_raised_for_generic_exception() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    error = RuntimeError("unexpected")

    AuthenticateDeviceWork.apply_failure_main_thread(model_entrypoint, error)

    assert len(emitted) == 1
    signal, payload = emitted[0]
    assert signal == CoreSignals.ERROR_RAISED
    assert isinstance(payload, ErrorRaisedPayload)
    assert payload.source == "AuthenticateDeviceWork"
    assert payload.error_type == "RuntimeError"
    assert payload.error_message == "unexpected"


def test_authenticate_apply_success_adds_phone_and_emits_signal() -> None:
    state = MockAdbState(seed=444, initial_devices=0)
    server = MockAdbServer(state=state)
    model_entrypoint = ModelEntrypoint()
    model_entrypoint._adb_server = server
    phone = Phone(id="paired-phone", state="device")
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    AuthenticateDeviceWork.apply_main_thread(
        model_entrypoint, AuthentificateDeviceOutcome(success_phone=phone)
    )

    assert server.paired_devices.get("paired-phone") is phone
    assert emitted == [
        (
            CoreSignals.DEVICE_AUTHENTIFICATION_SUCCEEDED,
            DeviceAuthentificationSucceededPayload(
                device=phone.serialize(),
            ),
        )
    ]
