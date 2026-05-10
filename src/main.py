import sys
from typing import Annotated

import typer
from PySide6 import QtWidgets

from __init__ import __application__, __version__
from logger import setup_logger

setup_logger()

from controller.app_controller import AppController
from core.models import CoreRuntimeModel
from gui.window import MainWindow

app = typer.Typer()


@app.command()
def main(
    interface_only: Annotated[
        bool,
        typer.Option(
            help="Only start the interface, no controller and model, useful for debugging."
        ),
    ] = False,
) -> None:
    """Start the application."""

    qt_application = QtWidgets.QApplication([])

    qt_application.setApplicationName(__application__)

    qt_application.setDesktopFileName(__application__)

    qt_application.setApplicationVersion(__version__)

    main_window = MainWindow(ui_constraints_disabled=interface_only)

    if not interface_only:

        simulation_model: CoreRuntimeModel = CoreRuntimeModel()

        app_controller: AppController = AppController(
            model=simulation_model, view=main_window
        )

    main_window.show()

    exit_code: int = qt_application.exec()

    sys.exit(exit_code)


if __name__ == "__main__":

    app()

    main()
