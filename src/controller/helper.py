"""Shared decorator helpers for controller and *SubController methods."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QTimer

from core.models import CoreRuntimeModel
from gui.window import MainWindow
from logger import logger


def validate_model(function: Callable[..., Any]) -> Callable[..., Any]:
    """Validate the model for the function.

    Args:
        function: Function to validate the model for.

    Returns:
        Function: Function with the model validated.
    """

    def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self, "model"):
            if not isinstance(self.model, CoreRuntimeModel):
                logger.warning(
                    "Controller: model type mismatch",
                    model_type=type(self.model).__name__,
                )
                return
        elif hasattr(self, "_subcontroller"):
            if not isinstance(self._subcontroller.model, CoreRuntimeModel):
                logger.warning(
                    "Controller: model type mismatch",
                    model_type=type(self._subcontroller.model).__name__,
                )
                return
        else:
            raise ValueError("Model not found")
        return function(self, *args, **kwargs)

    return wrapper


def validate_view(function: Callable[..., Any]) -> Callable[..., Any]:
    """Validate the view for the function.

    Args:
        function: Function to validate the view for.

    Returns:
        Function: Function with the view validated.
    """

    def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        if hasattr(self, "view"):
            if not isinstance(self.view, MainWindow):
                logger.warning(
                    "Controller: view type mismatch",
                    view_type=type(self.view).__name__,
                )
                return
        elif hasattr(self, "_subcontroller"):
            if not isinstance(self._subcontroller.view, MainWindow):
                logger.warning(
                    "Controller: view type mismatch",
                    view_type=type(self._subcontroller.view).__name__,
                )
                return
        else:
            raise ValueError("View not found")
        return function(self, *args, **kwargs)

    return wrapper


def delay(ms: int) -> Callable[[Callable[..., Any]], QTimer]:
    """
    Single-shot QTimer: call ``delay(ms)(f)`` to run *f* after *ms*.

    The timeout slot invokes *f* when the timer fires; it must not call *f* at
    connection time (``connect(f())``).
    """

    def wrapper(function: Callable[..., Any]) -> QTimer:
        timer = QTimer()
        timer.setSingleShot(True)

        def _on_timeout() -> None:
            function()

        timer.timeout.connect(_on_timeout)
        timer.start(ms)
        return timer

    return wrapper


def watchdog(ms: int) -> Callable[[Callable[..., Any]], QTimer]:
    """
    Start a single-shot QTimer that invokes *function* when *ms* elapses.

    Connects the timeout slot so *function* runs on fire, not at connection time
    (``connect(f())`` would call *f* immediately and wire the return value).

    Returns the started timer; stop it when work finishes early and/or in a
    ``finally`` block so the payload does not run after teardown.
    """

    def wrapper(function: Callable[..., Any]) -> QTimer:
        timer = QTimer()
        timer.setSingleShot(True)

        def _on_timeout() -> None:
            function()

        timer.timeout.connect(_on_timeout)
        timer.start(ms)
        return timer

    return wrapper


def repeat(ms: int) -> Callable[[Callable[..., Any]], QTimer]:
    """
    Repeating QTimer: call ``repeat(ms)(f)`` to invoke *f* every *ms*.

    Same connection rules as :func:`delay`; stop the returned timer to end repeats.
    """

    def wrapper(function: Callable[..., Any]) -> QTimer:
        timer = QTimer()
        timer.setSingleShot(False)

        def _on_timeout() -> None:
            function()

        timer.timeout.connect(_on_timeout)
        timer.start(ms)
        return timer

    return wrapper
