from PySide6.QtCore import QSize

from gui.settings import Settings


def get_svg_size(font_size: int) -> QSize:
    if font_size < 20:
        multiplier = Settings.SVG.MULTIPLIER_SMALL
    else:
        multiplier = Settings.SVG.MULTIPLIER_LARGE
    size = int(multiplier * font_size)
    return QSize(size, size)
