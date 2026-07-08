"""Shared helpers for seeding core signal dependency history in tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.signals import (
    AdbServerStartedPayload,
    CoreSignal,
    DevicesUpdatedPayload,
    InMemoryCoreSignalBus,
)

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint


def seed_adb_startup_signals(
    bus: InMemoryCoreSignalBus,
    *,
    adb_binary_path: str = "/adb/adb",
) -> None:
    """Record the minimum ADB startup emissions required before device/simulation signals."""
    bus.emit(
        CoreSignal.ADB_SERVER_STARTED,
        AdbServerStartedPayload(adb_binary_path=adb_binary_path),
    )
    bus.emit(
        CoreSignal.DEVICES_UPDATED,
        DevicesUpdatedPayload(devices=[]),
    )


def seed_adb_startup_for_entrypoint(
    model_entrypoint: ModelEntrypoint,
    *,
    adb_binary_path: str = "/adb/adb",
) -> None:
    """Seed dependency history on a model entrypoint bus for isolated core tests."""
    seed_adb_startup_signals(
        model_entrypoint._signal_bus,
        adb_binary_path=adb_binary_path,
    )
