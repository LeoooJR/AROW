"""Preflight integration tests for decorated core runtime work classes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.work.authentificate_device_work import (
    AuthenticateDeviceWork,
    DeviceAuthentificationError,
)
from core.work.close_work import CloseCoreRuntimeError, CloseCoreRuntimeWork
from core.work.refresh_known_devices_work import (
    RefreshKnownDevicesError,
    RefreshKnownDevicesWork,
)


def test_refresh_work_preflight_blocks_before_device_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = MockAdbState(seed=303, initial_devices=1)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    monkeypatch.setattr(server, "is_server_running", lambda: False)
    list_calls: list[None] = []

    def fake_get_known_devices() -> list[object]:
        list_calls.append(None)
        return []

    monkeypatch.setattr(server, "get_known_devices", fake_get_known_devices)

    with pytest.raises(
        RefreshKnownDevicesError,
        match="must be initialized and healthy before refreshing devices",
    ):
        RefreshKnownDevicesWork(server, client).run()

    assert list_calls == []


def test_authenticate_work_preflight_blocks_before_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = MockAdbState(seed=404, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    monkeypatch.setattr(server, "refresh_mdns_availability", lambda: False)

    with pytest.raises(DeviceAuthentificationError) as exc_info:
        AuthenticateDeviceWork(
            adb_server=server,
            adb_client=client,
            ip="999.168.1.1",
            port=37777,
            association_code="123456",
        ).run()

    assert exc_info.value.reason == "ADB runtime preflight failed"


def test_authenticate_work_network_preflight_blocks_before_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = MockAdbState(seed=405, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    monkeypatch.setattr(server, "refresh_network_availability", lambda: False)
    pair_calls: list[None] = []

    def pair(*_args: object) -> object:
        pair_calls.append(None)
        raise AssertionError("pair should not run")

    monkeypatch.setattr(client, "pair", pair)

    with pytest.raises(DeviceAuthentificationError) as exc_info:
        AuthenticateDeviceWork(
            adb_server=server,
            adb_client=client,
            ip="999.168.1.1",
            port=37777,
            association_code="123456",
        ).run()

    assert exc_info.value.reason == "ADB runtime preflight failed"
    assert pair_calls == []


def test_close_work_preflight_blocks_before_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adb_server = MagicMock()
    adb_server.binary.path = "/mock/adb"
    adb_server.is_server_running.return_value = False
    stop_calls: list[None] = []

    def stop() -> None:
        stop_calls.append(None)

    adb_server.stop = stop

    with pytest.raises(
        CloseCoreRuntimeError, match="must be running before close work"
    ):
        CloseCoreRuntimeWork(adb_server).run()

    assert stop_calls == []


def test_all_decorated_work_run_methods_have_preflight_wrapper() -> None:
    from core.work.authentificate_device_work import AuthenticateDeviceWork
    from core.work.close_work import CloseCoreRuntimeWork
    from core.work.host_install_identity_work import HostInstallIdentityWork
    from core.work.refresh_known_devices_work import RefreshKnownDevicesWork
    from core.work.startup_work import StartupCoreRuntimeWork

    for work_cls in (
        StartupCoreRuntimeWork,
        HostInstallIdentityWork,
        RefreshKnownDevicesWork,
        AuthenticateDeviceWork,
        CloseCoreRuntimeWork,
    ):
        assert getattr(work_cls.run, "__wrapped__", None) is not None
