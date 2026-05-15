"""
Bundled UI fonts: register with Qt after :class:`~PySide6.QtWidgets.QApplication` exists.

:class:`~PySide6.QtGui.QFontDatabase.addApplicationFont` is unsafe without a GUI application
instance on some platforms; keep registration out of ``settings.py`` and call from startup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final

from loguru import logger
from PySide6.QtGui import QFontDatabase

_FONTS_BASE: Final[Path] = Path(__file__).resolve().parent / "statics" / "fonts"
_INTER_DIR: Path = _FONTS_BASE / "Inter"


@dataclass(frozen=True, unsafe_hash=True)
class VariableFont:
    """Font used in the application.

    Args:
        name: The name of the font.
        path: The path to the font file.
    """

    name: Final[str] = field(
        default="Inter", metadata={"description": "The name of the font."}
    )
    path: Final[Path] = field(
        default=_INTER_DIR / "Inter-VariableFont_opsz,wght.ttf",
        hash=True,
        metadata={"description": "The path to the font file (.ttf or .otf)."},
    )

    def __post_init__(self):
        if not self.path.is_file():
            raise FileNotFoundError(f"Font file {self.path} not found.")


class VariableFonts(Enum):
    """Fonts used in the application."""

    INTER = VariableFont(
        name="Inter", path=_INTER_DIR / "Inter-VariableFont_opsz,wght.ttf"
    )
    INTER_ITALIC = VariableFont(
        name="Inter Italic", path=_INTER_DIR / "Inter-Italic-VariableFont_opsz,wght.ttf"
    )


@dataclass(frozen=True)
class StaticFonts:
    """Bundled static ``.ttf`` directories under ``statics/fonts`` (per-family ``<family>/static``)."""

    directories: tuple[Path, ...]

    @classmethod
    def discover(cls, base: Path | None = None) -> StaticFonts:
        """Collect ``family/static`` directories under the bundled fonts root."""
        root = base if base is not None else _FONTS_BASE
        dirs: list[Path] = []
        if root.is_dir():
            for family_dir in sorted(root.iterdir()):
                static_sub = family_dir / "static"
                if static_sub.is_dir():
                    dirs.append(static_sub)
        return cls(directories=tuple(dirs))

    def iter_ttf_paths(self) -> list[Path]:
        """All bundled static ``.ttf`` paths in deterministic order."""
        paths: list[Path] = []
        for directory in self.directories:
            paths.extend(sorted(directory.glob("*.ttf")))
        return sorted(paths)


def register_bundled_fonts() -> None:
    """Load bundled variable fonts into Qt when present; otherwise register static cuts."""

    nb_font_bundled = 0
    nb_font_refused = 0

    try:
        # Prefer variable fonts (fewer files, full weight axis); fall back to static cuts if missing.
        for font in VariableFonts:
            font_id = QFontDatabase.addApplicationFont(str(font.value.path))
            if font_id >= 0:
                nb_font_bundled += 1
            else:
                nb_font_refused += 1
                logger.warning("Qt refused bundled font file {}", font.value.path)
        if nb_font_bundled == 0:
            logger.warning("No bundled variable fonts loaded under {}", _FONTS_BASE)
            return
        if nb_font_refused > 0:
            logger.warning(
                "Qt refused {} bundled variable font file(s)", nb_font_refused
            )
        logger.debug("Registered {} bundled variable font file(s)", nb_font_bundled)
    except FileNotFoundError as e:
        logger.warning("Variable font file not found: {}", e)
        static_fonts = StaticFonts.discover()
        static_font_paths = static_fonts.iter_ttf_paths()
        if not static_font_paths:
            logger.warning("No bundled static fonts found under {}", _FONTS_BASE)
            return
        nb_font_bundled = 0
        nb_font_refused = 0
        for font_path in static_font_paths:
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id >= 0:
                nb_font_bundled += 1
            else:
                nb_font_refused += 1
                logger.warning("Qt refused bundled font file {}", font_path)
        if nb_font_bundled == 0:
            logger.warning(
                "Bundled static fonts present but none loaded under {}", _FONTS_BASE
            )
            return
        if nb_font_refused > 0:
            logger.warning("Qt refused {} bundled static font file(s)", nb_font_refused)
        logger.debug(
            "Registered {} bundled static font file(s) from directories {}",
            nb_font_bundled,
            static_fonts.directories,
        )
