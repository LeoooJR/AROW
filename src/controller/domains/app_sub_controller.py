"""Shared abstract base for subcontrollers owned by :class:`AppController`."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from controller.cron import CronJob
from core.entrypoint import ModelEntrypoint
from gui.windows import MainWindow

if TYPE_CHECKING:
    from controller.orchestration.app_controller import AppController


class AppSubController(ABC):
    """Subcontroller slice: shared access to app model entrypoint/view and signal wiring hooks."""

    def __init__(self, app: AppController) -> None:
        """Initialize a domain subcontroller owned by the application controller."""
        self._app = app

    @property
    def model_entrypoint(self) -> ModelEntrypoint:
        """Return the shared model entrypoint."""
        return self._app.model_entrypoint

    @property
    def view(self) -> MainWindow:
        """Return the shared main window."""
        return self._app.view

    def declare_cron_jobs(self) -> tuple[CronJob, ...]:
        """Return recurring async jobs owned by this domain."""
        return ()

    @abstractmethod
    def connect_view_signals(self) -> None:
        """Wire :data:`gui.signals.signals` for this domain."""
        ...

    @abstractmethod
    def connect_model_signals(self) -> None:
        """Subscribe to :class:`core.signals.CoreSignal` (or related) for this domain."""
        ...
