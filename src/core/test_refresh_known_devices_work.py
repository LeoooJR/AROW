"""Tests for src/core/work/refresh_known_devices_work.py (shell enrichment orchestration)."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.adb import MockAdbClient, MockAdbServer, MockAdbState
from core.devices import Phone
from core.models import CoreRuntimeModel
from core.signals import CoreSignal, DevicesUpdatedPayload
from core.work.refresh_known_devices_work import (
    RefreshKnownDevicesOutcome,
    RefreshKnownDevicesWork,
    enrich_phones_with_adb_shell_properties,
)


def test_enrich_phones_with_adb_shell_properties_empty_skips_adb_methods() -> None:
    """No phones implies no getters on the client (fast path)."""
    client = MagicMock()
    enrich_phones_with_adb_shell_properties(client, [])
    client.assert_not_called()


def test_refresh_known_devices_work_enriches_mock_adb_devices() -> None:
    """Mock ADB lets refresh exercise list parsing plus real shell getter enrichment."""
    state = MockAdbState(seed=101, initial_devices=2)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)

    outcome = RefreshKnownDevicesWork(server, client).run()

    assert len(outcome.devices) == 2
    for phone in outcome.devices:
        assert phone.descriptor.manufacturer.strip()
        assert phone.descriptor.model.strip()
        assert phone.descriptor.name.strip()
        assert phone.descriptor.os.strip()
        assert phone.descriptor.android_api_level is not None
        assert phone.descriptor.hardware_serial.strip()
        assert phone.stable_key.startswith("hw:v1:")


def test_refresh_known_devices_apply_replaces_devices_and_emits_update() -> None:
    """Applying refresh results replaces model devices and publishes the same list."""
    state = MockAdbState(seed=202, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    model = CoreRuntimeModel()
    model._adb_server = server
    model._adb_client = client
    stale_phone = Phone(id="stale-device", state="device")
    refreshed_phone = Phone(id="fresh-device", state="device")
    server.paired_devices.add(stale_phone)
    emitted: list[tuple[CoreSignal, object]] = []
    model._signal_bus.emit = lambda signal, payload: emitted.append((signal, payload))

    outcome = RefreshKnownDevicesOutcome(devices=[refreshed_phone])
    RefreshKnownDevicesWork.apply_main_thread(model, outcome)

    assert server.paired_devices.get("stale-device") is None
    assert server.paired_devices.get("fresh-device") is refreshed_phone
    assert emitted == [
        (CoreSignal.DEVICES_UPDATED, DevicesUpdatedPayload(devices=[refreshed_phone]))
    ]
