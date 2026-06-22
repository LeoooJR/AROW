"""Tests for SimulationRepository JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.devices import Phone
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
    }


def test_add_updates_index(tmp_path: Path) -> None:
    repository = SimulationRepository(tmp_path / "simulations")
    simulation = Simulation(id="sim-1")
    repository.add(simulation)

    payload = json.loads(repository.index_file.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
        "simulations": ["sim-1"],
    }


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
