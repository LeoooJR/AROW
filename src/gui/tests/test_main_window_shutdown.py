"""Managed main-window close lifecycle tests."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from gui.signals import signals
from gui.windows import MainWindow


def test_unmanaged_main_window_closes_normally(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.close()

    assert not window.isVisible()


def test_managed_shutdown_shows_overlay_and_completes(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    requests: list[str] = []

    def on_shutdown_requested() -> None:
        requests.append("requested")

    signals.UI.ApplicationShutdownRequested.connect(on_shutdown_requested)
    try:
        window.enable_managed_shutdown()
        window.show()

        window.close()
        window.close()

        assert window.isVisible()
        assert window.isEnabled()
        assert window.ui.shutdown_overlay.isVisible()
        assert window.ui.shutdown_overlay.geometry() == window.ui.app_shell.rect()
        assert (
            QApplication.widgetAt(window.ui.shutdown_overlay.mapToGlobal(QPoint(4, 4)))
            is window.ui.shutdown_overlay
        )
        assert requests == ["requested"]

        window.complete_managed_shutdown()
        assert not window.isVisible()
    finally:
        signals.UI.ApplicationShutdownRequested.disconnect(on_shutdown_requested)


def test_shutdown_overlay_forwards_wait_and_force_intents(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    waits: list[bool] = []
    forces: list[bool] = []

    def on_wait() -> None:
        waits.append(True)

    def on_force() -> None:
        forces.append(True)

    signals.UI.ApplicationShutdownWaitRequested.connect(on_wait)
    signals.UI.ApplicationForceCloseRequested.connect(on_force)
    try:
        window.show_background_shutdown_decision()
        qtbot.mouseClick(
            window.ui.shutdown_overlay.ui.shutdown_card.ui.wait_button,
            Qt.MouseButton.LeftButton,
        )
        window.show_adb_shutdown_decision()
        qtbot.mouseClick(
            window.ui.shutdown_overlay.ui.shutdown_card.ui.force_button,
            Qt.MouseButton.LeftButton,
        )

        assert waits == [True]
        assert forces == [True]
    finally:
        signals.UI.ApplicationShutdownWaitRequested.disconnect(on_wait)
        signals.UI.ApplicationForceCloseRequested.disconnect(on_force)
