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
  ``to_payload()``) into a ``dict`` and carry only that dict in the payload.
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
    SIMULATION_DELETED = "simulation.deleted"
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
class SimulationDeletedPayload:
    """Payload emitted when a simulation is deleted."""

    simulation_id: str


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
    label: str | None


@dataclass(frozen=True, slots=True)
class SimulationLocationValidatedPayload:
    """Payload emitted when a map milestone location passes referentiel validation."""

    simulation_id: str
    id: str
    lat: float
    lon: float
    label: str | None
    code_line: str | None = None
    type: str | None = None


@dataclass(frozen=True, slots=True)
class SimulationLocationRejectedPayload:
    """Payload emitted when a map milestone location is rejected."""

    simulation_id: str
    id: str
    code_line: str
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
    CoreSignal.SIMULATION_DELETED: SimulationDeletedPayload,
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
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
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
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
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
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        payload: SimulationDeletedPayload,
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
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
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
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        handler: SignalHandler[SimulationDeletedPayload],
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
        signal: Literal[CoreSignal.SIMULATION_DELETED],
        payload: SimulationDeletedPayload,
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

        Exception policy: log and continue to avoid one faulty callback blocking
        all downstream handlers.
        """
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
