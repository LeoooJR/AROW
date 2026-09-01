"""Qt timer helpers for controller and *SubController methods."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QTimer


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
