"""
Abstract contract for AsyncRunner-backed core jobs: blocking ``run`` on a worker and
``apply_main_thread`` on the Qt main thread (often via ``ModelEntrypoint.apply_result``).

Asynchronous worker must return a :class:`CoreRuntimeWorkOutcome` subtype that can be applied on
the main thread.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

from core.signals import CoreSignal, ErrorRaisedPayload

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint


class CoreRuntimeWorkOutcome:
    """
    Marker base for payloads returned from :meth:`CoreRuntimeWork.run` and passed to
    :meth:`CoreRuntimeWork.apply_main_thread` / :meth:`ModelEntrypoint.apply_result`.

    Concrete types are frozen dataclasses under ``src/core/work/``; they need not share fields.
    """

    __slots__ = ()


TOutcome = TypeVar("TOutcome", bound=CoreRuntimeWorkOutcome)


class CoreRuntimeWork(ABC, Generic[TOutcome]):
    """
    Concrete subclasses carry worker inputs in ``__init__``, implement blocking ``run``, and expose
    a static ``apply_main_thread(model_entrypoint, outcome)`` for dispatcher registration by outcome type
    (no sentinel worker instance needed).
    """

    @abstractmethod
    def run(self) -> TOutcome:
        """
        Execute blocking model work on an AsyncRunner worker thread.

        Subclasses perform I/O or other blocking steps here and return a
        :class:`CoreRuntimeWorkOutcome` subtype. Main-thread mutation and core-bus
        emission belong in :meth:`apply_main_thread`, not in ``run``.

        Returns:
            TOutcome: Concrete outcome payload for the matching
            :meth:`apply_main_thread` implementation.

        Raises:
            NotImplementedError: This abstract method has no body.
            Exception: Concrete subclasses define which project exceptions may
            propagate to AsyncRunner; see each work module's ``run`` docstring.
        """
        ...

    @staticmethod
    @abstractmethod
    def apply_main_thread(model_entrypoint: ModelEntrypoint, outcome: TOutcome) -> None:
        """Emit on the core bus / mutate entrypoint; call only from the Qt main thread."""
        ...

    @staticmethod
    @abstractmethod
    def apply_failure_main_thread(
        model_entrypoint: ModelEntrypoint, error: BaseException
    ) -> None:
        """Handle worker failure on the Qt main thread (via :meth:`~core.entrypoint.ModelEntrypoint.apply_failure`)."""
        ...

    @staticmethod
    def emit_generic_error(
        model_entrypoint: ModelEntrypoint,
        *,
        source: str,
        message: str,
        error: BaseException | None = None,
    ) -> None:
        """Emit a generic error on the core signal bus (Qt main thread)."""
        payload_error = error if isinstance(error, Exception) else None
        model_entrypoint._signal_bus.emit(
            CoreSignal.ERROR_RAISED,
            ErrorRaisedPayload(source=source, message=message, error=payload_error),
        )
