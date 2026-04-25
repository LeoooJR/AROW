from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, TypeVar

from core.adb import AdbBinary
from core.devices import Phone
from core.location import Location
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
    DEVICE_CONNECTION_SUCCEEDED = "device.connection.succeeded"
    DEVICE_CONNECTION_FAILED = "device.connection.failed"
    DEVICES_UPDATED = "devices.updated"
    SIMULATION_STATE_CHANGED = "simulation.state.changed"
    SIMULATION_POSITION_CHANGED = "simulation.position.changed"
    ERROR_RAISED = "error.raised"
    LOG_MESSAGE = "log.message"


@dataclass(frozen=True, slots=True)
class AdbServerStartedPayload:
    """Payload emitted when the ADB server starts."""

    adb_binary: AdbBinary


@dataclass(frozen=True, slots=True)
class AdbServerStoppedPayload:
    """Payload emitted when the ADB server stops."""

    adb_binary: AdbBinary


@dataclass(frozen=True, slots=True)
class DevicesUpdatedPayload:
    """Payload emitted when the known/connected devices list changes."""

    devices: list[Phone]


@dataclass(frozen=True, slots=True)
class DeviceConnectionSucceededPayload:
    """Payload emitted when a device is connected successfully."""

    phone: Phone


@dataclass(frozen=True, slots=True)
class DeviceConnectionFailedPayload:
    """Payload emitted when a device connection fails."""

    ip: str
    port: int
    association_code: str


@dataclass(frozen=True, slots=True)
class SimulationStateChangedPayload:
    """Payload emitted when simulation execution state changes."""

    active: bool
    paused: bool


@dataclass(frozen=True, slots=True)
class SimulationPositionChangedPayload:
    """Payload emitted when the effective simulation position changes."""

    location: Location


@dataclass(frozen=True, slots=True)
class AdbServerStateChangedPayload:
    """Payload emitted when ADB server running status changes."""

    running: bool


@dataclass(frozen=True, slots=True)
class ErrorRaisedPayload:
    """Generic payload for recoverable domain errors."""

    source: str
    message: str
    error: Exception | None = None


@dataclass(frozen=True, slots=True)
class LogMessagePayload:
    """Payload carrying domain logs to outer layers (controller/UI)."""

    level: str
    message: str


PayloadT = TypeVar("PayloadT")


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

    @abstractmethod
    def subscribe(self, signal: CoreSignal, handler: SignalHandler[object]) -> None:
        """
        Register a handler for one core signal.

        Implementations should make subscription idempotency/duplication behavior
        explicit (allow duplicates vs reject duplicates).
        """
        pass

    @abstractmethod
    def unsubscribe(self, signal: CoreSignal, handler: SignalHandler[object]) -> None:
        """
        Remove a previously registered handler for one core signal.

        Implementations should define behavior when handler/signal does not exist.
        """
        pass

    @abstractmethod
    def emit(self, signal: CoreSignal, payload: object) -> None:
        """
        Publish one payload to all handlers subscribed to the signal.

        Implementations should document:
        - ordering guarantees
        - exception policy (fail-fast vs collect/log and continue)
        - re-entrancy behavior
        """
        pass


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
        self._subscribers: dict[CoreSignal, list[SignalHandler[object]]] = {}

    def subscribe(self, signal: CoreSignal, handler: SignalHandler[object]) -> None:
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

    def unsubscribe(self, signal: CoreSignal, handler: SignalHandler[object]) -> None:
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

    def emit(self, signal: CoreSignal, payload: object) -> None:
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
