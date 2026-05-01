"""
Abstract contract for AsyncRunner-backed core jobs: blocking ``run`` on a worker and
``apply_main_thread`` on the Qt main thread (often via ``CoreRuntimeModel.apply_result``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from core.models import CoreRuntimeModel

TOutcome = TypeVar("TOutcome")


class CoreRuntimeWork(ABC, Generic[TOutcome]):
    """
    Concrete subclasses carry worker inputs in ``__init__``, implement blocking ``run``, and expose
    a static ``apply_main_thread(model, outcome)`` for dispatcher registration by outcome type
    (no sentinel worker instance needed).
    """

    @abstractmethod
    def run(self) -> TOutcome:
        """Blocking work executed on an AsyncRunner worker thread."""
        ...

    @staticmethod
    @abstractmethod
    def apply_main_thread(model: CoreRuntimeModel, outcome: TOutcome) -> None:
        """Emit on the core bus / mutate model; call only from the Qt main thread."""
        ...
