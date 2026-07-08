"""
Core domain signal bus: identifiers, typed payloads, and in-memory dispatch.

When adding a new core signal:
1. Add a ``CoreSignal`` enum member.
2. Add the payload dataclass.
3. Register the pair in ``CORE_SIGNAL_PAYLOAD_TYPES``.
4. Add matching ``@overload`` entries for ``subscribe``, ``unsubscribe``, and ``emit``
   on ``CoreSignalBus`` / ``InMemoryCoreSignalBus`` and ``Entrypoint``.

Payload design rules (controllers must not depend on live core domain objects):
- Prefer the smallest set of primitive fields (``str``, ``int``, ``float``, ``bool``).
- ``pathlib.Path`` is allowed for filesystem resources; it is not a custom core domain type.
- When a custom core object must be represented, serialize it (for example via
  ``serialize()``) into a ``dict`` and carry only that dict in the payload.
- Do not place live core domain instances (``Phone``, ``Simulation``, ``Location``,
  ``AdbBinary``, ``Exception``, etc.) on core signal payloads.
- When a signal payload changes, update every emitter, subscriber, controller bridge,
  GUI consumer, and test on the full pathway for that signal.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar, overload

from logger import logger


class CoreSignal(StrEnum):
    """
    Canonical event identifiers emitted by the core domain layer.

    Why this shape:
    - StrEnum keeps string interoperability while preventing magic literals.
    - A flat namespace is cheap to compare/hash and easy to route in a bus.
    - Names are domain-oriented (not UI-oriented) so controllers can adapt them.
    """

    ADB_SERVER_STARTED = "adb.server.started"
    ADB_SERVER_STOPPED = "adb.server.stopped"
    ADB_SERVER_STATE_CHANGED = "adb.server.state.changed"
    DEVICE_AUTHENTIFICATION_SUCCEEDED = "device.authentification.succeeded"
    DEVICE_AUTHENTIFICATION_FAILED = "device.authentification.failed"
    DEVICES_UPDATED = "devices.updated"
    SIMULATION_CREATED = "simulation.created"
    SIMULATION_RESTORED = "simulation.restored"
    SIMULATION_DELETED = "simulation.deleted"
    SIMULATION_CREATION_FAILED = "simulation.creation.failed"
    SIMULATION_DELETE_SKIPPED = "simulation.delete.skipped"
    SIMULATION_STATE_CHANGED = "simulation.state.changed"
    SIMULATION_POSITION_CHANGED = "simulation.position.changed"
    SIMULATION_LOCATION_VALIDATED = "simulation.location.validated"
    SIMULATION_LOCATION_REJECTED = "simulation.location.rejected"
    SIMULATION_MAP_FILE_CHANGED = "simulation.map.file.changed"
    ERROR_RAISED = "error.raised"
    LOG_MESSAGE = "log.message"
    HOST_COMPUTER_IDENTITY_UPDATED = "host.computer.identity.updated"
    ACTIVITY_LOG_FILE_UPDATED = "activity.log.file.updated"
    MAP_RENDERED = "map.rendered"
    MAP_RENDER_FAILED = "map.render.failed"


@dataclass(frozen=True, slots=True)
class HostComputerIdentityPayload:
    """Emitted when persisted install identity has been applied to the host descriptor."""

    stable_key: str


@dataclass(frozen=True, slots=True)
class AdbServerStartedPayload:
    """Payload emitted when the ADB server starts."""

    adb_binary_path: str


@dataclass(frozen=True, slots=True)
class AdbServerStoppedPayload:
    """Payload emitted when the ADB server stops."""

    adb_binary_path: str


@dataclass(frozen=True, slots=True)
class DevicesUpdatedPayload:
    """Payload emitted when the known/connected devices list changes."""

    devices: list[dict[str, object]]
    device_id_rebindings: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeviceAuthentificationSucceededPayload:
    """Payload emitted when a device is connected successfully."""

    device: dict[str, object]


@dataclass(frozen=True, slots=True)
class DeviceAuthentificationFailedPayload:
    """Payload emitted when a device authentification fails."""

    ip: str
    port: int
    association_code: str
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationCreatedPayload:
    """Payload emitted when a simulation is created."""

    simulation_id: str
    device_id: str
    device_name: str


@dataclass(frozen=True, slots=True)
class SimulationRestoredPayload:
    """Payload emitted when a simulation is restored."""

    simulation_id: str
    device_id: str
    device_name: str


@dataclass(frozen=True, slots=True)
class SimulationDeletedPayload:
    """Payload emitted when a simulation is deleted."""

    simulation_id: str
    device_id: str | None = None


@dataclass(frozen=True, slots=True)
class SimulationCreationFailedPayload:
    """Payload emitted when simulation creation is rejected."""

    device_id: str
    device_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationDeleteSkippedPayload:
    """Payload emitted when simulation deletion is a no-op for a device."""

    device_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationStateChangedPayload:
    """Payload emitted when simulation execution state changes."""

    simulation_id: str
    active: bool


@dataclass(frozen=True, slots=True)
class SimulationPositionChangedPayload:
    """Payload emitted when the effective simulation position changes."""

    simulation_id: str
    lat: float
    lon: float
    poi: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class SimulationLocationValidatedPayload:
    """Payload emitted when a map milestone location passes referentiel validation."""

    simulation_id: str
    lat: float
    lon: float
    poi: dict[str, object]


@dataclass(frozen=True, slots=True)
class SimulationLocationRejectedPayload:
    """Payload emitted when a map milestone location is rejected."""

    simulation_id: str
    km: int
    line: str
    lat: float
    lon: float
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationMapFileChangedPayload:
    """Payload emitted when the simulation map file changes."""

    simulation_id: str
    map_file_path: Path


@dataclass(frozen=True, slots=True)
class AdbServerStateChangedPayload:
    """Payload emitted when ADB server running status changes."""

    running: bool


@dataclass(frozen=True, slots=True)
class ErrorRaisedPayload:
    """Generic payload for recoverable domain errors."""

    source: str
    message: str
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class LogMessagePayload:
    """Payload carrying domain logs to outer layers (controller/UI)."""

    level: str
    message: str


@dataclass(frozen=True, slots=True)
class ActivityLogFileUpdatedPayload:
    """Payload emitted when the activity log file is updated."""

    path: Path


@dataclass(frozen=True, slots=True)
class MapRenderedPayload:
    """Payload emitted when map HTML has been written for a simulation."""

    simulation_id: str
    html_path: Path


@dataclass(frozen=True, slots=True)
class MapRenderFailedPayload:
    """Payload emitted when map rendering fails for a simulation."""

    simulation_id: str
    reason: str


CORE_SIGNAL_PAYLOAD_TYPES: Mapping[CoreSignal, type[object]] = {
    CoreSignal.ADB_SERVER_STARTED: AdbServerStartedPayload,
    CoreSignal.ADB_SERVER_STOPPED: AdbServerStoppedPayload,
    CoreSignal.ADB_SERVER_STATE_CHANGED: AdbServerStateChangedPayload,
    CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED: DeviceAuthentificationSucceededPayload,
    CoreSignal.DEVICE_AUTHENTIFICATION_FAILED: DeviceAuthentificationFailedPayload,
    CoreSignal.DEVICES_UPDATED: DevicesUpdatedPayload,
    CoreSignal.SIMULATION_CREATED: SimulationCreatedPayload,
    CoreSignal.SIMULATION_RESTORED: SimulationRestoredPayload,
    CoreSignal.SIMULATION_DELETED: SimulationDeletedPayload,
    CoreSignal.SIMULATION_CREATION_FAILED: SimulationCreationFailedPayload,
    CoreSignal.SIMULATION_DELETE_SKIPPED: SimulationDeleteSkippedPayload,
    CoreSignal.SIMULATION_STATE_CHANGED: SimulationStateChangedPayload,
    CoreSignal.SIMULATION_POSITION_CHANGED: SimulationPositionChangedPayload,
    CoreSignal.SIMULATION_LOCATION_VALIDATED: SimulationLocationValidatedPayload,
    CoreSignal.SIMULATION_LOCATION_REJECTED: SimulationLocationRejectedPayload,
    CoreSignal.SIMULATION_MAP_FILE_CHANGED: SimulationMapFileChangedPayload,
    CoreSignal.ERROR_RAISED: ErrorRaisedPayload,
    CoreSignal.LOG_MESSAGE: LogMessagePayload,
    CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED: HostComputerIdentityPayload,
    CoreSignal.ACTIVITY_LOG_FILE_UPDATED: ActivityLogFileUpdatedPayload,
    CoreSignal.MAP_RENDERED: MapRenderedPayload,
    CoreSignal.MAP_RENDER_FAILED: MapRenderFailedPayload,
}


class CoreSignalDependencyError(RuntimeError):
    """Raised when a core signal is emitted without required prior emissions."""

    def __init__(
        self,
        *,
        signal: CoreSignal,
        missing: tuple[CoreSignal, ...],
        scope: str | None = None,
    ) -> None:
        self.signal = signal
        self.missing = missing
        self.scope = scope
        if scope is None:
            message = (
                f"Cannot emit {signal!s}: requires prior "
                f"{', '.join(str(item) for item in missing)}"
            )
        else:
            message = (
                f"Cannot emit {signal!s} for scope {scope!r}: requires prior "
                f"{', '.join(str(item) for item in missing)} with the same scope"
            )
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CoreSignalDependencyRule:
    """One dependency requirement: any listed signal may satisfy the rule."""

    any_of: tuple[CoreSignal, ...]
    match_scope_from: str | None = None


@dataclass(frozen=True, slots=True)
class CoreSignalEmission:
    """One recorded core signal emission for debugging and dependency checks."""

    signal: CoreSignal
    payload: object
    scope: str | None = None


# Payload field used to index scoped emissions for dependency checks.
CORE_SIGNAL_SCOPE_FIELDS: Mapping[CoreSignal, str] = {
    CoreSignal.ADB_SERVER_STARTED: "adb_binary_path",
    CoreSignal.ADB_SERVER_STOPPED: "adb_binary_path",
    CoreSignal.SIMULATION_CREATED: "simulation_id",
    CoreSignal.SIMULATION_RESTORED: "simulation_id",
    CoreSignal.SIMULATION_DELETED: "simulation_id",
    CoreSignal.SIMULATION_STATE_CHANGED: "simulation_id",
    CoreSignal.SIMULATION_POSITION_CHANGED: "simulation_id",
    CoreSignal.SIMULATION_LOCATION_VALIDATED: "simulation_id",
    CoreSignal.SIMULATION_LOCATION_REJECTED: "simulation_id",
    CoreSignal.SIMULATION_MAP_FILE_CHANGED: "simulation_id",
    CoreSignal.MAP_RENDERED: "simulation_id",
    CoreSignal.MAP_RENDER_FAILED: "simulation_id",
}

# Required prior emissions before a signal may be published on the core bus.
CORE_SIGNAL_DEPENDENCIES: Mapping[CoreSignal, tuple[CoreSignalDependencyRule, ...]] = {
    CoreSignal.ADB_SERVER_STOPPED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignal.ADB_SERVER_STARTED,),
            match_scope_from="adb_binary_path",
        ),
    ),
    CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED: (
        CoreSignalDependencyRule(any_of=(CoreSignal.ADB_SERVER_STARTED,)),
    ),
    CoreSignal.DEVICES_UPDATED: (
        CoreSignalDependencyRule(any_of=(CoreSignal.ADB_SERVER_STARTED,)),
    ),
    CoreSignal.SIMULATION_CREATED: (
        CoreSignalDependencyRule(any_of=(CoreSignal.DEVICES_UPDATED,)),
    ),
    CoreSignal.SIMULATION_RESTORED: (
        CoreSignalDependencyRule(any_of=(CoreSignal.DEVICES_UPDATED,)),
    ),
    CoreSignal.SIMULATION_DELETED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignal.SIMULATION_CREATED, CoreSignal.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignal.SIMULATION_STATE_CHANGED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignal.SIMULATION_CREATED, CoreSignal.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignal.SIMULATION_POSITION_CHANGED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignal.SIMULATION_CREATED, CoreSignal.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignal.SIMULATION_LOCATION_VALIDATED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignal.SIMULATION_CREATED, CoreSignal.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignal.SIMULATION_LOCATION_REJECTED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignal.SIMULATION_CREATED, CoreSignal.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignal.SIMULATION_MAP_FILE_CHANGED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignal.SIMULATION_CREATED, CoreSignal.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignal.MAP_RENDERED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignal.SIMULATION_CREATED, CoreSignal.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignal.MAP_RENDER_FAILED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignal.SIMULATION_CREATED, CoreSignal.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
}


def _extract_core_signal_scope(signal: CoreSignal, payload: object) -> str | None:
    """Return the scoped entity key carried by *payload*, when defined for *signal*."""
    field_name = CORE_SIGNAL_SCOPE_FIELDS.get(signal)
    if field_name is None:
        return None
    value = getattr(payload, field_name, None)
    if value is None:
        return None
    return str(value)


PayloadT = TypeVar("PayloadT", contravariant=True)


class SignalHandler(Protocol[PayloadT]):
    """
    Contract for callback functions handling a given payload type.

    This protocol keeps handlers strongly typed while allowing plain callables.
    """

    def __call__(self, payload: PayloadT) -> None:
        """Handle one payload emitted for a signal."""
        pass


class CoreSignalBus(ABC):
    """
    Abstract, high-performance-friendly signal bus contract.

    This class intentionally defines the API only:
    - no storage strategy
    - no threading model
    - no dispatch implementation

    Concrete implementations can optimize for sync dispatch, async dispatch,
    lock-free reads, or thread-safe observer management.
    """

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STARTED],
        handler: SignalHandler[AdbServerStartedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STOPPED],
        handler: SignalHandler[AdbServerStoppedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STATE_CHANGED],
        handler: SignalHandler[AdbServerStateChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED],
        handler: SignalHandler[DeviceAuthentificationSucceededPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_FAILED],
        handler: SignalHandler[DeviceAuthentificationFailedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.DEVICES_UPDATED],
        handler: SignalHandler[DevicesUpdatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATED],
        handler: SignalHandler[SimulationCreatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_RESTORED],
        handler: SignalHandler[SimulationRestoredPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATION_FAILED],
        handler: SignalHandler[SimulationCreationFailedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETE_SKIPPED],
        handler: SignalHandler[SimulationDeleteSkippedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_STATE_CHANGED],
        handler: SignalHandler[SimulationStateChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_POSITION_CHANGED],
        handler: SignalHandler[SimulationPositionChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_VALIDATED],
        handler: SignalHandler[SimulationLocationValidatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_REJECTED],
        handler: SignalHandler[SimulationLocationRejectedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_MAP_FILE_CHANGED],
        handler: SignalHandler[SimulationMapFileChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ERROR_RAISED],
        handler: SignalHandler[ErrorRaisedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.LOG_MESSAGE],
        handler: SignalHandler[LogMessagePayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED],
        handler: SignalHandler[HostComputerIdentityPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ACTIVITY_LOG_FILE_UPDATED],
        handler: SignalHandler[ActivityLogFileUpdatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDERED],
        handler: SignalHandler[MapRenderedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDER_FAILED],
        handler: SignalHandler[MapRenderFailedPayload],
    ) -> None: ...

    @overload
    def subscribe(self, signal: CoreSignal, handler: SignalHandler[object]) -> None: ...

    @abstractmethod
    def subscribe(self, signal: CoreSignal, handler: SignalHandler[Any]) -> None:
        """
        Register a handler for one core signal.

        Implementations should make subscription idempotency/duplication behavior
        explicit (allow duplicates vs reject duplicates).
        """
        ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STARTED],
        handler: SignalHandler[AdbServerStartedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STOPPED],
        handler: SignalHandler[AdbServerStoppedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STATE_CHANGED],
        handler: SignalHandler[AdbServerStateChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED],
        handler: SignalHandler[DeviceAuthentificationSucceededPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_FAILED],
        handler: SignalHandler[DeviceAuthentificationFailedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.DEVICES_UPDATED],
        handler: SignalHandler[DevicesUpdatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATED],
        handler: SignalHandler[SimulationCreatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_RESTORED],
        handler: SignalHandler[SimulationRestoredPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATION_FAILED],
        handler: SignalHandler[SimulationCreationFailedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETE_SKIPPED],
        handler: SignalHandler[SimulationDeleteSkippedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_STATE_CHANGED],
        handler: SignalHandler[SimulationStateChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_POSITION_CHANGED],
        handler: SignalHandler[SimulationPositionChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_VALIDATED],
        handler: SignalHandler[SimulationLocationValidatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_REJECTED],
        handler: SignalHandler[SimulationLocationRejectedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_MAP_FILE_CHANGED],
        handler: SignalHandler[SimulationMapFileChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ERROR_RAISED],
        handler: SignalHandler[ErrorRaisedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.LOG_MESSAGE],
        handler: SignalHandler[LogMessagePayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED],
        handler: SignalHandler[HostComputerIdentityPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ACTIVITY_LOG_FILE_UPDATED],
        handler: SignalHandler[ActivityLogFileUpdatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDERED],
        handler: SignalHandler[MapRenderedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDER_FAILED],
        handler: SignalHandler[MapRenderFailedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self, signal: CoreSignal, handler: SignalHandler[object]
    ) -> None: ...

    @abstractmethod
    def unsubscribe(self, signal: CoreSignal, handler: SignalHandler[Any]) -> None:
        """
        Remove a previously registered handler for one core signal.

        Implementations should define behavior when handler/signal does not exist.
        """
        ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STARTED],
        payload: AdbServerStartedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STOPPED],
        payload: AdbServerStoppedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STATE_CHANGED],
        payload: AdbServerStateChangedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED],
        payload: DeviceAuthentificationSucceededPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_FAILED],
        payload: DeviceAuthentificationFailedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.DEVICES_UPDATED],
        payload: DevicesUpdatedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATED],
        payload: SimulationCreatedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_RESTORED],
        payload: SimulationRestoredPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        payload: SimulationDeletedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATION_FAILED],
        payload: SimulationCreationFailedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETE_SKIPPED],
        payload: SimulationDeleteSkippedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_STATE_CHANGED],
        payload: SimulationStateChangedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_POSITION_CHANGED],
        payload: SimulationPositionChangedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_VALIDATED],
        payload: SimulationLocationValidatedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_REJECTED],
        payload: SimulationLocationRejectedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_MAP_FILE_CHANGED],
        payload: SimulationMapFileChangedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ERROR_RAISED],
        payload: ErrorRaisedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.LOG_MESSAGE],
        payload: LogMessagePayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED],
        payload: HostComputerIdentityPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ACTIVITY_LOG_FILE_UPDATED],
        payload: ActivityLogFileUpdatedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.MAP_RENDERED],
        payload: MapRenderedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.MAP_RENDER_FAILED],
        payload: MapRenderFailedPayload,
    ) -> None: ...

    @overload
    def emit(self, signal: CoreSignal, payload: Any) -> None: ...

    @abstractmethod
    def emit(self, signal: CoreSignal, payload: Any) -> None:
        """
        Publish one payload to all handlers subscribed to the signal.

        Implementations should document:
        - ordering guarantees
        - exception policy (fail-fast vs collect/log and continue)
        - re-entrancy behavior
        """
        ...


class InMemoryCoreSignalBus(CoreSignalBus):
    """
    Concrete, synchronous in-memory signal bus.

    Design goals:
    - O(1) signal lookup using a dictionary keyed by CoreSignal.
    - Stable dispatch order by preserving handler insertion order.
    - Safe iteration while handlers mutate subscriptions during dispatch by
      iterating over a shallow snapshot.
    """

    def __init__(self) -> None:
        self._subscribers: dict[CoreSignal, list[SignalHandler[Any]]] = {}
        self._emissions: list[CoreSignalEmission] = []
        self._emitted_global: set[CoreSignal] = set()
        self._emitted_scoped: set[tuple[CoreSignal, str]] = set()

    @property
    def history(self) -> tuple[CoreSignalEmission, ...]:
        """Return all recorded emissions in dispatch order."""
        return tuple(self._emissions)

    def has_emitted(self, signal: CoreSignal, *, scope: str | None = None) -> bool:
        """Return whether *signal* was emitted, optionally for one scoped entity."""
        if scope is None:
            return signal in self._emitted_global
        return (signal, scope) in self._emitted_scoped

    def _validate_payload_type(self, signal: CoreSignal, payload: object) -> None:
        expected_type = CORE_SIGNAL_PAYLOAD_TYPES.get(signal)
        if expected_type is not None and not isinstance(payload, expected_type):
            raise TypeError(
                f"CoreSignalBus.emit expected {expected_type.__name__} for "
                f"{signal!s}, got {type(payload).__name__}"
            )

    def _enforce_dependencies(self, signal: CoreSignal, payload: object) -> None:
        rules = CORE_SIGNAL_DEPENDENCIES.get(signal, ())
        for rule in rules:
            if rule.match_scope_from is None:
                if any(
                    required_signal in self._emitted_global
                    for required_signal in rule.any_of
                ):
                    continue
                raise CoreSignalDependencyError(
                    signal=signal,
                    missing=rule.any_of,
                )

            scope_value = getattr(payload, rule.match_scope_from, None)
            if scope_value is None:
                raise CoreSignalDependencyError(
                    signal=signal,
                    missing=rule.any_of,
                )
            scope_key = str(scope_value)
            if any(
                (required_signal, scope_key) in self._emitted_scoped
                for required_signal in rule.any_of
            ):
                continue
            raise CoreSignalDependencyError(
                signal=signal,
                missing=rule.any_of,
                scope=scope_key,
            )

    def _record_emission(self, signal: CoreSignal, payload: object) -> None:
        scope = _extract_core_signal_scope(signal, payload)
        self._emissions.append(
            CoreSignalEmission(signal=signal, payload=payload, scope=scope)
        )
        self._emitted_global.add(signal)
        if scope is not None:
            self._emitted_scoped.add((signal, scope))

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STARTED],
        handler: SignalHandler[AdbServerStartedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STOPPED],
        handler: SignalHandler[AdbServerStoppedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STATE_CHANGED],
        handler: SignalHandler[AdbServerStateChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED],
        handler: SignalHandler[DeviceAuthentificationSucceededPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_FAILED],
        handler: SignalHandler[DeviceAuthentificationFailedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.DEVICES_UPDATED],
        handler: SignalHandler[DevicesUpdatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATED],
        handler: SignalHandler[SimulationCreatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_RESTORED],
        handler: SignalHandler[SimulationRestoredPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATION_FAILED],
        handler: SignalHandler[SimulationCreationFailedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETE_SKIPPED],
        handler: SignalHandler[SimulationDeleteSkippedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_STATE_CHANGED],
        handler: SignalHandler[SimulationStateChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_POSITION_CHANGED],
        handler: SignalHandler[SimulationPositionChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_VALIDATED],
        handler: SignalHandler[SimulationLocationValidatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_REJECTED],
        handler: SignalHandler[SimulationLocationRejectedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_MAP_FILE_CHANGED],
        handler: SignalHandler[SimulationMapFileChangedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ERROR_RAISED],
        handler: SignalHandler[ErrorRaisedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.LOG_MESSAGE],
        handler: SignalHandler[LogMessagePayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED],
        handler: SignalHandler[HostComputerIdentityPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.ACTIVITY_LOG_FILE_UPDATED],
        handler: SignalHandler[ActivityLogFileUpdatedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDERED],
        handler: SignalHandler[MapRenderedPayload],
    ) -> None: ...

    @overload
    def subscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDER_FAILED],
        handler: SignalHandler[MapRenderFailedPayload],
    ) -> None: ...

    @overload
    def subscribe(self, signal: CoreSignal, handler: SignalHandler[object]) -> None: ...

    def subscribe(self, signal: CoreSignal, handler: SignalHandler[Any]) -> None:
        """
        Register a handler for one signal.

        Duplicate registrations are ignored to keep callback cardinality stable.
        """
        handlers = self._subscribers.setdefault(signal, [])
        if handler in handlers:
            logger.debug(
                "CoreSignalBus: subscription ignored (duplicate handler)",
                signal=str(signal),
            )
            return
        handlers.append(handler)
        logger.debug(
            "CoreSignalBus: handler subscribed",
            signal=str(signal),
            subscriber_count=len(handlers),
        )

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STARTED],
        handler: SignalHandler[AdbServerStartedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STOPPED],
        handler: SignalHandler[AdbServerStoppedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STATE_CHANGED],
        handler: SignalHandler[AdbServerStateChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED],
        handler: SignalHandler[DeviceAuthentificationSucceededPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_FAILED],
        handler: SignalHandler[DeviceAuthentificationFailedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.DEVICES_UPDATED],
        handler: SignalHandler[DevicesUpdatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATED],
        handler: SignalHandler[SimulationCreatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_RESTORED],
        handler: SignalHandler[SimulationRestoredPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATION_FAILED],
        handler: SignalHandler[SimulationCreationFailedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETE_SKIPPED],
        handler: SignalHandler[SimulationDeleteSkippedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_STATE_CHANGED],
        handler: SignalHandler[SimulationStateChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_POSITION_CHANGED],
        handler: SignalHandler[SimulationPositionChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_VALIDATED],
        handler: SignalHandler[SimulationLocationValidatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_REJECTED],
        handler: SignalHandler[SimulationLocationRejectedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.SIMULATION_MAP_FILE_CHANGED],
        handler: SignalHandler[SimulationMapFileChangedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ERROR_RAISED],
        handler: SignalHandler[ErrorRaisedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.LOG_MESSAGE],
        handler: SignalHandler[LogMessagePayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED],
        handler: SignalHandler[HostComputerIdentityPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.ACTIVITY_LOG_FILE_UPDATED],
        handler: SignalHandler[ActivityLogFileUpdatedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDERED],
        handler: SignalHandler[MapRenderedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self,
        signal: Literal[CoreSignal.MAP_RENDER_FAILED],
        handler: SignalHandler[MapRenderFailedPayload],
    ) -> None: ...

    @overload
    def unsubscribe(
        self, signal: CoreSignal, handler: SignalHandler[object]
    ) -> None: ...

    def unsubscribe(self, signal: CoreSignal, handler: SignalHandler[Any]) -> None:
        """
        Remove a handler from one signal.

        If the signal or handler does not exist, this method is a no-op.
        """
        handlers = self._subscribers.get(signal)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            return
        if not handlers:
            self._subscribers.pop(signal, None)
        logger.debug(
            "CoreSignalBus: handler unsubscribed",
            signal=str(signal),
            subscriber_count=len(self._subscribers.get(signal, [])),
        )

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STARTED],
        payload: AdbServerStartedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STOPPED],
        payload: AdbServerStoppedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ADB_SERVER_STATE_CHANGED],
        payload: AdbServerStateChangedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED],
        payload: DeviceAuthentificationSucceededPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.DEVICE_AUTHENTIFICATION_FAILED],
        payload: DeviceAuthentificationFailedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.DEVICES_UPDATED],
        payload: DevicesUpdatedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATED],
        payload: SimulationCreatedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_RESTORED],
        payload: SimulationRestoredPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        payload: SimulationDeletedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_CREATION_FAILED],
        payload: SimulationCreationFailedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_DELETE_SKIPPED],
        payload: SimulationDeleteSkippedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_STATE_CHANGED],
        payload: SimulationStateChangedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_POSITION_CHANGED],
        payload: SimulationPositionChangedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_VALIDATED],
        payload: SimulationLocationValidatedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_LOCATION_REJECTED],
        payload: SimulationLocationRejectedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.SIMULATION_MAP_FILE_CHANGED],
        payload: SimulationMapFileChangedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ERROR_RAISED],
        payload: ErrorRaisedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.LOG_MESSAGE],
        payload: LogMessagePayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED],
        payload: HostComputerIdentityPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.ACTIVITY_LOG_FILE_UPDATED],
        payload: ActivityLogFileUpdatedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.MAP_RENDERED],
        payload: MapRenderedPayload,
    ) -> None: ...

    @overload
    def emit(
        self,
        signal: Literal[CoreSignal.MAP_RENDER_FAILED],
        payload: MapRenderFailedPayload,
    ) -> None: ...

    @overload
    def emit(self, signal: CoreSignal, payload: Any) -> None: ...

    def emit(self, signal: CoreSignal, payload: Any) -> None:
        """
        Emit one payload to all current handlers of a signal.

        Validates payload type and dependency history before recording the
        emission. Exception policy: log and continue to avoid one faulty callback
        blocking all downstream handlers.
        """
        self._validate_payload_type(signal, payload)
        self._enforce_dependencies(signal, payload)
        self._record_emission(signal, payload)

        handlers = self._subscribers.get(signal, [])
        if not handlers:
            return

        # Snapshot avoids mutation issues when handlers subscribe/unsubscribe.
        for handler in tuple(handlers):
            try:
                handler(payload)
            except Exception:
                logger.exception(
                    "CoreSignalBus: handler raised during emit",
                    signal=str(signal),
                    payload_type=type(payload).__name__,
                )
