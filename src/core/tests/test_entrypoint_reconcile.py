"""Tests for ModelEntrypoint.reconcile_paired_devices."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices.phone import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import CoreSignals, SimulationCreatedPayload
from core.tests.signal_test_helpers import seed_adb_startup_for_entrypoint

pytestmark = [pytest.mark.devices]


def _create_simulation_id(model_entrypoint: ModelEntrypoint, device_id: str) -> str:
    """Create a simulation and return its id via the SIMULATION_CREATED signal."""
    captured: list[str] = []

    def capture(payload: SimulationCreatedPayload) -> None:
        captured.append(payload.simulation_id)

    model_entrypoint.signal_bus.subscribe(CoreSignals.SIMULATION_CREATED, capture)
    model_entrypoint.create_simulation(device_id)
    assert len(captured) == 1
    return captured[0]


def _model_with_server(
    tmp_path: Path,
) -> tuple[ModelEntrypoint, MockAdbServer]:
    state = MockAdbState(seed=303, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    with patch(
        "core.entrypoint.get_or_create_application_dir",
        return_value=tmp_path,
    ):
        model_entrypoint = ModelEntrypoint()
    model_entrypoint._adb_server = server
    model_entrypoint._adb_client = client
    seed_adb_startup_for_entrypoint(model_entrypoint)
    return model_entrypoint, server


def test_reconcile_adds_newly_discovered_device(tmp_path: Path) -> None:
    """A handset absent from paired_devices is added."""
    model_entrypoint, server = _model_with_server(tmp_path)
    discovered = Phone(id="fresh-device", state="device", model="Pixel")

    result = model_entrypoint.reconcile_paired_devices([discovered])

    assert result.changed is True
    assert result.device_id_rebindings == {}
    assert server.paired_devices.get("fresh-device") is discovered


def test_create_simulation_reuses_existing_device_simulation(tmp_path: Path) -> None:
    """Repeat selection of the same device must not create duplicate simulations."""
    model_entrypoint, server = _model_with_server(tmp_path)
    phone = Phone(id="device-1", state="device", model="Pixel")
    server.paired_devices.add(phone)

    first_simulation_id = _create_simulation_id(model_entrypoint, "device-1")

    captured: list[str] = []

    def capture(payload: SimulationCreatedPayload) -> None:
        captured.append(payload.simulation_id)

    model_entrypoint.signal_bus.subscribe(CoreSignals.SIMULATION_CREATED, capture)
    model_entrypoint.create_simulation("device-1")
    second_simulation_id = first_simulation_id

    assert captured == []

    assert first_simulation_id == second_simulation_id
    assert model_entrypoint.get_simulation(first_simulation_id) is not None


def test_create_simulation_persists_last_active_device_id(tmp_path: Path) -> None:
    """Selected device id is written to the simulation repository index."""
    model_entrypoint, server = _model_with_server(tmp_path)
    phone = Phone(id="device-1", state="device", model="Pixel")
    server.paired_devices.add(phone)

    _create_simulation_id(model_entrypoint, "device-1")

    index_payload = json.loads(
        (tmp_path / "simulations" / "index.json").read_text(encoding="utf-8")
    )
    assert index_payload["last_active_device_id"] == "device-1"


def test_reconcile_removes_stale_device_and_simulation(tmp_path: Path) -> None:
    """Handsets missing from discovery are removed and their simulation is dropped."""
    model_entrypoint, server = _model_with_server(tmp_path)
    stale_phone = Phone(id="stale-device", state="device")
    server.paired_devices.add(stale_phone)
    simulation_id = _create_simulation_id(model_entrypoint, "stale-device")

    result = model_entrypoint.reconcile_paired_devices([])

    assert result.changed is True
    assert result.device_id_rebindings == {}
    assert server.paired_devices.get("stale-device") is None
    assert model_entrypoint.get_simulation(simulation_id) is None


def test_reconcile_updates_existing_device_in_place(tmp_path: Path) -> None:
    """Matching ADB ids refresh descriptor fields on the existing Phone instance."""
    model_entrypoint, server = _model_with_server(tmp_path)
    paired = Phone(id="device-1", state="device", model="Old model")
    server.paired_devices.add(paired)
    discovered = Phone(id="device-1", state="offline", model="New model")

    result = model_entrypoint.reconcile_paired_devices([discovered])

    assert result.changed is True
    assert result.device_id_rebindings == {}
    assert server.paired_devices.get("device-1") is paired
    assert paired.descriptor.model == "New model"
    assert paired.descriptor.state == "offline"


def test_reconcile_matches_by_stable_key_when_adb_id_changes(tmp_path: Path) -> None:
    """Reconnects with a new ADB connection id keep the same paired Phone object."""
    model_entrypoint, server = _model_with_server(tmp_path)
    paired = Phone(
        id="192.168.0.10:5555",
        hardware_serial="SER-RECONNECT",
        state="device",
        model="Old model",
    )
    server.paired_devices.add(paired)
    discovered = Phone(
        id="192.168.0.10:37849",
        hardware_serial="SER-RECONNECT",
        state="device",
        model="Updated model",
    )

    result = model_entrypoint.reconcile_paired_devices([discovered])

    assert result.changed is True
    assert result.device_id_rebindings == {"192.168.0.10:5555": "192.168.0.10:37849"}
    assert server.paired_devices.get("192.168.0.10:5555") is None
    assert server.paired_devices.get("192.168.0.10:37849") is paired
    assert paired.descriptor.model == "Updated model"


def test_reconcile_noop_when_discovery_matches_paired(tmp_path: Path) -> None:
    """Identical discovery payloads leave the repository untouched."""
    model_entrypoint, server = _model_with_server(tmp_path)
    paired = Phone(id="device-1", state="device", model="Pixel")
    server.paired_devices.add(paired)
    discovered = Phone(id="device-1", state="device", model="Pixel")

    assert paired == discovered
    result = model_entrypoint.reconcile_paired_devices([discovered])

    assert result.changed is False
    assert result.device_id_rebindings == {}
    assert server.paired_devices.get("device-1") is paired


def test_reconcile_preserves_simulation_reference_on_in_place_update(
    tmp_path: Path,
) -> None:
    """Simulations keep pointing at the same Phone object after descriptor refresh."""
    model_entrypoint, server = _model_with_server(tmp_path)
    paired = Phone(id="device-1", state="device", model="Old model")
    server.paired_devices.add(paired)
    simulation_id = _create_simulation_id(model_entrypoint, "device-1")
    discovered = Phone(id="device-1", state="device", model="New model")

    model_entrypoint.reconcile_paired_devices([discovered])

    simulation = model_entrypoint.get_simulation(simulation_id)
    assert simulation is not None
    assert simulation.device is paired
    assert simulation.device.descriptor.model == "New model"


def test_reconcile_does_not_merge_devices_on_tier2_stable_key_collision(
    tmp_path: Path,
) -> None:
    """Tier-2 fingerprint keys are not safe enough to rebind a different paired phone."""
    model_entrypoint, server = _model_with_server(tmp_path)
    paired_a = Phone(id="10.0.0.1:5555", state="device", model="Pixel 8")
    paired_b = Phone(id="10.0.0.2:5555", state="device", model="Pixel 8")
    discovered_a = Phone(id="10.0.0.1:44444", state="device", model="Pixel 8")
    discovered_b = Phone(id="10.0.0.2:5555", state="device", model="Pixel 8")
    for phone in (paired_a, paired_b, discovered_a, discovered_b):
        phone.manufacturer = "Google"
        phone.model = "Pixel 8"
        phone.hardware_serial = ""
        assert phone.stable_key.startswith("fp:v1:")
    server.paired_devices.add(paired_a)
    server.paired_devices.add(paired_b)

    result = model_entrypoint.reconcile_paired_devices([discovered_a, discovered_b])

    assert result.changed is True
    assert result.device_id_rebindings == {}
    assert server.paired_devices.get("10.0.0.1:5555") is None
    assert server.paired_devices.get("10.0.0.1:44444") is discovered_a
    assert server.paired_devices.get("10.0.0.2:5555") is paired_b
