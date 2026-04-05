import sys

from PySide6 import QtWidgets

from __init__ import __application__, __version__
from gui.window import MainWindow

if __name__ == "__main__":

    application = QtWidgets.QApplication([])

    application.setApplicationName(__application__)

    application.setDesktopFileName(__application__)

    application.setApplicationVersion(__version__)

    main_window = MainWindow()

    main_window.show()

    exit_code: int = application.exec()

    sys.exit(exit_code)
