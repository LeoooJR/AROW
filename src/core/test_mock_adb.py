"""
Tests for faker-backed mock ADB (no real adb binary; not marked ``@pytest.mark.adb``).
"""

from __future__ import annotations

from core.adb import MockAdbClient, MockAdbServer, MockAdbState
from core.work.authentificate_device_work import AuthenticateDeviceWork
from core.work.startup_work import StartupCoreRuntimeWork


def test_startup_mock_enriches_devices() -> None:
    outcome = StartupCoreRuntimeWork(use_mock_adb=True).run()
    assert outcome.adb_server is not None
    assert outcome.adb_client is not None
    assert len(outcome.devices) >= 1
    phone = outcome.devices[0]
    assert phone.descriptor.manufacturer.strip()
    assert phone.descriptor.os.strip()
    assert phone.descriptor.android_api_level is not None


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


def test_mock_server_restart_repopulates_devices() -> None:
    state = MockAdbState(seed=7, initial_devices=2)
    server = MockAdbServer(state=state)
    assert len(server.paired_devices) == 2
    server.restart()
    assert len(server.paired_devices) == 2
