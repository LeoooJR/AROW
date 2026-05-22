"""Shared abstract base for subcontrollers owned by :class:`AppController`."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from core.models import CoreRuntimeModel
from gui.window import MainWindow

if TYPE_CHECKING:
    from controller.orchestration.app_controller import AppController


class AppSubController(ABC):
    """Subcontroller slice: shared access to app model/view and signal wiring hooks."""

    def __init__(self, app: AppController) -> None:
        self._app = app

    @property
    def model(self) -> CoreRuntimeModel:
        return self._app.model

    @property
    def view(self) -> MainWindow:
        return self._app.view

    @abstractmethod
    def connect_view_signals(self) -> None:
        """Wire :data:`gui.signals.view_signals` for this domain."""
        ...

    @abstractmethod
    def connect_model_signals(self) -> None:
        """Subscribe to :class:`core.signals.CoreSignal` (or related) for this domain."""
        ...
