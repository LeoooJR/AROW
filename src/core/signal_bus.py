"""
Core signal bus protocol and in-memory dispatch implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, Protocol, TypeVar

from core.signals import (
    CORE_SIGNAL_DEPENDENCIES,
    CoreSignal,
    CoreSignalDependencyError,
    CoreSignalEmission,
    extract_core_signal_scope,
)
from logger import logger

PayloadT = TypeVar("PayloadT", contravariant=True)


class SignalHandler(Protocol[PayloadT]):
    """Contract for callback functions handling a given payload type."""

    def __call__(self, payload: PayloadT) -> None:
        """Handle one payload emitted for a signal."""
        ...


class CoreSignalSubscription:
    """Handle returned by :meth:`CoreSignalBus.subscribe` for idempotent teardown."""

    __slots__ = ("_active", "_bus", "_handler", "_signal")

    def __init__(
        self,
        bus: CoreSignalBus,
        signal: CoreSignal[Any],
        handler: SignalHandler[Any],
    ) -> None:
        self._bus = bus
        self._signal = signal
        self._handler = handler
        self._active = True

    def unsubscribe(self) -> None:
        """Remove the subscription once; later calls are no-ops."""
        if not self._active:
            return
        self._bus.unsubscribe(self._signal, self._handler)
        self._active = False


class CoreSignalBus(ABC):
    """
    Abstract signal bus contract.

    Concrete implementations define storage, threading, and dispatch policy.
    """

    @abstractmethod
    def subscribe(
        self,
        signal: CoreSignal[PayloadT],
        handler: SignalHandler[PayloadT],
    ) -> CoreSignalSubscription:
        """Register a handler for one core signal."""
        ...

    @abstractmethod
    def unsubscribe(
        self,
        signal: CoreSignal[PayloadT],
        handler: SignalHandler[PayloadT],
    ) -> None:
        """Remove a previously registered handler for one core signal."""
        ...

    @abstractmethod
    def emit(
        self,
        signal: CoreSignal[PayloadT],
        payload: PayloadT,
    ) -> None:
        """Publish one payload to all handlers subscribed to the signal."""
        ...


class InMemoryCoreSignalBus(CoreSignalBus):
    """
    Concrete, synchronous in-memory signal bus.

    Design goals:
    - O(1) signal lookup using a dictionary keyed by CoreSignal tokens.
    - Stable dispatch order by preserving handler insertion order.
    - Safe iteration while handlers mutate subscriptions during dispatch by
      iterating over a shallow snapshot.
    """

    def __init__(self) -> None:
        self._subscribers: dict[CoreSignal[Any], list[SignalHandler[Any]]] = {}
        self._emissions: list[CoreSignalEmission] = []
        self._emitted_global: set[CoreSignal[Any]] = set()
        self._emitted_scoped: set[tuple[CoreSignal[Any], str]] = set()

    @property
    def history(self) -> tuple[CoreSignalEmission, ...]:
        """Return all recorded emissions in dispatch order."""
        return tuple(self._emissions)

    def has_emitted(self, signal: CoreSignal[Any], *, scope: str | None = None) -> bool:
        """Return whether *signal* was emitted, optionally for one scoped entity."""
        if scope is None:
            return signal in self._emitted_global
        return (signal, scope) in self._emitted_scoped

    def _validate_payload_type(self, signal: CoreSignal[Any], payload: object) -> None:
        expected_type = signal.payload_type
        if not isinstance(payload, expected_type):
            raise TypeError(
                f"CoreSignalBus.emit expected {expected_type.__name__} for "
                f"{signal!s}, got {type(payload).__name__}"
            )

    def _enforce_dependencies(self, signal: CoreSignal[Any], payload: object) -> None:
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

    def _record_emission(self, signal: CoreSignal[Any], payload: object) -> None:
        scope = extract_core_signal_scope(signal, payload)
        self._emissions.append(
            CoreSignalEmission(signal=signal, payload=payload, scope=scope)
        )
        self._emitted_global.add(signal)
        if scope is not None:
            self._emitted_scoped.add((signal, scope))

    def subscribe(
        self,
        signal: CoreSignal[PayloadT],
        handler: SignalHandler[PayloadT],
    ) -> CoreSignalSubscription:
        """
        Register a handler for one signal.

        Duplicate registrations are ignored to keep callback cardinality stable.
        """
        handlers = self._subscribers.setdefault(signal, [])
        if handler in handlers:
            logger.debug(
                "Duplicate core signal subscription ignored",
                signal=str(signal),
            )
            return CoreSignalSubscription(self, signal, handler)
        handlers.append(handler)
        logger.debug(
            "Core signal handler subscribed",
            signal=str(signal),
            subscriber_count=len(handlers),
        )
        return CoreSignalSubscription(self, signal, handler)

    def unsubscribe(
        self,
        signal: CoreSignal[PayloadT],
        handler: SignalHandler[PayloadT],
    ) -> None:
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
            "Core signal handler unsubscribed",
            signal=str(signal),
            subscriber_count=len(self._subscribers.get(signal, [])),
        )

    def emit(
        self,
        signal: CoreSignal[PayloadT],
        payload: PayloadT,
    ) -> None:
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
                    "Core signal handler raised while processing an event",
                    signal=str(signal),
                    payload_type=type(payload).__name__,
                )
