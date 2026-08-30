"""Managed main-window close lifecycle tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from gui.signals import signals
from gui.windows import MainWindow


def test_unmanaged_main_window_closes_normally(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.close()

    assert not window.isVisible()


def test_managed_shutdown_can_abort_retry_and_complete(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    window.ui.app_shell.post_toast = MagicMock()  # type: ignore[method-assign]
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
        assert not window.isEnabled()
        assert requests == ["requested"]

        window.abort_managed_shutdown("jobs are still active")

        assert window.isEnabled()
        window.ui.app_shell.post_toast.assert_called_once_with(
            "Application shutdown was cancelled: jobs are still active.",
            level="error",
        )

        window.close()
        assert requests == ["requested", "requested"]
        assert window.isVisible()

        window.complete_managed_shutdown()
        assert not window.isVisible()
    finally:
        signals.UI.ApplicationShutdownRequested.disconnect(on_shutdown_requested)
