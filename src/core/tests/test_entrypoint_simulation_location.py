"""Tests for ModelEntrypoint simulation marker location validation."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices import Phone
from core.entrypoint import ModelEntrypoint
from core.geo.location import clear_referentiel_pk_cache
from core.signals import CoreSignal, SimulationLocationValidatedPayload


@pytest.fixture(autouse=True)
def _clear_referentiel_cache() -> Iterator[None]:
    clear_referentiel_pk_cache()
    yield
    clear_referentiel_pk_cache()


def _make_model(tmp_path: Path) -> ModelEntrypoint:
    state = MockAdbState(seed=501, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    device = Phone(id="device-1", state="device", model="Pixel")
    server.paired_devices.add(device)
    with patch(
        "core.entrypoint.get_or_create_application_dir",
        return_value=tmp_path,
    ):
        model_entrypoint = ModelEntrypoint()
    model_entrypoint._adb_server = server
    model_entrypoint._adb_client = client
    model_entrypoint.create_simulation("device-1")
    return model_entrypoint


def test_validate_simulation_marker_location_emits_validated_payload(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(tmp_path)
    simulation_id = next(iter(model_entrypoint._simulations)).id
    captured: list[SimulationLocationValidatedPayload] = []

    def capture(payload: SimulationLocationValidatedPayload) -> None:
        captured.append(payload)

    model_entrypoint.subscribe(CoreSignal.SIMULATION_LOCATION_VALIDATED, capture)
    model_entrypoint.validate_simulation_marker_location(
        simulation_id,
        "001+000",
        "001000-1",
        48.88533318609319,
        2.363530409238113,
    )

    assert len(captured) == 1
    assert captured[0].simulation_id == simulation_id
    assert captured[0].marker_id == "001+000"
    assert captured[0].line == "001000-1"
    assert captured[0].lat == pytest.approx(48.88533318609319)
    assert captured[0].lon == pytest.approx(2.363530409238113)


def test_validate_simulation_marker_location_missing_simulation_raises(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(tmp_path)
    captured: list[SimulationLocationValidatedPayload] = []

    def capture(payload: SimulationLocationValidatedPayload) -> None:
        captured.append(payload)

    model_entrypoint.subscribe(
        CoreSignal.SIMULATION_LOCATION_VALIDATED,
        capture,
    )

    with pytest.raises(ValueError, match="Simulation with id missing not found"):
        model_entrypoint.validate_simulation_marker_location(
            "missing",
            "001+000",
            "001000-1",
            48.88533318609319,
            2.363530409238113,
        )

    assert captured == []


def test_validate_simulation_marker_location_invalid_marker_raises_without_emit(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(tmp_path)
    simulation_id = next(iter(model_entrypoint._simulations)).id
    captured: list[SimulationLocationValidatedPayload] = []

    def capture(payload: SimulationLocationValidatedPayload) -> None:
        captured.append(payload)

    model_entrypoint.subscribe(
        CoreSignal.SIMULATION_LOCATION_VALIDATED,
        capture,
    )

    with pytest.raises(ValueError, match="Unknown milestone marker id"):
        model_entrypoint.validate_simulation_marker_location(
            simulation_id,
            "999+999",
            "001000-1",
            0.0,
            0.0,
        )

    assert captured == []
