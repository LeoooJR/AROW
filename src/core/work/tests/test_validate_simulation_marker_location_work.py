"""Tests for validate simulation marker location core runtime work."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from application_paths import ApplicationPaths
from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices.phone import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignals,
    ErrorRaisedPayload,
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
    ValidateSimulationMarkerLocationWork,
)

pytestmark = pytest.mark.usefixtures("clear_lignes_cache")


def _make_model(tmp_path: Path) -> tuple[ModelEntrypoint, str]:
    state = MockAdbState(seed=601, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    device = Phone(id="device-1", state="device", model="Pixel")
    server.paired_devices.add(device)
    model_entrypoint = ModelEntrypoint(
        paths=ApplicationPaths(tmp_path, tmp_path / "config", tmp_path / "src", "linux")
    )
    model_entrypoint.adb_server = server
    model_entrypoint.adb_client = client
    seed_adb_startup_for_entrypoint(model_entrypoint)
    captured_ids: list[str] = []

    def capture(payload: SimulationCreatedPayload) -> None:
        captured_ids.append(payload.simulation_id)

    model_entrypoint.signal_bus.subscribe(CoreSignals.SIMULATION_CREATED, capture)
    model_entrypoint.create_simulation("device-1")
    return model_entrypoint, captured_ids[0]


def test_validate_simulation_marker_location_work_run_returns_validated_outcome(
    tmp_path: Path,
) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)

    outcome = ValidateSimulationMarkerLocationWork(
        simulation_id=simulation_id,
        km=1,
        line_code=SAMPLE_LINE_CODE,
        line_troncon=SAMPLE_LINE_TRONCON,
        latitude=SAMPLE_LATITUDE,
        longitude=SAMPLE_LONGITUDE,
    ).run()

    assert outcome.validated is not None
    assert outcome.rejected is None
    assert outcome.validated.simulation_id == simulation_id
    assert outcome.validated.km == 1
    assert outcome.validated.line_code == SAMPLE_LINE_CODE
    assert outcome.validated.line_troncon == SAMPLE_LINE_TRONCON


def test_validate_simulation_marker_location_work_run_rejects_unknown_line(
    tmp_path: Path,
) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)

    outcome = ValidateSimulationMarkerLocationWork(
        simulation_id=simulation_id,
        km=1,
        line_code="999999",
        line_troncon=1,
        latitude=SAMPLE_LATITUDE,
        longitude=SAMPLE_LONGITUDE,
    ).run()

    assert outcome.validated is None
    assert outcome.rejected is not None
    assert outcome.rejected.simulation_id == simulation_id
    assert outcome.rejected.line_code == "999999"
    assert outcome.rejected.line_troncon == 1


def test_validate_simulation_marker_location_work_run_returns_rejected_outcome(
    tmp_path: Path,
) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)

    outcome = ValidateSimulationMarkerLocationWork(
        simulation_id=simulation_id,
        km=999,
        line_code=SAMPLE_LINE_CODE,
        line_troncon=SAMPLE_LINE_TRONCON,
        latitude=0.0,
        longitude=0.0,
    ).run()

    assert outcome.validated is None
    assert outcome.rejected is not None
    assert outcome.rejected.simulation_id == simulation_id
    assert "Unknown milestone" in outcome.rejected.reason


def test_apply_main_thread_emits_validated_signal(tmp_path: Path, log_records) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)
    captured: list[SimulationLocationValidatedPayload] = []

    def capture(payload: SimulationLocationValidatedPayload) -> None:
        simulation = model_entrypoint.get_simulation(simulation_id)
        assert simulation is not None
        assert simulation.spoofed_location.poi is not None
        metadata_path = tmp_path / "simulations" / simulation_id / "simulation.json"
        persisted = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert persisted["spoofed_location"]["poi"]["km"] == 1
        captured.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_LOCATION_VALIDATED, capture
    )
    outcome = ValidateSimulationMarkerLocationWork(
        simulation_id=simulation_id,
        km=1,
        line_code=SAMPLE_LINE_CODE,
        line_troncon=SAMPLE_LINE_TRONCON,
        latitude=SAMPLE_LATITUDE,
        longitude=SAMPLE_LONGITUDE,
    ).run()
    ValidateSimulationMarkerLocationWork.apply_main_thread(model_entrypoint, outcome)

    assert len(captured) == 1
    assert captured[0].simulation_id == simulation_id
    record = log_records[-1]
    assert record["level"].name == "INFO"
    assert record["message"] == "Simulation location validated"


def test_apply_main_thread_emits_rejected_signal(tmp_path: Path, log_records) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)
    captured: list[SimulationLocationRejectedPayload] = []

    def capture(payload: SimulationLocationRejectedPayload) -> None:
        captured.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_LOCATION_REJECTED, capture
    )
    outcome = ValidateSimulationMarkerLocationWork(
        simulation_id=simulation_id,
        km=999,
        line_code=SAMPLE_LINE_CODE,
        line_troncon=SAMPLE_LINE_TRONCON,
        latitude=0.0,
        longitude=0.0,
    ).run()
    ValidateSimulationMarkerLocationWork.apply_main_thread(model_entrypoint, outcome)

    assert len(captured) == 1
    assert captured[0].km == 999
    record = log_records[-1]
    assert record["level"].name == "WARNING"
    assert record["message"] == "Simulation location rejected"


@pytest.mark.parametrize(
    ("matches_stored_marker", "expected_poi"),
    [(True, None), (False, "001000-1-1")],
)
def test_rejected_outcome_clears_only_exact_stored_marker(
    tmp_path: Path,
    matches_stored_marker: bool,
    expected_poi: str | None,
) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)
    validated_outcome = ValidateSimulationMarkerLocationWork(
        simulation_id=simulation_id,
        km=1,
        line_code=SAMPLE_LINE_CODE,
        line_troncon=SAMPLE_LINE_TRONCON,
        latitude=SAMPLE_LATITUDE,
        longitude=SAMPLE_LONGITUDE,
    ).run()
    assert validated_outcome.validated is not None
    ValidateSimulationMarkerLocationWork.apply_main_thread(
        model_entrypoint, validated_outcome
    )
    validated = validated_outcome.validated
    rejected = SimulationLocationRejectedPayload(
        simulation_id=simulation_id,
        km=validated.km if matches_stored_marker else validated.km + 1,
        line_code=validated.line_code,
        line_troncon=validated.line_troncon,
        lat=validated.lat,
        lon=validated.lon,
        reason="Dataset revalidation rejected the marker",
    )

    ValidateSimulationMarkerLocationWork.apply_main_thread(
        model_entrypoint,
        ValidateSimulationMarkerLocationOutcome(rejected=rejected),
    )

    simulation = model_entrypoint.get_simulation(simulation_id)
    assert simulation is not None
    actual_poi = simulation.spoofed_location.poi
    assert (actual_poi.id if actual_poi is not None else None) == expected_poi
    metadata_path = tmp_path / "simulations" / simulation_id / "simulation.json"
    persisted = json.loads(metadata_path.read_text(encoding="utf-8"))
    persisted_poi = persisted["spoofed_location"]["poi"]
    if matches_stored_marker:
        assert persisted_poi is None
    else:
        assert persisted_poi["km"] == 1


@pytest.mark.parametrize("validated", [True, False])
def test_apply_main_thread_discards_stale_outcome(
    tmp_path: Path, validated: bool
) -> None:
    model_entrypoint, simulation_id = _make_model(tmp_path)
    simulation = model_entrypoint.get_simulation(simulation_id)
    assert simulation is not None
    model_entrypoint.delete_simulation(simulation)
    emitted: list[object] = []

    def capture_validated(payload: SimulationLocationValidatedPayload) -> None:
        emitted.append(payload)

    def capture_rejected(payload: SimulationLocationRejectedPayload) -> None:
        emitted.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_LOCATION_VALIDATED, capture_validated
    )
    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_LOCATION_REJECTED, capture_rejected
    )
    work = ValidateSimulationMarkerLocationWork(
        simulation_id=simulation_id,
        km=1 if validated else 999,
        line_code=SAMPLE_LINE_CODE,
        line_troncon=SAMPLE_LINE_TRONCON,
        latitude=SAMPLE_LATITUDE if validated else 0.0,
        longitude=SAMPLE_LONGITUDE if validated else 0.0,
    )

    ValidateSimulationMarkerLocationWork.apply_main_thread(model_entrypoint, work.run())

    assert emitted == []


def test_apply_failure_main_thread_emits_generic_error(tmp_path: Path) -> None:
    model_entrypoint, _simulation_id = _make_model(tmp_path)
    captured: list[ErrorRaisedPayload] = []

    def capture(payload: ErrorRaisedPayload) -> None:
        captured.append(payload)

    model_entrypoint.signal_bus.subscribe(CoreSignals.ERROR_RAISED, capture)
    ValidateSimulationMarkerLocationWork.apply_failure_main_thread(
        model_entrypoint,
        RuntimeError("unexpected"),
    )

    assert len(captured) == 1
    assert captured[0].source == "ValidateSimulationMarkerLocationWork"


def test_outcome_requires_exactly_one_payload() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ValidateSimulationMarkerLocationOutcome()

    with pytest.raises(ValueError, match="exactly one"):
        ValidateSimulationMarkerLocationOutcome(
            validated=SimulationLocationValidatedPayload(
                simulation_id="sim-1",
                lat=0.0,
                lon=0.0,
                km=1,
                line_id="line-id",
                line_code=SAMPLE_LINE_CODE,
                line_troncon=SAMPLE_LINE_TRONCON,
                line_type="type",
                line_label="label",
                label="001+000",
                milestone_type="Kilometer",
                line_geometry_wkb_b64="",
            ),
            rejected=SimulationLocationRejectedPayload(
                simulation_id="sim-1",
                km=1,
                line_code=SAMPLE_LINE_CODE,
                line_troncon=SAMPLE_LINE_TRONCON,
                lat=0.0,
                lon=0.0,
                reason="bad",
            ),
        )
