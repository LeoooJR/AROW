"""Entrypoint tests for simulation creation and deletion signal outcomes."""

from __future__ import annotations

from pathlib import Path

import pytest

from application_paths import ApplicationPaths
from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices.phone import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignals,
    SimulationCreatedPayload,
    SimulationCreationFailedPayload,
    SimulationDeletedPayload,
    SimulationDeleteSkippedPayload,
)
from core.tests.signal_test_helpers import seed_adb_startup_for_entrypoint


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


def test_create_simulation_missing_device_emits_creation_failed(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(tmp_path)
    captured: list[SimulationCreationFailedPayload] = []

    def capture_failed(payload: SimulationCreationFailedPayload) -> None:
        captured.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_CREATION_FAILED,
        capture_failed,
    )

    model_entrypoint.create_simulation("missing-device")

    assert len(captured) == 1
    payload = captured[0]
    assert payload.device_id == "missing-device"
    assert payload.device_name == "missing-device"
    assert "not found" in payload.reason
    assert model_entrypoint.get_simulation("missing-device") is None


def test_delete_simulation_for_device_emits_deleted_with_device_id(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(
        tmp_path,
        device=Phone(id="device-1", state="device", model="Pixel"),
    )
    created_ids: list[str] = []

    def capture_created(payload: SimulationCreatedPayload) -> None:
        created_ids.append(payload.simulation_id)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_CREATED, capture_created
    )
    model_entrypoint.create_simulation("device-1")
    assert len(created_ids) == 1

    captured: list[SimulationDeletedPayload] = []

    def capture_deleted(payload: SimulationDeletedPayload) -> None:
        captured.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_DELETED, capture_deleted
    )

    model_entrypoint.delete_simulation_for_device("device-1")

    assert len(captured) == 1
    assert captured[0].simulation_id == created_ids[0]
    assert captured[0].device_id == "device-1"
    assert model_entrypoint.get_simulation(created_ids[0]) is None


def test_delete_simulation_for_device_without_simulation_emits_skipped(
    tmp_path: Path,
) -> None:
    model_entrypoint = _make_model(
        tmp_path,
        device=Phone(id="device-1", state="device", model="Pixel"),
    )
    captured: list[SimulationDeleteSkippedPayload] = []

    def capture_skipped(payload: SimulationDeleteSkippedPayload) -> None:
        captured.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.SIMULATION_DELETE_SKIPPED,
        capture_skipped,
    )

    model_entrypoint.delete_simulation_for_device("device-1")

    assert len(captured) == 1
    assert captured[0].device_id == "device-1"
    assert "not found" in captured[0].reason
