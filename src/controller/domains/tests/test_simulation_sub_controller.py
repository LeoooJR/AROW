"""Tests for SimulationSubController simulation lifecycle and signal wiring."""

from __future__ import annotations

import builtins
import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from controller.domains.simulation_sub_controller import SimulationSubController
from controller.orchestration.app_controller import AppController
from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices import Phone
from core.entrypoint import ModelEntrypoint
from core.geo.element import clear_referentiel_pk_cache
from core.signals import (
    CoreSignal,
    SimulationCreatedPayload,
    SimulationLocationValidatedPayload,
    SimulationPositionChangedPayload,
    SimulationStateChangedPayload,
)


@pytest.fixture(autouse=True)
def _clear_referentiel_cache() -> Iterator[None]:
    clear_referentiel_pk_cache()
    yield
    clear_referentiel_pk_cache()


class _AppProbe:
    def __init__(self, model_entrypoint: ModelEntrypoint) -> None:
        self.model_entrypoint = model_entrypoint
        self.view = MagicMock()


def _patch_controller_type_checks(monkeypatch, probe: object) -> None:
    real_isinstance = builtins.isinstance

    def _isinstance(obj, cls) -> bool:
        cls_name = getattr(cls, "__name__", "")
        if cls_name == "MainWindow" and obj is getattr(probe, "view", object()):
            return True
        if cls_name == "ModelEntrypoint" and obj is getattr(
            probe, "model_entrypoint", object()
        ):
            return True
        return real_isinstance(obj, cls)

    monkeypatch.setattr(builtins, "isinstance", _isinstance)


def _make_model(tmp_path: Path, *, device: Phone | None = None) -> ModelEntrypoint:
    state = MockAdbState(seed=404, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    with patch(
        "core.entrypoint.get_or_create_application_dir",
        return_value=tmp_path,
    ):
        model_entrypoint = ModelEntrypoint()
    model_entrypoint._adb_server = server
    model_entrypoint._adb_client = client
    if device is not None:
        server.paired_devices.add(device)
    return model_entrypoint


def _make_subcontroller(model_entrypoint: ModelEntrypoint) -> SimulationSubController:
    app = _AppProbe(model_entrypoint)
    return SimulationSubController(cast(AppController, app))


def _view_mock(subcontroller: SimulationSubController) -> MagicMock:
    return cast(MagicMock, cast(_AppProbe, subcontroller._app).view)


def _create_simulation_id(model_entrypoint: ModelEntrypoint, device_id: str) -> str:
    """Create a simulation and return its id via SIMULATION_CREATED."""
    captured: list[str] = []

    def capture(payload: SimulationCreatedPayload) -> None:
        captured.append(payload.simulation_id)

    model_entrypoint.subscribe(CoreSignal.SIMULATION_CREATED, capture)
    model_entrypoint.create_simulation(device_id)
    assert len(captured) == 1
    return captured[0]


def test_connect_model_signals_subscribes_to_simulation_events(tmp_path: Path) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)
    subscribe = MagicMock()
    model_entrypoint.subscribe = subscribe  # type: ignore[method-assign]

    subcontroller.connect_model_signals()

    assert subscribe.call_count == 6
    subscribe.assert_any_call(
        CoreSignal.SIMULATION_CREATED,
        subcontroller._on_simulation_created,
    )
    subscribe.assert_any_call(
        CoreSignal.MAP_RENDERED,
        subcontroller._on_map_rendered,
    )
    subscribe.assert_any_call(
        CoreSignal.SIMULATION_STATE_CHANGED,
        subcontroller._on_simulation_state_changed,
    )
    subscribe.assert_any_call(
        CoreSignal.SIMULATION_POSITION_CHANGED,
        subcontroller._on_simulation_position_changed,
    )
    subscribe.assert_any_call(
        CoreSignal.SIMULATION_MAP_FILE_CHANGED,
        subcontroller._on_simulation_map_file_changed,
    )
    subscribe.assert_any_call(
        CoreSignal.SIMULATION_LOCATION_VALIDATED,
        subcontroller._on_simulation_location_validated,
    )


def test_device_selection_confirmed_creates_simulation_and_waits_for_signal(
    monkeypatch, tmp_path: Path
) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    subcontroller = _make_subcontroller(model_entrypoint)
    _patch_controller_type_checks(monkeypatch, subcontroller._app)

    subcontroller._on_device_selection_confirmed("device-1", "Pixel")

    simulations = list(model_entrypoint._simulations)
    assert len(simulations) == 1
    assert simulations[0].device is not None
    assert simulations[0].device.id == "device-1"
    view = _view_mock(subcontroller)
    view.forward_device_selection_succeeded.assert_not_called()
    view.forward_device_selection_failed.assert_not_called()


def test_device_selection_confirmed_forwards_failure_when_device_is_unknown(
    monkeypatch, tmp_path: Path
) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)
    _patch_controller_type_checks(monkeypatch, subcontroller._app)

    subcontroller._on_device_selection_confirmed("missing-device", "Ghost")

    assert list(model_entrypoint._simulations) == []
    view = _view_mock(subcontroller)
    view.forward_device_selection_failed.assert_called_once_with(
        "missing-device", "Ghost"
    )
    view.forward_device_selection_succeeded.assert_not_called()


def test_on_simulation_created_forwards_success_with_simulation_id(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    subcontroller = _make_subcontroller(model_entrypoint)
    simulation_id = _create_simulation_id(model_entrypoint, "device-1")
    simulation = model_entrypoint.get_simulation(simulation_id)
    assert simulation is not None
    assert simulation.device is not None

    subcontroller._on_simulation_created(
        SimulationCreatedPayload(
            simulation_id=simulation_id,
            device_id="device-1",
            device_name=simulation.device.name,
        )
    )


def test_on_simulation_created_ignores_payload_without_device(tmp_path: Path) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)

    subcontroller._on_simulation_created(
        SimulationCreatedPayload(
            simulation_id="sim-1",
            device_id="",
            device_name="",
        )
    )


def test_remove_device_requested_deletes_simulation_and_forwards_success(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    simulation_id = _create_simulation_id(model_entrypoint, "device-1")
    subcontroller = _make_subcontroller(model_entrypoint)

    subcontroller._on_remove_device_requested("device-1")

    assert model_entrypoint.get_simulation(simulation_id) is None
    _view_mock(
        subcontroller
    ).forward_remove_active_device_succeeded.assert_called_once_with("device-1")


def test_remove_device_requested_ignores_devices_without_active_simulation(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    subcontroller = _make_subcontroller(model_entrypoint)

    subcontroller._on_remove_device_requested("device-1")

    _view_mock(subcontroller).forward_remove_active_device_succeeded.assert_not_called()


def test_run_stop_pause_and_resume_update_simulation_active_state(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    simulation_id = _create_simulation_id(model_entrypoint, "device-1")
    subcontroller = _make_subcontroller(model_entrypoint)

    subcontroller.run(simulation_id)
    assert model_entrypoint.is_simulation_active(simulation_id) is True

    subcontroller.run(simulation_id)
    assert model_entrypoint.is_simulation_active(simulation_id) is True

    subcontroller.pause(simulation_id)
    assert model_entrypoint.is_simulation_active(simulation_id) is False

    subcontroller.resume(simulation_id)
    assert model_entrypoint.is_simulation_active(simulation_id) is True

    subcontroller.stop(simulation_id)
    assert model_entrypoint.is_simulation_active(simulation_id) is False


def test_run_persists_active_state_to_metadata(tmp_path: Path) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    subcontroller = _make_subcontroller(model_entrypoint)
    subcontroller.connect_model_signals()
    simulation_id = _create_simulation_id(model_entrypoint, "device-1")

    subcontroller.run(simulation_id)

    metadata_path = model_entrypoint._simulations.simulation_metadata_file(
        simulation_id
    )
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["active"] is True


def test_update_simulation_location_persists_metadata(tmp_path: Path) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    subcontroller = _make_subcontroller(model_entrypoint)
    subcontroller.connect_model_signals()
    simulation_id = _create_simulation_id(model_entrypoint, "device-1")
    new_spoofed_location = (48.85, 2.35, None)

    model_entrypoint.update_simulation(
        simulation_id,
        spoofed_location=new_spoofed_location,
    )

    metadata_path = model_entrypoint._simulations.simulation_metadata_file(
        simulation_id
    )
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["spoofed_location"] == {
        "lat": new_spoofed_location[0],
        "lon": new_spoofed_location[1],
        "poi": None,
    }


def test_set_simulation_active_emits_state_changed_with_simulation_id(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    simulation_id = _create_simulation_id(model_entrypoint, "device-1")
    captured: list[SimulationStateChangedPayload] = []

    def capture_state(payload: SimulationStateChangedPayload) -> None:
        captured.append(payload)

    model_entrypoint.subscribe(
        CoreSignal.SIMULATION_STATE_CHANGED,
        capture_state,
    )

    model_entrypoint.set_simulation_active(simulation_id, True)

    assert len(captured) == 1
    assert captured[0].simulation_id == simulation_id
    assert captured[0].active is True


def test_update_simulation_location_emits_position_changed_with_simulation_id(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    simulation_id = _create_simulation_id(model_entrypoint, "device-1")
    new_spoofed_location = (1.0, 2.0, None)
    captured: list[SimulationPositionChangedPayload] = []

    def capture_position(payload: SimulationPositionChangedPayload) -> None:
        captured.append(payload)

    model_entrypoint.subscribe(
        CoreSignal.SIMULATION_POSITION_CHANGED,
        capture_position,
    )

    model_entrypoint.update_simulation(
        simulation_id, real_location=new_spoofed_location
    )

    assert len(captured) == 1
    assert captured[0].simulation_id == simulation_id
    assert captured[0].lat == new_spoofed_location[0]
    assert captured[0].lon == new_spoofed_location[1]
    assert captured[0].poi is None


def test_simulation_location_validated_updates_spoofed_location_and_persists(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    subcontroller = _make_subcontroller(model_entrypoint)
    simulation_id = _create_simulation_id(model_entrypoint, "device-1")
    captured: list[SimulationLocationValidatedPayload] = []

    def capture(payload: SimulationLocationValidatedPayload) -> None:
        captured.append(payload)

    model_entrypoint.subscribe(CoreSignal.SIMULATION_LOCATION_VALIDATED, capture)
    model_entrypoint.validate_simulation_marker_location(
        simulation_id,
        1,
        "001000-1",
        48.88533318609319,
        2.363530409238113,
    )
    assert len(captured) == 1
    payload = captured[0]

    subcontroller.connect_model_signals()
    subcontroller._on_simulation_location_validated(payload)

    simulation = model_entrypoint.get_simulation(simulation_id)
    assert simulation is not None
    assert simulation.spoofed_location.lat == pytest.approx(payload.lat)
    assert simulation.spoofed_location.lon == pytest.approx(payload.lon)
    assert simulation.spoofed_location.poi is not None
    assert simulation.spoofed_location.poi.id == "001000-1-1"
    assert simulation.spoofed_location.poi.is_validated
    metadata_path = model_entrypoint._simulations.simulation_metadata_file(
        simulation_id
    )
    persisted = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert persisted["spoofed_location"]["lat"] == pytest.approx(payload.lat)
    assert persisted["spoofed_location"]["lon"] == pytest.approx(payload.lon)
    assert persisted["spoofed_location"]["poi"]["km"] == 1
    assert persisted["spoofed_location"]["poi"]["line"]["code"] == "001000"
