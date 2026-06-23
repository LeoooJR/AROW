"""Tests for SimulationRepository JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.devices import Phone, PhoneRepository
from core.location import Location
from core.simulation import (
    INDEX_FILENAME,
    SIMULATION_FILENAME,
    SIMULATION_REPOSITORY_SCHEMA_VERSION,
    Simulation,
    SimulationRepository,
)


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


def test_add_updates_index(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    simulation = Simulation(id="sim-1")
    repository.add(simulation)

    payload = json.loads(repository.index_file.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
        "simulations": ["sim-1"],
        "last_active_device_id": None,
    }


def test_phone_from_payload_rebuilds_persisted_fields() -> None:
    phone = Phone(id="device-1", name="Pixel", state="device", ip="10.0.0.5", port=5555)
    payload = phone.to_payload()
    restored = Phone.from_payload(payload)

    assert restored.id == phone.id
    assert restored.name == phone.name
    assert restored.os == phone.os
    assert restored.ip == phone.ip
    assert restored.port == phone.port
    assert restored.state == phone.state
    assert restored.stable_key == phone.stable_key


def test_simulation_from_payload_rebuilds_fields(tmp_path: Path) -> None:
    device = Phone(id="device-1", name="Pixel", state="device")
    simulation_dir = tmp_path / "sim-1"
    map_file = simulation_dir / "map" / "sim-1.html"
    log_file = simulation_dir / "sim-1.log"
    map_file.parent.mkdir(parents=True, exist_ok=True)
    map_file.write_text("<html></html>", encoding="utf-8")
    log_file.write_text("log", encoding="utf-8")
    simulation = Simulation(
        id="sim-1",
        device=device,
        real_location=Location(lat=1.0, lon=2.0, label="real"),
        fake_location=Location(lat=3.0, lon=4.0, label="fake"),
        map_file=map_file,
        log_file=log_file,
        active=True,
    )
    payload = simulation.to_payload(simulation_dir)
    restored = Simulation.from_payload(payload, simulation_dir)

    assert restored.id == "sim-1"
    assert restored.device is not None
    assert restored.device.id == "device-1"
    assert restored.real_location == simulation.real_location
    assert restored.fake_location == simulation.fake_location
    assert restored.map_file == map_file
    assert restored.log_file == log_file
    assert restored.active is True


def test_load_all_for_devices_binds_existing_phone_instance(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    paired_phone = Phone(id="device-1", name="Pixel", state="device")
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


def test_load_all_for_devices_deletes_stale_simulation(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    stale_device = Phone(id="missing-device", name="Ghost", state="device")
    simulation = Simulation(id="sim-stale", device=stale_device)
    repository.add(simulation)
    repository.write_all()

    loaded_repository = SimulationRepository(tmp_path / "simulations")
    loaded = loaded_repository.load_all_for_devices(PhoneRepository())

    assert loaded == []
    assert not loaded_repository.simulation_dir("sim-stale").exists()
    index_payload = json.loads(loaded_repository.index_file.read_text(encoding="utf-8"))
    assert index_payload["simulations"] == []


def test_write_all_writes_simulation_json_and_index_last(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    device = Phone(id="device-1", name="Pixel", state="device")
    simulation_one = Simulation(
        id="sim-1",
        device=device,
        real_location=Location(lat=1.0, lon=2.0, label="real"),
        fake_location=Location(lat=3.0, lon=4.0, label="fake"),
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
        "device": {
            "id": "device-1",
            "name": "Pixel",
            "os": "",
            "ip": "",
            "port": None,
            "state": "device",
            "stable_key": device.stable_key,
        },
        "real_location": {"lat": 1.0, "lon": 2.0, "label": "real"},
        "fake_location": {"lat": 3.0, "lon": 4.0, "label": "fake"},
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
        repository.write_simulation(simulation)

    target = repository.save_dir / relative_path
    assert target.is_file()
    assert not target.with_suffix(target.suffix + ".tmp").exists()
