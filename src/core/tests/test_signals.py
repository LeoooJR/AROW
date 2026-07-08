"""Behavior tests for the in-memory core signal bus."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.signals import (
    ActivityLogFileUpdatedPayload,
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    CoreSignalDependencyError,
    InMemoryCoreSignalBus,
    SimulationCreatedPayload,
    SimulationCreationFailedPayload,
    SimulationDeleteSkippedPayload,
    SimulationLocationValidatedPayload,
    SimulationRestoredPayload,
    SimulationStateChangedPayload,
)
from core.tests.signal_test_helpers import seed_adb_startup_signals


def test_signal_bus_ignores_duplicate_subscriptions() -> None:
    bus = InMemoryCoreSignalBus()
    received: list[Path] = []

    def handler(payload: ActivityLogFileUpdatedPayload) -> None:
        received.append(payload.path)

    bus.subscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, handler)
    bus.subscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, handler)

    bus.emit(
        CoreSignal.ACTIVITY_LOG_FILE_UPDATED,
        ActivityLogFileUpdatedPayload(path=Path("/tmp/activity.log")),
    )

    assert received == [Path("/tmp/activity.log")]


def test_signal_bus_unsubscribe_is_safe_and_stops_future_emits() -> None:
    bus = InMemoryCoreSignalBus()
    received: list[Path] = []

    def handler(payload: ActivityLogFileUpdatedPayload) -> None:
        received.append(payload.path)

    bus.unsubscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, handler)
    bus.subscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, handler)
    bus.unsubscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, handler)

    bus.emit(
        CoreSignal.ACTIVITY_LOG_FILE_UPDATED,
        ActivityLogFileUpdatedPayload(path=Path("/tmp/activity.log")),
    )

    assert received == []


def test_signal_bus_emit_uses_handler_snapshot_when_subscriptions_mutate() -> None:
    bus = InMemoryCoreSignalBus()
    events: list[str] = []

    def second_handler(payload: ActivityLogFileUpdatedPayload) -> None:
        events.append(f"second:{payload.path.name}")

    def first_handler(payload: ActivityLogFileUpdatedPayload) -> None:
        events.append(f"first:{payload.path.name}")
        bus.unsubscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, second_handler)

    bus.subscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, first_handler)
    bus.subscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, second_handler)

    bus.emit(
        CoreSignal.ACTIVITY_LOG_FILE_UPDATED,
        ActivityLogFileUpdatedPayload(path=Path("/tmp/first.log")),
    )
    bus.emit(
        CoreSignal.ACTIVITY_LOG_FILE_UPDATED,
        ActivityLogFileUpdatedPayload(path=Path("/tmp/second.log")),
    )

    assert events == ["first:first.log", "second:first.log", "first:second.log"]


def test_signal_bus_continues_dispatch_when_handler_raises() -> None:
    bus = InMemoryCoreSignalBus()
    received: list[Path] = []

    def failing_handler(payload: ActivityLogFileUpdatedPayload) -> None:
        raise RuntimeError(f"boom:{payload.path.name}")

    def succeeding_handler(payload: ActivityLogFileUpdatedPayload) -> None:
        received.append(payload.path)

    bus.subscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, failing_handler)
    bus.subscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, succeeding_handler)

    bus.emit(
        CoreSignal.ACTIVITY_LOG_FILE_UPDATED,
        ActivityLogFileUpdatedPayload(path=Path("/tmp/activity.log")),
    )

    assert received == [Path("/tmp/activity.log")]


def test_signal_bus_records_history_without_subscribers() -> None:
    bus = InMemoryCoreSignalBus()

    bus.emit(
        CoreSignal.ACTIVITY_LOG_FILE_UPDATED,
        ActivityLogFileUpdatedPayload(path=Path("/tmp/activity.log")),
    )

    assert len(bus.history) == 1
    assert bus.history[0].signal == CoreSignal.ACTIVITY_LOG_FILE_UPDATED
    assert bus.has_emitted(CoreSignal.ACTIVITY_LOG_FILE_UPDATED)


def test_signal_bus_rejects_adb_stop_before_matching_start() -> None:
    bus = InMemoryCoreSignalBus()

    with pytest.raises(CoreSignalDependencyError, match="adb.server.started"):
        bus.emit(
            CoreSignal.ADB_SERVER_STOPPED,
            AdbServerStoppedPayload(adb_binary_path="/adb/adb"),
        )


def test_signal_bus_allows_adb_stop_after_matching_start() -> None:
    bus = InMemoryCoreSignalBus()
    bus.emit(
        CoreSignal.ADB_SERVER_STARTED,
        AdbServerStartedPayload(adb_binary_path="/adb/adb"),
    )

    bus.emit(
        CoreSignal.ADB_SERVER_STOPPED,
        AdbServerStoppedPayload(adb_binary_path="/adb/adb"),
    )

    assert bus.has_emitted(CoreSignal.ADB_SERVER_STOPPED, scope="/adb/adb")


def test_signal_bus_rejects_simulation_state_change_before_create_or_restore() -> None:
    bus = InMemoryCoreSignalBus()
    seed_adb_startup_signals(bus)

    with pytest.raises(CoreSignalDependencyError, match="simulation.created"):
        bus.emit(
            CoreSignal.SIMULATION_STATE_CHANGED,
            SimulationStateChangedPayload(simulation_id="sim-1", active=True),
        )


def test_signal_bus_allows_simulation_dependent_signals_after_create() -> None:
    bus = InMemoryCoreSignalBus()
    seed_adb_startup_signals(bus)
    bus.emit(
        CoreSignal.SIMULATION_CREATED,
        SimulationCreatedPayload(
            simulation_id="sim-1",
            device_id="device-1",
            device_name="Phone",
        ),
    )

    bus.emit(
        CoreSignal.SIMULATION_STATE_CHANGED,
        SimulationStateChangedPayload(simulation_id="sim-1", active=True),
    )
    bus.emit(
        CoreSignal.SIMULATION_LOCATION_VALIDATED,
        SimulationLocationValidatedPayload(
            simulation_id="sim-1",
            lat=1.0,
            lon=2.0,
            poi={"km": 1, "line": {"code": "001000", "troncon": 1}},
        ),
    )

    assert bus.has_emitted(CoreSignal.SIMULATION_LOCATION_VALIDATED, scope="sim-1")


def test_signal_bus_allows_simulation_dependent_signals_after_restore() -> None:
    bus = InMemoryCoreSignalBus()
    seed_adb_startup_signals(bus)
    bus.emit(
        CoreSignal.SIMULATION_RESTORED,
        SimulationRestoredPayload(
            simulation_id="sim-2",
            device_id="device-2",
            device_name="Phone",
        ),
    )

    bus.emit(
        CoreSignal.SIMULATION_STATE_CHANGED,
        SimulationStateChangedPayload(simulation_id="sim-2", active=False),
    )

    assert bus.has_emitted(CoreSignal.SIMULATION_STATE_CHANGED, scope="sim-2")


def test_signal_bus_accepts_simulation_outcome_payloads_without_dependencies() -> None:
    bus = InMemoryCoreSignalBus()

    bus.emit(
        CoreSignal.SIMULATION_CREATION_FAILED,
        SimulationCreationFailedPayload(
            device_id="device-1",
            device_name="Pixel",
            reason="Device with id device-1 not found",
        ),
    )
    bus.emit(
        CoreSignal.SIMULATION_DELETE_SKIPPED,
        SimulationDeleteSkippedPayload(
            device_id="device-1",
            reason="Simulation for device with id device-1 not found",
        ),
    )

    assert bus.has_emitted(CoreSignal.SIMULATION_CREATION_FAILED)
    assert bus.has_emitted(CoreSignal.SIMULATION_DELETE_SKIPPED)


def test_signal_bus_rejects_scoped_dependency_from_different_simulation_id() -> None:
    bus = InMemoryCoreSignalBus()
    seed_adb_startup_signals(bus)
    bus.emit(
        CoreSignal.SIMULATION_CREATED,
        SimulationCreatedPayload(
            simulation_id="sim-1",
            device_id="device-1",
            device_name="Phone",
        ),
    )

    with pytest.raises(CoreSignalDependencyError, match="sim-2"):
        bus.emit(
            CoreSignal.SIMULATION_STATE_CHANGED,
            SimulationStateChangedPayload(simulation_id="sim-2", active=True),
        )
