import locale
import sys
from typing import Annotated

import typer
from PySide6 import QtWidgets

from __init__ import __application__, __version__
from logger import setup_logger

try:
    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
except locale.Error:
    # Locale setting failed (not available on this machine); fallback to default locale.
    pass

setup_logger()

app = typer.Typer()


@app.command()
def main(
    interface_only: Annotated[
        bool,
        typer.Option(
            help="Only start the interface, no controller and model, useful for debugging."
        ),
    ] = False,
    mock_adb: Annotated[
        bool,
        typer.Option(help="Use faker-backed mock ADB (no real adb daemon or binary)."),
    ] = False,
) -> None:
    """Start the application."""

    qt_application = QtWidgets.QApplication.instance()
    if qt_application is None:
        qt_application = QtWidgets.QApplication([])

    qt_application.setApplicationName(__application__)

    qt_application.setDesktopFileName(__application__)

    qt_application.setApplicationVersion(__version__)

    # Bundled fonts need Qt GUI app + registration before stylesheet (imported with MainWindow).
    from gui.fonts import register_bundled_fonts

    register_bundled_fonts()

    from gui.window import MainWindow

    main_window = MainWindow(ui_constraints_disabled=interface_only)

    if not interface_only:

        from controller import AppController
        from core.models import CoreRuntimeModel

        simulation_model: CoreRuntimeModel = CoreRuntimeModel(use_mock_adb=mock_adb)

        app_controller: AppController = AppController(
            model=simulation_model, view=main_window
        )

    main_window.show()

    exit_code: int = qt_application.exec()

    sys.exit(exit_code)


if __name__ == "__main__":
    app()
