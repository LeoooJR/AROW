"""
Bundled UI fonts: register with Qt after :class:`~PySide6.QtWidgets.QApplication` exists.

:class:`~PySide6.QtGui.QFontDatabase.addApplicationFont` is unsafe without a GUI application
instance on some platforms; keep registration out of ``settings.py`` and call from startup.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtGui import QFontDatabase

_INTER_DIR: Path = Path(__file__).resolve().parent / "statics" / "fonts" / "Inter"

# Prefer variable fonts (fewer files, full weight axis); fall back to static cuts if missing.
_VARIABLE_FILES: tuple[Path, ...] = (
    _INTER_DIR / "Inter-VariableFont_opsz,wght.ttf",
    _INTER_DIR / "Inter-Italic-VariableFont_opsz,wght.ttf",
)


def register_bundled_fonts() -> None:
    """Load bundled Inter fonts into Qt's application font database."""
    paths: list[Path] = []
    for candidate in _VARIABLE_FILES:
        if candidate.is_file():
            paths.append(candidate)

    static_dir = _INTER_DIR / "static"
    if not paths and static_dir.is_dir():
        paths.extend(sorted(static_dir.glob("*.ttf")))

    if not paths:
        logger.warning("Bundled Inter fonts missing under {}", _INTER_DIR)
        return

    ok = 0
    for path in paths:
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            ok += 1
        else:
            logger.warning("Qt refused bundled font file {}", path)

    if ok:
        logger.debug(
            "Registered {} bundled Inter font file(s) from {}",
            ok,
            _INTER_DIR,
        )
