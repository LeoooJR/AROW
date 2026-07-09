"""Tests for src/core/work/refresh_known_devices_work.py (shell enrichment orchestration)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices import Phone, serialize_phone_collection
from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignal,
    CoreSignals,
    DevicesUpdatedPayload,
    SimulationDeleteSkippedPayload,
)
from core.work.refresh_known_devices_work import (
    RefreshKnownDevicesOutcome,
    RefreshKnownDevicesWork,
    enrich_phones_with_adb_shell_properties,
)

pytestmark = [pytest.mark.devices]


def test_enrich_phones_with_adb_shell_properties_empty_skips_adb_methods() -> None:
    """No phones implies no getters on the client (fast path)."""
    client = MagicMock()
    enrich_phones_with_adb_shell_properties(client, [])
    client.assert_not_called()


def test_enrich_phones_with_adb_shell_properties_skips_non_targetable_phone() -> None:
    """Only devices in executable ADB state receive shell enrichment."""
    client = MagicMock()
    phone = Phone(id="offline-phone", state="offline")

    enrich_phones_with_adb_shell_properties(client, [phone])

    client.get_shell_enrichment_properties.assert_not_called()


def test_enrich_phones_with_adb_shell_properties_uses_batch_getter() -> None:
    """Full enrichment keeps existing application order while using one ADB shell call."""
    client = MagicMock()
    client.get_shell_enrichment_properties.return_value = {
        "manufacturer": "Google",
        "model": "Pixel 8",
        "device_name": "Field handset",
        "android_release": "15",
        "sdk": 35,
        "ro_serialno": "SER123",
    }
    phone = Phone(id="target-phone", state="device")

    enrich_phones_with_adb_shell_properties(client, [phone])

    client.get_shell_enrichment_properties.assert_called_once_with(phone)
    client.get_product_manufacturer.assert_not_called()
    client.get_product_model.assert_not_called()
    client.get_device_name_prop.assert_not_called()
    client.get_android_release.assert_not_called()
    client.get_android_sdk_api_level.assert_not_called()
    client.get_ro_serialno.assert_not_called()
    assert phone.descriptor.manufacturer == "Google"
    assert phone.descriptor.model == "Pixel 8"
    assert phone.descriptor.shell_device_name == "Field handset"
    assert phone.descriptor.name == "Field handset"
    assert phone.descriptor.os == "15"
    assert phone.descriptor.android_api_level == 35
    assert phone.descriptor.hardware_serial == "SER123"
    assert phone.stable_key.startswith("hw:v1:")


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
    model_entrypoint = ModelEntrypoint()
    model_entrypoint._adb_server = server
    model_entrypoint._adb_client = client
    stale_phone = Phone(id="stale-device", state="device")
    refreshed_phone = Phone(id="fresh-device", state="device")
    server.paired_devices.add(stale_phone)
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    outcome = RefreshKnownDevicesOutcome(devices=[refreshed_phone])
    RefreshKnownDevicesWork.apply_main_thread(model_entrypoint, outcome)

    assert server.paired_devices.get("stale-device") is None
    assert server.paired_devices.get("fresh-device") is refreshed_phone
    assert len(emitted) == 2
    assert emitted[0] == (
        CoreSignals.SIMULATION_DELETE_SKIPPED,
        SimulationDeleteSkippedPayload(
            device_id="stale-device",
            reason="Simulation for device with id stale-device not found",
        ),
    )
    assert emitted[1] == (
        CoreSignals.DEVICES_UPDATED,
        DevicesUpdatedPayload(
            devices=serialize_phone_collection([refreshed_phone]),
        ),
    )


def test_refresh_known_devices_apply_emits_safe_device_id_rebindings() -> None:
    """ADB id changes matched by Tier-1 serial are forwarded to the UI payload."""
    state = MockAdbState(seed=204, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    model_entrypoint = ModelEntrypoint()
    model_entrypoint._adb_server = server
    model_entrypoint._adb_client = client
    paired_phone = Phone(
        id="192.168.0.10:5555",
        state="device",
        hardware_serial="SER-REFRESH",
        model="Pixel",
    )
    refreshed_phone = Phone(
        id="192.168.0.10:37849",
        state="device",
        hardware_serial="SER-REFRESH",
        model="Pixel",
    )
    server.paired_devices.add(paired_phone)
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    outcome = RefreshKnownDevicesOutcome(devices=[refreshed_phone])
    RefreshKnownDevicesWork.apply_main_thread(model_entrypoint, outcome)

    assert server.paired_devices.get("192.168.0.10:5555") is None
    assert server.paired_devices.get("192.168.0.10:37849") is paired_phone
    assert emitted == [
        (
            CoreSignals.DEVICES_UPDATED,
            DevicesUpdatedPayload(
                devices=serialize_phone_collection([paired_phone]),
                device_id_rebindings={"192.168.0.10:5555": "192.168.0.10:37849"},
            ),
        )
    ]


def test_refresh_known_devices_apply_skips_emit_when_devices_unchanged() -> None:
    """Unchanged discovery payloads avoid redundant DEVICES_UPDATED emissions."""
    state = MockAdbState(seed=203, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    model_entrypoint = ModelEntrypoint()
    model_entrypoint._adb_server = server
    model_entrypoint._adb_client = client
    phone = Phone(id="device-1", state="device", model="Pixel")
    server.paired_devices.add(phone)
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    outcome = RefreshKnownDevicesOutcome(
        devices=[Phone(id="device-1", state="device", model="Pixel")]
    )
    RefreshKnownDevicesWork.apply_main_thread(model_entrypoint, outcome)

    assert emitted == []
