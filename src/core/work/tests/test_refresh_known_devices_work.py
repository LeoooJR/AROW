"""Tests for src/core/work/refresh_known_devices_work.py (shell enrichment orchestration)."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices.phone import AdbConnection, Phone, serialize_phone_collection
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


def _phone(
    connection_id: str,
    *,
    state: str = "device",
    model: str = "",
    hardware_serial: str = "",
    observed_at: datetime.datetime | None = None,
) -> Phone:
    return Phone(
        AdbConnection.observed(
            connection_id,
            state=state,
            observed_at=observed_at,
        ),
        model=model,
        hardware_serial=hardware_serial,
    )


def test_enrich_phones_with_adb_shell_properties_empty_skips_adb_methods() -> None:
    """No phones implies no getters on the client (fast path)."""
    client = MagicMock()
    enrich_phones_with_adb_shell_properties(client, [])
    client.assert_not_called()


def test_enrich_phones_with_adb_shell_properties_skips_non_targetable_phone() -> None:
    """Only devices in executable ADB state receive shell enrichment."""
    client = MagicMock()
    phone = _phone("offline-phone", state="offline")

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
    phone = _phone("target-phone")

    enrich_phones_with_adb_shell_properties(client, [phone])

    client.get_shell_enrichment_properties.assert_called_once_with(
        phone.target_connection
    )
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
    server.start()
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
    model_entrypoint.adb_server = server
    model_entrypoint.adb_client = client
    stale_phone = _phone("stale-device")
    refreshed_phone = _phone("fresh-device")
    server.paired_devices.add(stale_phone)
    emitted: list[tuple[CoreSignal[Any], object]] = []

    def fake_emit(signal: CoreSignal[Any], payload: object) -> None:
        emitted.append((signal, payload))

    model_entrypoint.emit_core_signal = fake_emit  # type: ignore[method-assign]

    outcome = RefreshKnownDevicesOutcome(devices=[refreshed_phone])
    RefreshKnownDevicesWork.apply_main_thread(model_entrypoint, outcome)

    assert server.paired_devices.get(stale_phone.id) is None
    assert server.paired_devices.get(refreshed_phone.id) is refreshed_phone
    assert emitted == [
        (
            CoreSignals.SIMULATION_DELETE_SKIPPED,
            SimulationDeleteSkippedPayload(
                device_id=stale_phone.id,
                reason=f"Simulation for device with id {stale_phone.id} not found",
            ),
        ),
        (
            CoreSignals.DEVICES_UPDATED,
            DevicesUpdatedPayload(
                devices=serialize_phone_collection([refreshed_phone]),
            ),
        ),
    ]


def test_refresh_known_devices_apply_rebinds_connection_without_phone_id_change() -> (
    None
):
    """A Tier-1 match replaces the endpoint without replacing physical identity."""
    state = MockAdbState(seed=204, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    model_entrypoint = ModelEntrypoint()
    model_entrypoint.adb_server = server
    model_entrypoint.adb_client = client
    paired_phone = _phone(
        "192.168.0.10:5555",
        hardware_serial="SER-REFRESH",
        model="Pixel",
    )
    refreshed_phone = _phone(
        "192.168.0.10:37849",
        hardware_serial="SER-REFRESH",
        model="Pixel",
    )
    server.paired_devices.add(paired_phone)
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint.emit_core_signal = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    outcome = RefreshKnownDevicesOutcome(devices=[refreshed_phone])
    RefreshKnownDevicesWork.apply_main_thread(model_entrypoint, outcome)

    assert server.paired_devices.get(paired_phone.id) is paired_phone
    assert server.paired_devices.get_by_connection_id("192.168.0.10:5555") is None
    assert (
        server.paired_devices.get_by_connection_id("192.168.0.10:37849") is paired_phone
    )
    assert emitted == [
        (
            CoreSignals.DEVICES_UPDATED,
            DevicesUpdatedPayload(
                devices=serialize_phone_collection([paired_phone]),
                phone_id_rebindings={},
            ),
        )
    ]


def test_refresh_known_devices_apply_skips_emit_when_devices_unchanged() -> None:
    """Unchanged discovery payloads avoid redundant DEVICES_UPDATED emissions."""
    state = MockAdbState(seed=203, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    model_entrypoint = ModelEntrypoint()
    model_entrypoint.adb_server = server
    model_entrypoint.adb_client = client
    phone = _phone("device-1", model="Pixel")
    server.paired_devices.add(phone)
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint.emit_core_signal = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    unchanged = Phone(phone.connections[0], model="Pixel")
    outcome = RefreshKnownDevicesOutcome(devices=[unchanged])
    RefreshKnownDevicesWork.apply_main_thread(model_entrypoint, outcome)

    assert emitted == []


def test_refresh_known_devices_apply_emits_timestamp_only_active_update() -> None:
    state = MockAdbState(seed=205, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    model_entrypoint = ModelEntrypoint()
    model_entrypoint.adb_server = server
    model_entrypoint.adb_client = client
    paired = _phone(
        "device-1",
        model="Pixel",
        observed_at=datetime.datetime(2025, 6, 15, 10, 30),
    )
    discovered = _phone(
        "device-1",
        model="Pixel",
        observed_at=datetime.datetime(2025, 6, 15, 10, 31),
    )
    server.paired_devices.add(paired)
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint.emit_core_signal = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    RefreshKnownDevicesWork.apply_main_thread(
        model_entrypoint,
        RefreshKnownDevicesOutcome(devices=[discovered]),
    )

    assert server.paired_devices.get(paired.id) is paired
    assert paired.connections[0].last_connection == datetime.datetime(
        2025, 6, 15, 10, 31
    )
    assert emitted == [
        (
            CoreSignals.DEVICES_UPDATED,
            DevicesUpdatedPayload(devices=serialize_phone_collection([paired])),
        )
    ]
