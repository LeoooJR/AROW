"""Protocols for core work appliers; keep work modules decoupled from ModelEntrypoint."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from core.adb.client import AdbClient
    from core.adb.server import AdbServer
    from core.devices import Phone
    from core.signals import CoreSignal
    from core.simulation import Simulation

PayloadT = TypeVar("PayloadT")


class CoreSignalEmitter(Protocol):
    """Minimal entrypoint surface for main-thread core-bus emission."""

    def emit_core_signal(
        self,
        signal: CoreSignal[PayloadT],
        payload: PayloadT,
    ) -> None:
        """Publish one typed payload on the core signal bus."""


class SimulationLookupEntrypoint(CoreSignalEmitter, Protocol):
    """Entrypoint surface for work that reads simulations after async completion."""

    def get_simulation(self, simulation_id: str) -> Simulation | None:
        """Return the tracked simulation for an id, if it still exists."""


class DeviceReconcileResultProtocol(Protocol):
    """Structural type for paired-device reconciliation outcomes."""

    @property
    def changed(self) -> bool:
        """True when paired devices were added, removed, or rebound."""

    @property
    def device_id_rebindings(self) -> Mapping[str, str]:
        """Old device id to new id when ADB serials were rebound."""


class AdbRuntimeEntrypoint(CoreSignalEmitter, Protocol):
    """Entrypoint surface for work that mutates ADB server/client handles."""

    adb_server: AdbServer | None
    adb_client: AdbClient | None


class StartupRuntimeEntrypoint(AdbRuntimeEntrypoint, Protocol):
    """Entrypoint surface for startup restoration and device activation."""

    def restore_persisted_simulation(self, simulation: Simulation) -> None:
        """Register a simulation deserialized from disk."""

    def sync_last_active_device_id(self, device_id: str | None) -> None:
        """Persist the last active handset id from startup metadata."""

    def create_simulation(self, device_id: str) -> None:
        """Create or reuse the simulation bound to a paired device."""


class DeviceRegistrationEntrypoint(CoreSignalEmitter, Protocol):
    """Entrypoint surface for successful device pairing."""

    def register_paired_device(self, phone: Phone) -> None:
        """Add or update a paired handset in the model."""


class DeviceReconcileEntrypoint(CoreSignalEmitter, Protocol):
    """Entrypoint surface for refreshing known devices against paired state."""

    adb_server: AdbServer | None

    def reconcile_paired_devices(
        self, phones: list[Phone]
    ) -> DeviceReconcileResultProtocol:
        """Merge a fresh ADB discovery list into paired devices."""


class HostIdentityEntrypoint(CoreSignalEmitter, Protocol):
    """Entrypoint surface for persisted host install identity."""

    def set_host_identity(self, stable_key: str) -> None:
        """Apply the stable host key derived from install identity."""
