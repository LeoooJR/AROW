"""
Bundled UI fonts: register with Qt after :class:`~PySide6.QtWidgets.QApplication` exists.

:class:`~PySide6.QtGui.QFontDatabase.addApplicationFont` is unsafe without a GUI application
instance on some platforms; keep registration out of ``settings.py`` and call from startup.

When registering a new bundled font:
1. Add font files under ``src/gui/statics/fonts/<family>/`` (variable ``.ttf`` at family root,
   or static cuts under ``<family>/static/``).
2. Add a ``VariableFonts`` enum member when the family ships a variable font file; otherwise
   rely on ``StaticFonts.discover()`` for static cuts only.
3. Update ``FontSettings`` in ``src/gui/constants/settings.py`` (``FAMILY``, ``FAMILY_CSS``, weights) when
   the new face becomes the application default.
4. Ensure startup calls ``register_bundled_fonts()`` after ``QApplication`` is created
   (see ``src/commands/run/gui.py`` and GUI test helpers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final

from loguru import logger
from PySide6.QtGui import QFontDatabase

_FONTS_BASE: Final[Path] = Path(__file__).resolve().parent.parent / "statics" / "fonts"
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
        root: Path = base if base is not None else _FONTS_BASE
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

    nb_variable_font_bundled: int = 0
    nb_variable_font_refused: int = 0

    nb_static_font_bundled: int = 0
    nb_static_font_refused: int = 0

    # Prefer variable fonts (fewer files, full weight axis); fall back to static cuts when no variable font file is bundled at all.
    variable_font_paths: list[Path] = [
        font.value.path for font in VariableFonts if font.value.path.is_file()
    ]

    if variable_font_paths:
        for variable_font_path in variable_font_paths:
            variable_font_id = QFontDatabase.addApplicationFont(str(variable_font_path))
            if variable_font_id >= 0:
                nb_variable_font_bundled += 1
                logger.debug(
                    "Bundled variable font registered", path=str(variable_font_path)
                )
            else:
                nb_variable_font_refused += 1
                logger.debug(
                    "Bundled variable font refused by Qt",
                    path=str(variable_font_path),
                )

    if nb_variable_font_bundled == 0:
        logger.warning(
            "Bundled variable fonts unavailable; falling back to static fonts",
            path=str(_FONTS_BASE),
            discovered_count=len(variable_font_paths),
            refused_count=nb_variable_font_refused,
        )
    else:
        logger.debug(
            "Bundled variable fonts registered",
            registered_count=nb_variable_font_bundled,
            refused_count=nb_variable_font_refused,
        )
        if nb_variable_font_refused > 0:
            logger.warning(
                "Some bundled variable fonts were refused by Qt",
                refused_count=nb_variable_font_refused,
            )
        return

    # If no variable fonts are bundled, fallback to static fonts.
    static_fonts: StaticFonts = StaticFonts.discover()
    static_font_paths: list[Path] = static_fonts.iter_ttf_paths()

    if not static_font_paths:
        logger.warning(
            "Bundled static font fallback is unavailable",
            path=str(_FONTS_BASE),
        )
        return

    for static_font_path in static_font_paths:
        static_font_id = QFontDatabase.addApplicationFont(str(static_font_path))
        if static_font_id >= 0:
            nb_static_font_bundled += 1
            logger.debug(
                "Bundled static font registered",
                path=str(static_font_path),
            )
        else:
            nb_static_font_refused += 1
            logger.debug(
                "Bundled static font refused by Qt",
                path=str(static_font_path),
            )

    if nb_static_font_bundled == 0:
        logger.warning(
            "Bundled static fonts could not be registered",
            path=str(_FONTS_BASE),
            refused_count=nb_static_font_refused,
        )
    else:
        logger.debug(
            "Bundled static fonts registered",
            registered_count=nb_static_font_bundled,
            refused_count=nb_static_font_refused,
        )
        if nb_static_font_refused > 0:
            logger.warning(
                "Some bundled static fonts were refused by Qt",
                refused_count=nb_static_font_refused,
            )
    return
