from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.devices import Phone
from core.work.authentificate_device_work import (
    AuthenticateDeviceWork,
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


@pytest.mark.parametrize("ip", ["", "not-an-ip", "192.168.1", "999.168.1.1"])
def test_pairing_input_validator_rejects_invalid_ipv4(ip: str) -> None:
    assert PairingInputValidator.validate(ip, 37777, "123456") == "Invalid IP address"


@pytest.mark.parametrize("port", [0, 65536, -1, True])
def test_pairing_input_validator_rejects_invalid_port(port: int) -> None:
    assert PairingInputValidator.validate("192.168.1.10", port, "123456") == (
        "Invalid port"
    )


@pytest.mark.parametrize("association_code", ["", "12345", "1234567", "12a456"])
def test_pairing_input_validator_rejects_invalid_association_code(
    association_code: str,
) -> None:
    assert PairingInputValidator.validate("192.168.1.10", 37777, association_code) == (
        "Invalid association code"
    )


def test_authenticate_work_invalid_input_fails_without_adb_pair_or_restart() -> None:
    server = FakeAdbServer()
    client = FakeAdbClient()

    outcome = AuthenticateDeviceWork(
        adb_server=server,
        adb_client=client,
        ip="999.168.1.1",
        port=37777,
        association_code="123456",
    ).run()

    assert outcome.success_phone is None
    assert outcome.failure is not None
    assert outcome.failure.ip == "999.168.1.1"
    assert outcome.failure.port == 37777
    assert outcome.failure.association_code == "123456"
    assert outcome.failure.reason == "Invalid IP address"
    assert client.pair_calls == []
    assert server.restart_calls == 0


def test_authenticate_work_valid_input_pairs_and_returns_success() -> None:
    server = FakeAdbServer()
    client = FakeAdbClient()

    outcome = AuthenticateDeviceWork(
        adb_server=server,
        adb_client=client,
        ip="192.168.1.10",
        port=37777,
        association_code="123456",
    ).run()

    assert outcome.failure is None
    assert outcome.success_phone is not None
    assert outcome.success_phone.descriptor.id == "mock-phone"
    assert client.pair_calls == [PairCall("192.168.1.10", 37777, "123456")]
    assert server.restart_calls == 0
