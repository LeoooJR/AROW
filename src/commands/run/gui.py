"""Command for running the PySide6 graphical interface."""

import locale

import typer
from PySide6 import QtWidgets

from __init__ import __application__, __version__
from commands.run.options import RunOptions
from logger import setup_logger


def gui(context: typer.Context) -> None:
    """Run the application with GUI."""
    run_options = context.ensure_object(RunOptions)

    try:
        locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
    except locale.Error:
        # Locale setting failed (not available on this machine); fallback to default locale.
        pass

    setup_logger()

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

    main_window = MainWindow()

    from controller import AppController
    from core.entrypoint import ModelEntrypoint

    model_entrypoint: ModelEntrypoint = ModelEntrypoint(
        use_mock_adb=run_options.mock_adb
    )

    _app_controller: AppController = AppController(
        model_entrypoint=model_entrypoint, view=main_window
    )

    main_window.show()

    exit_code: int = qt_application.exec()

    raise typer.Exit(exit_code)
