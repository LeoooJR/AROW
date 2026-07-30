"""Tests for core work preflight decorator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.adb.binary import AdbBinary
from core.devices.phone import Phone
from core.work.helper import preflight


@dataclass
class _FakeOutcome:
    value: str = "ok"


class _FakeWork:
    def __init__(
        self,
        *,
        server: object | None = None,
        client: object | None = None,
        ip: object = "192.168.1.10",
        port: object = 37777,
    ) -> None:
        self._adb_server = server
        self._adb_client = client
        self.ip = ip
        self.port = port
        self.body_calls = 0

    @preflight()
    def run_no_checks(self) -> _FakeOutcome:
        self.body_calls += 1
        return _FakeOutcome()

    @preflight(
        check_server_started=True,
        error_to_raise=lambda self: RuntimeError("server preflight failed"),
    )
    def run_server_check(self) -> _FakeOutcome:
        self.body_calls += 1
        return _FakeOutcome()

    @preflight(
        check_server_started=True,
        check_client_created=True,
        error_to_raise=lambda self: AttributeError("client preflight failed"),
    )
    def run_server_and_client(self) -> _FakeOutcome:
        self.body_calls += 1
        return _FakeOutcome()

    @preflight(
        check_device_not_paired=True,
        error_to_raise=lambda self: RuntimeError("device preflight failed"),
    )
    def run_device_check(self) -> _FakeOutcome:
        self.body_calls += 1
        return _FakeOutcome()

    @preflight(
        check_server_started=True,
        check_client_created=True,
        check_device_not_paired=True,
        check_network_available=True,
        check_mdns_available=True,
        error_to_raise=lambda self: RuntimeError("mdns preflight failed"),
    )
    def run_full_preflight(self) -> _FakeOutcome:
        self.body_calls += 1
        return _FakeOutcome()


def _healthy_server(*, mdns: bool = True, network: bool = True) -> MagicMock:
    server = MagicMock()
    server.paired_devices = []
    server.is_server_running.return_value = True
    server.refresh_mdns_availability.return_value = mdns
    server.refresh_network_availability.return_value = network
    return server


def _healthy_client() -> MagicMock:
    client = MagicMock()
    client.binary = AdbBinary(path=Path("/mock/adb"))
    return client


def test_preflight_no_checks_runs_body() -> None:
    work = _FakeWork()
    outcome = work.run_no_checks()
    assert outcome.value == "ok"
    assert work.body_calls == 1


def test_preflight_server_health_failure_blocks_body() -> None:
    server = MagicMock()
    server.is_server_running.return_value = False
    work = _FakeWork(server=server)

    with pytest.raises(RuntimeError, match="server preflight failed"):
        work.run_server_check()

    assert work.body_calls == 0


def test_preflight_missing_client_blocks_body() -> None:
    work = _FakeWork(server=_healthy_server(), client=None)

    with pytest.raises(AttributeError, match="client preflight failed"):
        work.run_server_and_client()

    assert work.body_calls == 0


def test_preflight_exact_device_endpoint_blocks_before_health_probe() -> None:
    server = _healthy_server()
    server.paired_devices = [Phone(id="paired", ip="192.168.1.10", port=37777)]
    work = _FakeWork(server=server)

    with pytest.raises(RuntimeError, match="mdns preflight failed"):
        work.run_full_preflight()

    assert work.body_calls == 0
    server.is_server_running.assert_not_called()


def test_preflight_device_check_requires_server() -> None:
    work = _FakeWork(server=None)

    with pytest.raises(RuntimeError, match="device preflight failed"):
        work.run_device_check()

    assert work.body_calls == 0


@pytest.mark.parametrize(
    ("paired_ip", "paired_port"),
    [
        ("192.168.1.10", 37778),
        ("192.168.1.11", 37777),
    ],
)
def test_preflight_allows_nonmatching_device_endpoint(
    paired_ip: str, paired_port: int
) -> None:
    server = _healthy_server()
    server.paired_devices = [Phone(id="paired", ip=paired_ip, port=paired_port)]
    work = _FakeWork(server=server)

    outcome = work.run_device_check()

    assert outcome.value == "ok"
    assert work.body_calls == 1


def test_preflight_ignores_invalid_paired_device_port() -> None:
    server = _healthy_server()
    server.paired_devices = [Phone(id="paired", ip="192.168.1.10", port=True)]
    work = _FakeWork(server=server, port=1)

    outcome = work.run_device_check()

    assert outcome.value == "ok"
    assert work.body_calls == 1


@pytest.mark.parametrize(
    ("ip", "port"),
    [
        ("", 37777),
        (None, 37777),
        ("192.168.1.10", None),
        ("192.168.1.10", True),
        ("192.168.1.10", 0),
        ("192.168.1.10", 65536),
    ],
)
def test_preflight_device_check_rejects_invalid_target_endpoint(
    ip: object, port: object
) -> None:
    work = _FakeWork(server=_healthy_server(), ip=ip, port=port)

    with pytest.raises(RuntimeError, match="device preflight failed"):
        work.run_device_check()

    assert work.body_calls == 0


def test_preflight_network_check_requires_server() -> None:
    work = _FakeWork(server=None, client=_healthy_client())

    with pytest.raises(RuntimeError, match="mdns preflight failed"):
        work.run_full_preflight()

    assert work.body_calls == 0


def test_preflight_mdns_failure_blocks_body() -> None:
    work = _FakeWork(
        server=_healthy_server(mdns=False),
        client=_healthy_client(),
    )

    with pytest.raises(RuntimeError, match="mdns preflight failed"):
        work.run_full_preflight()

    assert work.body_calls == 0


def test_preflight_network_failure_blocks_body_before_mdns() -> None:
    server = _healthy_server(network=False)
    work = _FakeWork(server=server, client=_healthy_client())

    with pytest.raises(RuntimeError, match="mdns preflight failed"):
        work.run_full_preflight()

    assert work.body_calls == 0
    server.refresh_network_availability.assert_called_once()
    server.refresh_mdns_availability.assert_not_called()


def test_preflight_passes_before_body_when_all_checks_succeed() -> None:
    server = _healthy_server(mdns=True)
    work = _FakeWork(
        server=server,
        client=_healthy_client(),
    )

    outcome = work.run_full_preflight()

    assert outcome.value == "ok"
    assert work.body_calls == 1
    server.is_server_running.assert_called_once()
    server.refresh_network_availability.assert_called_once()
    server.refresh_mdns_availability.assert_called_once()
