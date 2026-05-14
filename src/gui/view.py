import sys

from PySide6 import QtWidgets

from __init__ import __application__, __version__
from gui.window import MainWindow

if __name__ == "__main__":

    qt_application: QtWidgets.QApplication = QtWidgets.QApplication.instance()
    if qt_application is None:
        qt_application = QtWidgets.QApplication([])

    qt_application.setApplicationName(__application__)

    qt_application.setDesktopFileName(__application__)

    qt_application.setApplicationVersion(__version__)

    from gui.fonts import register_bundled_fonts

    register_bundled_fonts()

    main_window = MainWindow()

    main_window.show()

    exit_code: int = qt_application.exec()

    sys.exit(exit_code)
