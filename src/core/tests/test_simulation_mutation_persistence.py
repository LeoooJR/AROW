"""Tests for core-owned simulation mutation and incremental persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from application_paths import ApplicationPaths
from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignals,
    SimulationRestoredPayload,
    SimulationStateChangedPayload,
)
from core.simulation import Simulation
from core.tests.signal_test_helpers import seed_adb_startup_for_entrypoint


def _make_model(tmp_path: Path) -> tuple[ModelEntrypoint, Simulation, Path]:
    model_entrypoint = ModelEntrypoint(
        paths=ApplicationPaths(tmp_path, tmp_path / "config", tmp_path / "src", "linux")
    )
    simulation = Simulation(id="sim-1")
    model_entrypoint.restore_persisted_simulation(simulation)
    seed_adb_startup_for_entrypoint(model_entrypoint)
    model_entrypoint.emit_core_signal(
        CoreSignals.SIMULATION_RESTORED,
        SimulationRestoredPayload(
            simulation_id=simulation.id,
            device_id="device-1",
            device_name="Pixel",
        ),
    )
    metadata_path = tmp_path / "simulations" / simulation.id / "simulation.json"
    return model_entrypoint, simulation, metadata_path


def _read_metadata(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_simulation_mutations_persist_without_controller_wiring(tmp_path: Path) -> None:
    model_entrypoint, simulation, metadata_path = _make_model(tmp_path)

    model_entrypoint.set_simulation_active(simulation.id, True)
    assert _read_metadata(metadata_path)["active"] is True

    model_entrypoint.set_simulation_real_location(simulation.id, 48.1, 2.1)
    assert _read_metadata(metadata_path)["real_location"] == {
        "lat": 48.1,
        "lon": 2.1,
        "poi": None,
    }

    model_entrypoint.set_simulation_spoofed_location(simulation.id, 48.2, 2.2)
    assert _read_metadata(metadata_path)["spoofed_location"] == {
        "lat": 48.2,
        "lon": 2.2,
        "poi": None,
    }

    map_path = tmp_path / "simulations" / simulation.id / "map" / "sim-1.html"
    model_entrypoint.set_simulation_map_file(simulation.id, map_path)
    assert _read_metadata(metadata_path)["map_file"] == "map/sim-1.html"

    model_entrypoint.clear_simulation_map_file(simulation.id)
    assert _read_metadata(metadata_path)["map_file"] is None


def test_unchanged_mutation_does_not_write_or_emit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model_entrypoint, simulation, _metadata_path = _make_model(tmp_path)
    model_entrypoint.set_simulation_active(simulation.id, True)
    emitted: list[SimulationStateChangedPayload] = []

    def capture(payload: SimulationStateChangedPayload) -> None:
        emitted.append(payload)

    model_entrypoint.signal_bus.subscribe(CoreSignals.SIMULATION_STATE_CHANGED, capture)

    def fail_write(_simulation: Simulation) -> Path:
        raise AssertionError("unchanged state must not be persisted")

    monkeypatch.setattr(
        model_entrypoint._simulation_service._simulations,
        "write_simulation",
        fail_write,
    )

    model_entrypoint.set_simulation_active(simulation.id, True)

    assert emitted == []


def test_incremental_write_failure_keeps_mutation_and_emits_signal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    log_records,
) -> None:
    model_entrypoint, simulation, _metadata_path = _make_model(tmp_path)
    emitted: list[SimulationStateChangedPayload] = []

    def capture(payload: SimulationStateChangedPayload) -> None:
        emitted.append(payload)

    model_entrypoint.signal_bus.subscribe(CoreSignals.SIMULATION_STATE_CHANGED, capture)

    def fail_write(_simulation: Simulation) -> Path:
        raise OSError("disk unavailable")

    monkeypatch.setattr(
        model_entrypoint._simulation_service._simulations,
        "write_simulation",
        fail_write,
    )

    model_entrypoint.set_simulation_active(simulation.id, True)

    assert simulation.active is True
    assert emitted == [
        SimulationStateChangedPayload(simulation_id=simulation.id, active=True)
    ]
    assert any(
        record["message"] == "Simulation persistence failed after state mutation"
        for record in log_records
    )
