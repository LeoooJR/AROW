"""Shared helpers for styled GUI screenshot tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QVBoxLayout, QWidget

import gui.ressources_rc  # noqa: F401 — register Qt resources for icon pixmaps
from gui.colors import Theme, set_current_theme
from gui.fonts import register_bundled_fonts
from gui.settings import Settings
from gui.stylesheet import stylesheet_dark, stylesheet_light

_SCREENSHOT_ENV = "AROW_GUI_SCREENSHOT_DIR"
_FONTS_REGISTERED = False


def ensure_screenshot_test_environment() -> None:
    """Register bundled fonts once before styled screenshot capture."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    register_bundled_fonts()
    _FONTS_REGISTERED = True


def screenshot_output_dir(tmp_path: Path) -> Path:
    """Return persistent screenshot dir from env or pytest tmp_path."""
    output_dir = os.environ.get(_SCREENSHOT_ENV)
    if output_dir:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return tmp_path


def screenshot_output_path(tmp_path: Path, filename: str) -> Path:
    """Return a stable screenshot path, removing any previous artifact first."""
    path = screenshot_output_dir(tmp_path) / filename
    if path.exists():
        path.unlink()
    return path


def stylesheet_for_theme(theme: Theme) -> str:
    """Return the explicit stylesheet variant for deterministic screenshots."""
    return stylesheet_light if theme == "light" else stylesheet_dark


def apply_stylesheet(widget: QWidget, theme: Theme = "light") -> None:
    """Apply production stylesheet tokens to a widget subtree."""
    ensure_screenshot_test_environment()
    set_current_theme(theme)
    widget.setStyleSheet(stylesheet_for_theme(theme))
    widget.setFont(QFont(Settings.FONT.FAMILY))


def create_styled_root(
    theme: Theme = "light",
    *,
    width: int | None = None,
    height: int | None = None,
) -> QWidget:
    """Create a styled root widget for isolated component screenshots."""
    root = QWidget()
    root.setObjectName("screenshot-root")
    apply_stylesheet(root, theme)
    if width is not None and height is not None:
        root.resize(width, height)
    return root


def save_pixmap(pixmap: QPixmap, path: Path) -> None:
    """Save a pixmap to disk, overwriting any existing file."""
    if path.exists():
        path.unlink()
    saved = pixmap.save(str(path))
    assert saved is True, f"Failed to save screenshot: {path}"
    assert path.exists(), f"Screenshot file missing after save: {path}"


def capture_styled_widget_screenshot(
    qtbot,
    widget: QWidget,
    *,
    tmp_path: Path,
    filename: str,
    theme: Theme = "light",
    width: int | None = None,
    height: int | None = None,
    margins: tuple[int, int, int, int] = (24, 24, 24, 24),
    grab_target: QWidget | None = None,
    grab_root: bool = False,
    prepare: Callable[[QWidget], None] | None = None,
) -> Path:
    """Show a widget under a styled root and save an offscreen screenshot."""
    root = create_styled_root(theme, width=width, height=height)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(*margins)
    layout.addWidget(widget)
    qtbot.addWidget(root)
    root.show()
    if width is not None and height is not None:
        qtbot.waitExposed(root)
    else:
        root.adjustSize()
        qtbot.wait(0)
    if prepare is not None:
        prepare(widget)
        qtbot.wait(0)

    target = root if grab_root else (grab_target or widget)
    pixmap = target.grab()
    assert pixmap.isNull() is False
    assert pixmap.width() > 0
    assert pixmap.height() > 0

    output_path = screenshot_output_path(tmp_path, filename)
    save_pixmap(pixmap, output_path)
    root.hide()
    root.close()
    qtbot.wait(0)
    return output_path


def capture_styled_top_level_screenshot(
    qtbot,
    widget: QWidget,
    *,
    tmp_path: Path,
    filename: str,
    theme: Theme = "light",
    prepare: Callable[[QWidget], None] | None = None,
) -> Path:
    """Show a top-level widget with production stylesheet and save a screenshot."""
    apply_stylesheet(widget, theme)
    if prepare is not None:
        prepare(widget)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    pixmap = widget.grab()
    assert pixmap.isNull() is False
    assert pixmap.width() > 0
    assert pixmap.height() > 0

    output_path = screenshot_output_path(tmp_path, filename)
    save_pixmap(pixmap, output_path)
    widget.hide()
    widget.close()
    qtbot.wait(0)
    return output_path
