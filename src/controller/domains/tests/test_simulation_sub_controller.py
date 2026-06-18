"""Tests for SimulationSubController simulation lifecycle and signal wiring."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

from controller.domains.simulation_sub_controller import SimulationSubController
from controller.orchestration.app_controller import AppController
from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import CoreSignal, SimulationCreatedPayload
from core.simulation import Simulation, SimulationRepository


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
    model_entrypoint = ModelEntrypoint()
    model_entrypoint._adb_server = server
    model_entrypoint._adb_client = client
    model_entrypoint._simulations = SimulationRepository(tmp_path / "simulations")
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
        captured.append(payload.simulation.id)

    model_entrypoint.subscribe(CoreSignal.SIMULATION_CREATED, capture)
    model_entrypoint.create_simulation(device_id)
    assert len(captured) == 1
    return captured[0]


def test_connect_model_signals_subscribes_to_simulation_created(tmp_path: Path) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)
    subscribe = MagicMock()
    model_entrypoint.subscribe = subscribe  # type: ignore[method-assign]

    subcontroller.connect_model_signals()

    subscribe.assert_called_once_with(
        CoreSignal.SIMULATION_CREATED,
        subcontroller._on_simulation_created,
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
        SimulationCreatedPayload(simulation=simulation)
    )

    _view_mock(
        subcontroller
    ).forward_device_selection_succeeded.assert_called_once_with(
        simulation_id,
        "device-1",
        simulation.device.name,
    )


def test_on_simulation_created_ignores_payload_without_device(tmp_path: Path) -> None:
    model_entrypoint = _make_model(tmp_path)
    subcontroller = _make_subcontroller(model_entrypoint)
    simulation = Simulation(device=None)

    subcontroller._on_simulation_created(
        SimulationCreatedPayload(simulation=simulation)
    )

    _view_mock(subcontroller).forward_device_selection_succeeded.assert_not_called()


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
