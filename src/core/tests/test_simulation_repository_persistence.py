"""Tests for SimulationRepository JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.devices.phone import Phone, PhoneRepository
from core.geo.location import Location
from core.simulation import (
    INDEX_FILENAME,
    SIMULATION_FILENAME,
    SIMULATION_REPOSITORY_SCHEMA_VERSION,
    Simulation,
    SimulationDiskStore,
    SimulationRepository,
)
from core.tests.phone_test_factory import make_phone


def test_init_writes_empty_index(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")

    index_path = repository.index_file
    assert index_path.is_file()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
        "simulations": [],
        "last_active_device_id": None,
    }


def test_init_loads_last_active_device_id_from_index(tmp_path: Path) -> None:
    save_dir = tmp_path / "simulations"
    save_dir.mkdir(parents=True)
    index_path = save_dir / INDEX_FILENAME
    index_path.write_text(
        json.dumps(
            {
                "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
                "simulations": [],
                "last_active_device_id": "device-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    repository = SimulationRepository(save_dir)

    assert repository.last_active_device_id == "device-1"


def test_set_last_active_device_id_persists_to_index(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")

    repository.last_active_device_id = "device-1"

    payload = json.loads(repository.index_file.read_text(encoding="utf-8"))
    assert payload["last_active_device_id"] == "device-1"
    assert repository.last_active_device_id == "device-1"


def test_load_all_for_devices_clears_last_active_when_device_missing(
    tmp_path: Path,
) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    repository.last_active_device_id = "missing-device"

    loaded_repository = SimulationRepository(tmp_path / "simulations")
    loaded_repository.load_all_for_devices(PhoneRepository())

    assert loaded_repository.last_active_device_id is None
    index_payload = json.loads(loaded_repository.index_file.read_text(encoding="utf-8"))
    assert index_payload["last_active_device_id"] is None


def test_init_preserves_existing_index(tmp_path: Path) -> None:
    save_dir = tmp_path / "simulations"
    save_dir.mkdir(parents=True)
    index_path = save_dir / INDEX_FILENAME
    index_path.write_text(
        json.dumps(
            {
                "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
                "simulations": ["sim-1"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    repository = SimulationRepository(save_dir)

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
        "simulations": ["sim-1"],
    }
    assert repository.last_active_device_id is None


def test_add_updates_index_and_writes_metadata(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    simulation = Simulation(id="sim-1")
    repository.add(simulation)

    payload = json.loads(repository.index_file.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
        "simulations": ["sim-1"],
        "last_active_device_id": None,
    }
    assert repository.simulation_metadata_file("sim-1").is_file()


def test_add_only_survives_reload_without_write_all(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    paired_phone = make_phone(id="device-1", name="Pixel", state="device")
    simulation = Simulation(id="sim-1", device=paired_phone, active=False)
    repository.add(simulation)

    paired_devices = PhoneRepository()
    paired_devices.add(paired_phone)
    state = SimulationDiskStore(tmp_path / "simulations").load_for_devices(
        paired_devices
    )

    assert len(state.simulations) == 1
    assert state.simulations[0].id == "sim-1"
    assert state.simulations[0].device is paired_phone


def test_phone_from_payload_rebuilds_persisted_fields() -> None:
    phone = make_phone(
        id="device-1", name="Pixel", state="device", ip="10.0.0.5", port=5555
    )
    payload = phone.serialize(json_compatible=False)
    restored = Phone.deserialize(payload)

    assert restored.id == phone.id
    assert restored.name == phone.name
    assert restored.os == phone.os
    assert restored.connections == phone.connections
    assert restored.stable_key == phone.stable_key


def test_simulation_from_payload_rebuilds_fields(tmp_path: Path) -> None:
    device = make_phone(id="device-1", name="Pixel", state="device")
    simulation_dir = tmp_path / "sim-1"
    map_file = simulation_dir / "map" / "sim-1.html"
    log_file = simulation_dir / "sim-1.log"
    map_file.parent.mkdir(parents=True, exist_ok=True)
    map_file.write_text("<html></html>", encoding="utf-8")
    log_file.write_text("log", encoding="utf-8")
    simulation = Simulation(
        id="sim-1",
        device=device,
        real_location=Location(lat=1.0, lon=2.0, poi=None),
        spoofed_location=Location(lat=3.0, lon=4.0, poi=None),
        map_file=map_file,
        log_file=log_file,
        active=True,
    )
    payload = simulation.serialize(simulation_dir, json_compatible=True)
    restored = Simulation.deserialize(payload, simulation_dir)

    assert restored.id == "sim-1"
    assert restored.device is not None
    assert restored.device.id == "device-1"
    assert restored.real_location == simulation.real_location
    assert restored.spoofed_location == simulation.spoofed_location
    assert restored.map_file == map_file
    assert restored.log_file == log_file
    assert restored.active is True
    assert restored.device.connections == device.connections


def test_simulation_deserialize_ignores_legacy_device_timestamp(tmp_path: Path) -> None:
    device = make_phone(id="device-1", name="Pixel", state="device")
    simulation = Simulation(id="sim-1", device=device)
    simulation_dir = tmp_path / "sim-1"
    payload = simulation.serialize(simulation_dir, json_compatible=True)
    device_payload = payload["device"]
    assert isinstance(device_payload, dict)
    device_payload.pop("connections")
    device_payload.pop("preferred_connection_id")
    device_payload["id"] = "device-1"
    device_payload["state"] = "offline"
    device_payload["last_communication"] = "2025-06-15T10:30:00"

    restored = Simulation.deserialize(payload, simulation_dir)

    assert restored.device is not None
    assert restored.device.connections[0].id == "device-1"
    assert restored.device.connections[0].last_connection is None


def test_simulation_payload_round_trips_external_artifact_paths(
    tmp_path: Path,
) -> None:
    simulation_dir = tmp_path / "sim-1"
    external_dir = tmp_path / "external"
    external_dir.mkdir(parents=True)
    map_file = external_dir / "sim-1.html"
    log_file = external_dir / "sim-1.log"
    map_file.write_text("<html></html>", encoding="utf-8")
    log_file.write_text("log", encoding="utf-8")
    simulation = Simulation(
        id="sim-1",
        map_file=map_file,
        log_file=log_file,
    )

    payload = simulation.serialize(simulation_dir, json_compatible=True)
    restored = Simulation.deserialize(payload, simulation_dir)

    assert payload["map_file"] == str(map_file)
    assert payload["log_file"] == str(log_file)
    assert restored.map_file == map_file
    assert restored.log_file == log_file


def test_disk_store_load_for_devices_binds_paired_phone(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    paired_phone = make_phone(id="device-1", name="Pixel", state="device")
    simulation = Simulation(id="sim-1", device=paired_phone, active=False)
    repository.add(simulation)
    repository.write_all()

    paired_devices = PhoneRepository()
    paired_devices.add(paired_phone)
    state = SimulationDiskStore(tmp_path / "simulations").load_for_devices(
        paired_devices
    )

    assert len(state.simulations) == 1
    assert state.simulations[0].device is paired_phone
    assert state.last_active_device_id is None


def test_load_all_for_devices_binds_existing_phone_instance(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    paired_phone = make_phone(id="device-1", name="Pixel", state="device")
    simulation = Simulation(
        id="sim-1",
        device=paired_phone,
        active=False,
    )
    repository.add(simulation)
    repository.write_all()

    loaded_repository = SimulationRepository(tmp_path / "simulations")
    paired_devices = PhoneRepository()
    paired_devices.add(paired_phone)
    loaded = loaded_repository.load_all_for_devices(paired_devices)

    assert len(loaded) == 1
    assert loaded[0].device is paired_phone
    assert loaded_repository.get("sim-1") is loaded[0]


def test_load_all_for_devices_rebinds_simulation_by_stable_key_when_adb_id_changes(
    tmp_path: Path,
) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    persisted_phone = make_phone(
        id="device-old",
        name="Pixel",
        state="device",
        hardware_serial="SER-123",
    )
    simulation = Simulation(id="sim-1", device=persisted_phone, active=True)
    repository.add(simulation)
    repository.last_active_device_id = persisted_phone.id
    repository.write_all()

    rebound_phone = make_phone(
        id="device-new",
        name="Pixel",
        state="device",
        hardware_serial="SER-123",
    )
    paired_devices = PhoneRepository()
    paired_devices.add(rebound_phone)

    loaded_repository = SimulationRepository(tmp_path / "simulations")
    loaded = loaded_repository.load_all_for_devices(paired_devices)

    assert len(loaded) == 1
    assert loaded[0].device is rebound_phone
    assert loaded_repository.last_active_device_id == rebound_phone.id
    index_payload = json.loads(loaded_repository.index_file.read_text(encoding="utf-8"))
    assert index_payload["last_active_device_id"] == rebound_phone.id
    assert loaded_repository.simulation_dir("sim-1").exists()


def test_load_all_for_devices_does_not_rebind_by_collision_prone_stable_key(
    tmp_path: Path,
) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    persisted_phone = make_phone(
        id="device-old",
        name="Pixel",
        state="device",
        product="pixel",
        model="Pixel 8",
        manufacturer="Google",
    )
    persisted_phone.hardware_serial = ""
    assert persisted_phone.stable_key.startswith("fp:v1:")
    simulation = Simulation(id="sim-1", device=persisted_phone, active=True)
    repository.add(simulation)
    repository.last_active_device_id = persisted_phone.id
    repository.write_all()

    rebound_phone = make_phone(
        id="device-new",
        name="Pixel",
        state="device",
        product="pixel",
        model="Pixel 8",
        manufacturer="Google",
    )
    rebound_phone.hardware_serial = ""
    assert rebound_phone.stable_key == persisted_phone.stable_key
    paired_devices = PhoneRepository()
    paired_devices.add(rebound_phone)

    loaded_repository = SimulationRepository(tmp_path / "simulations")
    loaded = loaded_repository.load_all_for_devices(paired_devices)

    assert loaded == []
    assert loaded_repository.last_active_device_id is None
    assert not loaded_repository.simulation_dir("sim-1").exists()
    index_payload = json.loads(loaded_repository.index_file.read_text(encoding="utf-8"))
    assert index_payload["simulations"] == []
    assert index_payload["last_active_device_id"] is None


def test_load_all_for_devices_deletes_stale_simulation(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    stale_device = make_phone(id="missing-device", name="Ghost", state="device")
    simulation = Simulation(id="sim-stale", device=stale_device)
    repository.add(simulation)
    repository.write_all()

    loaded_repository = SimulationRepository(tmp_path / "simulations")
    loaded = loaded_repository.load_all_for_devices(PhoneRepository())

    assert loaded == []
    assert not loaded_repository.simulation_dir("sim-stale").exists()
    index_payload = json.loads(loaded_repository.index_file.read_text(encoding="utf-8"))
    assert index_payload["simulations"] == []


def test_load_all_for_devices_deletes_invalid_persisted_simulation(
    tmp_path: Path,
) -> None:
    save_dir = tmp_path / "simulations"
    repository = SimulationRepository(save_dir)
    paired_phone = make_phone(id="device-1", name="Pixel", state="device")
    simulation = Simulation(id="sim-1", device=paired_phone)
    repository.add(simulation)
    repository.write_all()
    metadata_path = repository.simulation_metadata_file("sim-1")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 999
    metadata_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    loaded_repository = SimulationRepository(save_dir)
    paired_devices = PhoneRepository()
    paired_devices.add(paired_phone)

    loaded = loaded_repository.load_all_for_devices(paired_devices)

    assert loaded == []
    assert not loaded_repository.simulation_dir("sim-1").exists()
    index_payload = json.loads(loaded_repository.index_file.read_text(encoding="utf-8"))
    assert index_payload["simulations"] == []


def test_load_all_for_devices_deletes_simulation_with_missing_location_payload(
    tmp_path: Path,
) -> None:
    save_dir = tmp_path / "simulations"
    repository = SimulationRepository(save_dir)
    paired_phone = make_phone(id="device-1", name="Pixel", state="device")
    simulation = Simulation(id="sim-1", device=paired_phone)
    repository.add(simulation)
    repository.write_all()
    metadata_path = repository.simulation_metadata_file("sim-1")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("real_location")
    metadata_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    loaded_repository = SimulationRepository(save_dir)
    paired_devices = PhoneRepository()
    paired_devices.add(paired_phone)

    loaded = loaded_repository.load_all_for_devices(paired_devices)

    assert loaded == []
    assert not loaded_repository.simulation_dir("sim-1").exists()
    index_payload = json.loads(loaded_repository.index_file.read_text(encoding="utf-8"))
    assert index_payload["simulations"] == []


def test_load_all_for_devices_deletes_simulation_without_persisted_device(
    tmp_path: Path,
) -> None:
    save_dir = tmp_path / "simulations"
    repository = SimulationRepository(save_dir)
    paired_phone = make_phone(id="device-1", name="Pixel", state="device")
    simulation = Simulation(id="sim-1", device=paired_phone)
    repository.add(simulation)
    repository.write_all()
    metadata_path = repository.simulation_metadata_file("sim-1")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload["device"] = None
    metadata_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    loaded_repository = SimulationRepository(save_dir)
    paired_devices = PhoneRepository()
    paired_devices.add(paired_phone)

    loaded = loaded_repository.load_all_for_devices(paired_devices)

    assert loaded == []
    assert not loaded_repository.simulation_dir("sim-1").exists()
    index_payload = json.loads(loaded_repository.index_file.read_text(encoding="utf-8"))
    assert index_payload["simulations"] == []


def test_write_all_writes_simulation_json_and_index_last(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    device = make_phone(id="device-1", name="Pixel", state="device")
    simulation_one = Simulation(
        id="sim-1",
        device=device,
        real_location=Location(lat=1.0, lon=2.0, poi=None),
        spoofed_location=Location(lat=3.0, lon=4.0, poi=None),
        active=True,
    )
    simulation_two = Simulation(id="sim-2")
    repository.add(simulation_one)
    repository.add(simulation_two)

    simulation_dir = repository.simulation_dir("sim-1")
    map_file = simulation_dir / "map" / "sim-1.html"
    map_file.parent.mkdir(parents=True, exist_ok=True)
    map_file.write_text("<html></html>", encoding="utf-8")
    simulation_one.map_file = map_file

    repository.write_all()

    simulation_payload = json.loads(
        repository.simulation_metadata_file("sim-1").read_text(encoding="utf-8")
    )
    assert simulation_payload == {
        "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
        "id": "sim-1",
        "device": device.serialize(json_compatible=True),
        "real_location": {"lat": 1.0, "lon": 2.0, "poi": None},
        "spoofed_location": {"lat": 3.0, "lon": 4.0, "poi": None},
        "map_file": "map/sim-1.html",
        "log_file": "sim-1.log",
        "active": True,
    }

    index_payload = json.loads(repository.index_file.read_text(encoding="utf-8"))
    assert index_payload == {
        "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
        "simulations": ["sim-1", "sim-2"],
        "last_active_device_id": None,
    }
    assert repository.simulation_metadata_file("sim-2").is_file()


def test_remove_updates_index(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    simulation = Simulation(id="sim-1")
    repository.add(simulation)
    repository.remove(simulation)

    payload = json.loads(repository.index_file.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
        "simulations": [],
        "last_active_device_id": None,
    }


def test_remove_rejects_same_id_clone_without_deleting_persisted_state(
    tmp_path: Path,
) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    stored = Simulation(id="sim-1")
    repository.add(stored)
    simulation_dir = repository.simulation_dir(stored.id)

    with pytest.raises(ValueError, match="not the stored repository instance"):
        repository.remove(Simulation(id="sim-1"))

    assert repository.get("sim-1") is stored
    assert simulation_dir.is_dir()
    assert repository.simulation_metadata_file("sim-1").is_file()
    index_payload = json.loads(repository.index_file.read_text(encoding="utf-8"))
    assert index_payload["simulations"] == ["sim-1"]


@pytest.mark.parametrize(
    ("filename", "relative_path"),
    [
        (INDEX_FILENAME, INDEX_FILENAME),
        (SIMULATION_FILENAME, f"sim-1/{SIMULATION_FILENAME}"),
    ],
)
def test_json_files_use_atomic_suffix_pattern(
    tmp_path: Path, filename: str, relative_path: str
) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    if filename == SIMULATION_FILENAME:
        simulation = Simulation(id="sim-1")
        repository.add(simulation)

    target = repository.save_dir / relative_path
    assert target.is_file()
    assert not target.with_suffix(target.suffix + ".tmp").exists()
