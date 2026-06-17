"""Behavior tests for the in-memory core signal bus."""

from __future__ import annotations

from pathlib import Path

from core.signals import (
    ActivityLogFileUpdatedPayload,
    CoreSignal,
    InMemoryCoreSignalBus,
)


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
