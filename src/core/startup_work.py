"""
Paired worker output and main-thread application for core runtime startup.

Worker-side ``run`` and UI-thread ``apply_main_thread`` live here so the full
startup async flow is easy to find and update.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.adb import AdbClient, AdbServer
from core.device_serial_work import enrich_phones_with_serial
from core.devices import Phone
from core.signals import (
    AdbServerStartedPayload,
    CoreSignal,
    DevicesUpdatedPayload,
)

if TYPE_CHECKING:
    from core.models import CoreRuntimeModel


@dataclass
class StartupResult:
    """Result of the async startup job (build on a worker, apply on the main thread)."""

    adb_server: AdbServer | None = field(
        default=None, metadata={"description": "The ADB server instance"}
    )
    adb_client: AdbClient | None = field(
        default=None, metadata={"description": "The ADB client instance"}
    )
    devices: list[Phone] = field(
        default_factory=list, metadata={"description": "The known devices"}
    )


def run(model: CoreRuntimeModel) -> StartupResult:
    """
    Execute startup steps that may block (called from an AsyncRunner worker thread).
    """
    from core.models import CoreRuntimeModel as _CoreRuntimeModel

    if not isinstance(model, _CoreRuntimeModel):
        raise TypeError("run() requires CoreRuntimeModel")
    adb_server = model.start_adb_server()
    adb_client = model.create_adb_client()
    devices = model.get_known_devices(adb_server)
    enrich_phones_with_serial(adb_client, devices)
    return StartupResult(
        adb_server=adb_server,
        adb_client=adb_client,
        devices=devices,
    )


def apply_main_thread(model: CoreRuntimeModel, result: StartupResult) -> None:
    """
    Own server/client state and emit on the bus (call from the Qt main thread;
    AsyncRunner job completion runs there).
    """
    from core.models import CoreRuntimeModel as _CoreRuntimeModel

    if not isinstance(model, _CoreRuntimeModel):
        raise TypeError("apply_main_thread() requires CoreRuntimeModel")
    if result.adb_server is not None:
        model._adb_server = result.adb_server
    if result.adb_client is not None:
        model._adb_client = result.adb_client
    if result.adb_server is not None:
        model._signal_bus.emit(
            CoreSignal.ADB_SERVER_STARTED,
            AdbServerStartedPayload(adb_binary=result.adb_server.binary),
        )
        model._signal_bus.emit(
            CoreSignal.DEVICES_UPDATED,
            DevicesUpdatedPayload(devices=result.devices),
        )
