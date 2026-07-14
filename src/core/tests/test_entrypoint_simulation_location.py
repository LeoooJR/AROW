"""Tests for ModelEntrypoint simulation marker location validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices.phone import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignals,
    SimulationCreatedPayload,
    SimulationLocationRejectedPayload,
    SimulationLocationValidatedPayload,
)
from core.tests.geo_fixtures import (
    SAMPLE_LATITUDE,
    SAMPLE_LINE_CODE,
    SAMPLE_LINE_TRONCON,
    SAMPLE_LONGITUDE,
)
from core.tests.signal_test_helpers import seed_adb_startup_for_entrypoint
from core.work.validate_simulation_marker_location_work import (
    ValidateSimulationMarkerLocationOutcome,
)

pytestmark = pytest.mark.usefixtures("clear_lignes_cache")


def _make_model(tmp_path: Path) -> tuple[ModelEntrypoint, str]:
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
    model_entrypoint.adb_server = server
    model_entrypoint.adb_client = client
    seed_adb_startup_for_entrypoint(model_entrypoint)
    captured_ids: list[str] = []

    def capture(payload: SimulationCreatedPayload) -> None:
        captured_ids.append(payload.simulation_id)

    model_entrypoint.signal_bus.subscribe(CoreSignals.SIMULATION_CREATED, capture)
    model_entrypoint.create_simulation("device-1")
    return model_entrypoint, captured_ids[0]


def test_validate_simulation_marker_location_emits_validated_payload(
    tmp_path: Path,
) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)
    captured: list[SimulationLocationValidatedPayload] = []

    def capture(payload: SimulationLocationValidatedPayload) -> None:
        captured.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_LOCATION_VALIDATED, capture
    )
    outcome = model_entrypoint.validate_simulation_marker_location(
        simulation_id,
        1,
        SAMPLE_LINE_CODE,
        SAMPLE_LINE_TRONCON,
        SAMPLE_LATITUDE,
        SAMPLE_LONGITUDE,
    )
    assert isinstance(outcome, ValidateSimulationMarkerLocationOutcome)
    model_entrypoint.apply_result(outcome)

    assert len(captured) == 1
    assert captured[0].simulation_id == simulation_id
    assert captured[0].km == 1
    assert captured[0].line_code == SAMPLE_LINE_CODE
    assert captured[0].line_troncon == SAMPLE_LINE_TRONCON
    assert captured[0].lat == pytest.approx(SAMPLE_LATITUDE)
    assert captured[0].lon == pytest.approx(SAMPLE_LONGITUDE)


def test_validate_simulation_marker_location_missing_simulation_raises(
    tmp_path: Path,
) -> None:
    model_entrypoint, _simulation_id = _make_model(tmp_path)
    captured: list[SimulationLocationValidatedPayload] = []

    def capture(payload: SimulationLocationValidatedPayload) -> None:
        captured.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_LOCATION_VALIDATED,
        capture,
    )

    with pytest.raises(ValueError, match="Simulation with id missing not found"):
        model_entrypoint.validate_simulation_marker_location(
            "missing",
            1,
            SAMPLE_LINE_CODE,
            SAMPLE_LINE_TRONCON,
            SAMPLE_LATITUDE,
            SAMPLE_LONGITUDE,
        )

    assert captured == []


def test_validate_simulation_marker_location_invalid_marker_emits_rejected_payload(
    tmp_path: Path,
) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)
    validated: list[SimulationLocationValidatedPayload] = []
    rejected: list[SimulationLocationRejectedPayload] = []

    def capture_validated(payload: SimulationLocationValidatedPayload) -> None:
        validated.append(payload)

    def capture_rejected(payload: SimulationLocationRejectedPayload) -> None:
        rejected.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_LOCATION_VALIDATED,
        capture_validated,
    )
    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_LOCATION_REJECTED,
        capture_rejected,
    )

    outcome = model_entrypoint.validate_simulation_marker_location(
        simulation_id,
        999,
        SAMPLE_LINE_CODE,
        SAMPLE_LINE_TRONCON,
        0.0,
        0.0,
    )
    model_entrypoint.apply_result(outcome)

    assert validated == []
    assert len(rejected) == 1
    assert rejected[0].simulation_id == simulation_id
    assert rejected[0].km == 999
    assert rejected[0].line_code == SAMPLE_LINE_CODE
    assert rejected[0].line_troncon == SAMPLE_LINE_TRONCON
    assert "Unknown milestone" in rejected[0].reason


def test_set_simulation_spoofed_location_from_validated_payload_updates_without_deserialize(
    tmp_path: Path,
) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)
    outcome = model_entrypoint.validate_simulation_marker_location(
        simulation_id,
        1,
        SAMPLE_LINE_CODE,
        SAMPLE_LINE_TRONCON,
        SAMPLE_LATITUDE,
        SAMPLE_LONGITUDE,
    )
    assert outcome.validated is not None
    payload = outcome.validated

    model_entrypoint.set_simulation_spoofed_location(
        payload.simulation_id,
        payload.lat,
        payload.lon,
        payload,
    )

    simulation = model_entrypoint.get_simulation(simulation_id)
    assert simulation is not None
    assert simulation.spoofed_location.lat == pytest.approx(payload.lat)
    assert simulation.spoofed_location.lon == pytest.approx(payload.lon)
    assert simulation.spoofed_location.poi is not None
    assert simulation.spoofed_location.poi.id == "001000-1-1"
    assert simulation.spoofed_location.poi.is_validated
