"""Tests for SimulationSubController simulation lifecycle and signal wiring."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from application_paths import ApplicationPaths
from controller.domains.simulation_sub_controller import SimulationSubController
from controller.orchestration.app_controller import AppController
from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices.phone import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignals,
    SimulationCreatedPayload,
    SimulationCreationFailedPayload,
    SimulationDeletedPayload,
)
from core.tests.signal_test_helpers import seed_adb_startup_for_entrypoint


class _AppProbe:
    def __init__(self, model_entrypoint: ModelEntrypoint) -> None:
        self.model_entrypoint = model_entrypoint
        self.view = MagicMock()


def _make_model(tmp_path: Path, *, device: Phone | None = None) -> ModelEntrypoint:
    state = MockAdbState(seed=404, initial_devices=0)
    server = MockAdbServer(state=state)
    client = MockAdbClient(state=state)
    model_entrypoint = ModelEntrypoint(
        paths=ApplicationPaths(tmp_path, tmp_path / "config", tmp_path / "src", "linux")
    )
    model_entrypoint._adb_server = server
    model_entrypoint._adb_client = client
    seed_adb_startup_for_entrypoint(model_entrypoint)
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

    model_entrypoint.signal_bus.subscribe(CoreSignals.SIMULATION_CREATED, capture)
    seed_adb_startup_for_entrypoint(model_entrypoint)
    model_entrypoint.create_simulation(device_id)
    assert len(captured) == 1
    return captured[0]


def test_connect_model_signals_subscribes_to_simulation_events(tmp_path: Path) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)
    subscribe = MagicMock()
    model_entrypoint.signal_bus.subscribe = subscribe  # type: ignore[method-assign]

    subcontroller.connect_model_signals()

    assert subscribe.call_count == 5
    subscribe.assert_any_call(
        CoreSignals.SIMULATION_CREATED,
        subcontroller._on_simulation_created,
    )
    subscribe.assert_any_call(
        CoreSignals.SIMULATION_RESTORED,
        subcontroller._on_simulation_restored,
    )
    subscribe.assert_any_call(
        CoreSignals.SIMULATION_CREATION_FAILED,
        subcontroller._on_simulation_creation_failed,
    )
    subscribe.assert_any_call(
        CoreSignals.SIMULATION_DELETED,
        subcontroller._on_simulation_deleted,
    )
    subscribe.assert_any_call(
        CoreSignals.SIMULATION_DELETE_SKIPPED,
        subcontroller._on_simulation_delete_skipped,
    )


def test_device_selection_confirmed_creates_simulation_and_waits_for_signal(
    tmp_path: Path, log_records
) -> None:
    model_entrypoint = _make_model(
        tmp_path, device=Phone(id="device-1", state="device", model="Pixel")
    )
    subcontroller = _make_subcontroller(model_entrypoint)
    captured: list[str] = []

    def capture(payload: SimulationCreatedPayload) -> None:
        captured.append(payload.simulation_id)

    model_entrypoint.signal_bus.subscribe(CoreSignals.SIMULATION_CREATED, capture)

    subcontroller._on_device_selection_confirmed("device-1", "Pixel")

    assert len(captured) == 1
    simulation = model_entrypoint.get_simulation(captured[0])
    assert simulation is not None
    assert simulation.device is not None
    assert simulation.device.id == "device-1"
    view = _view_mock(subcontroller)
    view.forward_device_selection_succeeded.assert_not_called()
    view.forward_device_selection_failed.assert_not_called()
    created_records = [
        record for record in log_records if record["message"] == "Simulation created"
    ]
    assert len(created_records) == 1
    assert created_records[0]["level"].name == "INFO"
    assert created_records[0]["extra"]["device_id"] == "device-1"


def test_device_selection_confirmed_forwards_failure_when_device_is_unknown(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)
    subcontroller.connect_model_signals()
    created_ids: list[str] = []

    def capture(payload: SimulationCreatedPayload) -> None:
        created_ids.append(payload.simulation_id)

    model_entrypoint.signal_bus.subscribe(CoreSignals.SIMULATION_CREATED, capture)

    subcontroller._on_device_selection_confirmed("missing-device", "Ghost")

    assert created_ids == []
    view = _view_mock(subcontroller)
    view.forward_device_selection_failed.assert_called_once_with(
        "missing-device", "missing-device"
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
    subcontroller.connect_model_signals()

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


def test_on_simulation_creation_failed_forwards_device_selection_failure(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)
    payload = SimulationCreationFailedPayload(
        device_id="device-1",
        device_name="Pixel",
        reason="Device with id device-1 not found",
    )

    subcontroller._on_simulation_creation_failed(payload)

    _view_mock(subcontroller).forward_device_selection_failed.assert_called_once_with(
        "device-1",
        "Pixel",
    )


def test_on_simulation_deleted_forwards_remove_active_device_success(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)
    payload = SimulationDeletedPayload(
        simulation_id="sim-1",
        device_id="device-1",
    )

    subcontroller._on_simulation_deleted(payload)

    _view_mock(
        subcontroller
    ).forward_remove_active_device_succeeded.assert_called_once_with("device-1")


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


def test_persist_simulation_repository_delegates_to_model_entrypoint(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)
    model_entrypoint.persist_simulations = MagicMock()  # type: ignore[method-assign]

    subcontroller.persist_simulation_repository()

    model_entrypoint.persist_simulations.assert_called_once_with()
