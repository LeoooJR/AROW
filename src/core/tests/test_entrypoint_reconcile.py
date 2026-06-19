"""Tests for ModelEntrypoint.reconcile_paired_devices."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices import (
    Phone,
    apply_phone_manufacturer_enrichment,
    apply_phone_product_model_enrichment,
    apply_phone_ro_serial_enrichment,
)
from core.entrypoint import ModelEntrypoint
from core.signals import CoreSignal, SimulationCreatedPayload
from core.simulation import SimulationRepository

pytestmark = [pytest.mark.devices]


def _create_simulation_id(model_entrypoint: ModelEntrypoint, device_id: str) -> str:
    """Create a simulation and return its id via the SIMULATION_CREATED signal."""
    captured: list[str] = []

    def capture(payload: SimulationCreatedPayload) -> None:
        captured.append(payload.simulation.id)

    model_entrypoint.subscribe(CoreSignal.SIMULATION_CREATED, capture)
    model_entrypoint.create_simulation(device_id)
    assert len(captured) == 1
    return captured[0]


def _model_with_server(
    tmp_path: Path,
) -> tuple[ModelEntrypoint, MockAdbServer]:
    state = MockAdbState(seed=303, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    model_entrypoint = ModelEntrypoint()
    model_entrypoint._adb_server = server
    model_entrypoint._adb_client = client
    model_entrypoint._simulations = SimulationRepository(tmp_path / "simulations")
    return model_entrypoint, server


def test_reconcile_adds_newly_discovered_device(tmp_path: Path) -> None:
    """A handset absent from paired_devices is added."""
    model_entrypoint, server = _model_with_server(tmp_path)
    discovered = Phone(id="fresh-device", state="device", model="Pixel")

    changed = model_entrypoint.reconcile_paired_devices([discovered])

    assert changed is True
    assert server.paired_devices.get("fresh-device") is discovered


def test_create_simulation_reuses_existing_device_simulation(tmp_path: Path) -> None:
    """Repeat selection of the same device must not create duplicate simulations."""
    model_entrypoint, server = _model_with_server(tmp_path)
    phone = Phone(id="device-1", state="device", model="Pixel")
    server.paired_devices.add(phone)

    first_simulation_id = _create_simulation_id(model_entrypoint, "device-1")
    second_simulation_id = _create_simulation_id(model_entrypoint, "device-1")

    assert first_simulation_id == second_simulation_id
    assert len(list(model_entrypoint._simulations)) == 1


def test_reconcile_removes_stale_device_and_simulation(tmp_path: Path) -> None:
    """Handsets missing from discovery are removed and their simulation is dropped."""
    model_entrypoint, server = _model_with_server(tmp_path)
    stale_phone = Phone(id="stale-device", state="device")
    server.paired_devices.add(stale_phone)
    simulation_id = _create_simulation_id(model_entrypoint, "stale-device")

    changed = model_entrypoint.reconcile_paired_devices([])

    assert changed is True
    assert server.paired_devices.get("stale-device") is None
    assert model_entrypoint.get_simulation(simulation_id) is None


def test_reconcile_updates_existing_device_in_place(tmp_path: Path) -> None:
    """Matching ADB ids refresh descriptor fields on the existing Phone instance."""
    model_entrypoint, server = _model_with_server(tmp_path)
    paired = Phone(id="device-1", state="device", model="Old model")
    server.paired_devices.add(paired)
    discovered = Phone(id="device-1", state="offline", model="New model")

    changed = model_entrypoint.reconcile_paired_devices([discovered])

    assert changed is True
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

    changed = model_entrypoint.reconcile_paired_devices([discovered])

    assert changed is True
    assert server.paired_devices.get("192.168.0.10:5555") is None
    assert server.paired_devices.get("192.168.0.10:37849") is paired
    assert paired.descriptor.model == "Updated model"


def test_reconcile_noop_when_discovery_matches_paired(tmp_path: Path) -> None:
    """Identical discovery payloads leave the repository untouched."""
    model_entrypoint, server = _model_with_server(tmp_path)
    paired = Phone(id="device-1", state="device", model="Pixel")
    server.paired_devices.add(paired)
    discovered = Phone(id="device-1", state="device", model="Pixel")

    changed = model_entrypoint.reconcile_paired_devices([discovered])

    assert changed is False
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
        apply_phone_manufacturer_enrichment(phone, "Google")
        apply_phone_product_model_enrichment(phone, "Pixel 8")
        apply_phone_ro_serial_enrichment(phone, "")
        assert phone.stable_key.startswith("fp:v1:")
    server.paired_devices.add(paired_a)
    server.paired_devices.add(paired_b)

    changed = model_entrypoint.reconcile_paired_devices([discovered_a, discovered_b])

    assert changed is True
    assert server.paired_devices.get("10.0.0.1:5555") is None
    assert server.paired_devices.get("10.0.0.1:44444") is discovered_a
    assert server.paired_devices.get("10.0.0.2:5555") is paired_b
