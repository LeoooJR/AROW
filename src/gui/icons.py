from dataclasses import dataclass
from enum import Enum

from gui.colors import Theme, get_current_theme


@dataclass(frozen=True)
class Icon:
    """Single GUI icon with Qt resource paths per theme."""

    name: str
    light_mode_path: str
    dark_mode_path: str

    def for_theme(self, theme: Theme) -> str:
        return self.light_mode_path if theme == "light" else self.dark_mode_path


def _pair(filename: str, *, has_both_themes: bool = True) -> Icon:
    """Build an Icon that uses identical Qt paths for light and dark until dark assets exist.

    SVG icons live under ``statics/light/<filename>``. Files that remain at ``statics/<filename>``
    (for example raster logos) pass ``has_both_themes=False``.
    """
    if has_both_themes:
        qt_paths: tuple[str, str] = (
            f":/statics/light/{filename}",
            f":/statics/dark/{filename}",
        )
    else:
        qt_paths: tuple[str, str] = (f":/statics/{filename}", f":/statics/{filename}")
    stem = filename.rsplit(".", 1)[0]
    return Icon(stem.replace("-", " ").title(), *qt_paths)


def icon_qt_path(
    member: "GenericIcons | OperatingSystemIcons | ApplicationIcons",
) -> str:
    """Qt resource path for the given enum member under the active UI theme."""
    return member.value.for_theme(get_current_theme())


def icon_qt_path_for_theme(
    theme: Theme,
    member: "GenericIcons | OperatingSystemIcons | ApplicationIcons",
) -> str:
    """Qt resource path for the given enum member and explicit theme."""
    return member.value.for_theme(theme)


def icons_need_theme_updates() -> bool:
    """True when at least one icon uses different assets for light vs dark theme."""
    for enum_cls in (GenericIcons, OperatingSystemIcons, ApplicationIcons):
        for m in enum_cls:
            icon = m.value
            if icon.light_mode_path != icon.dark_mode_path:
                return True
    return False


class GenericIcons(Enum):
    """Icons that are used to represent generic elements."""

    LOCATION = _pair("location.svg")
    FAKE_LOCATION = _pair("fake-location.svg")
    CROSSHAIR = _pair("crosshair.svg")
    MILESTONE = _pair("milestone.svg")
    RAILWAY = _pair("railway.svg")
    MAP = _pair("globe-central-south-asia.svg")
    MAP_PLACEHOLDER = _pair("globe-central-south-asia-placeholder.svg")
    GEO = _pair("geo-fill.svg")
    LAPTOP = _pair("laptop.svg")
    DEVICE = _pair("phone.svg")
    DEVICE_PLACEHOLDER = _pair("device-placeholder.svg")
    ARROW_CLOCKWISE = _pair("arrow-clockwise.svg")
    LOGS = _pair("substack.svg")
    UPLOAD = _pair("upload.svg")
    START = _pair("start.svg")
    OFF = _pair("off.svg")
    ON = _pair("on.svg")
    PLAY = _pair("play-circle.svg")
    PAUSE = _pair("pause-circle.svg")
    LAYOUT_SIDEBAR = _pair("layout-sidebar.svg")
    LAYOUT_SIDEBAR_REVERSE = _pair("layout-sidebar-reverse.svg")
    LAYOUT_SIDEBAR_INSET = _pair("layout-sidebar-inset.svg")
    LAYOUT_SIDEBAR_INSET_REVERSE = _pair("layout-sidebar-inset-reverse.svg")
    LAYOUT_TOPBAR = _pair("layout-topbar.svg")
    LAYOUT_TOPBAR_INSET = _pair("layout-topbar-inset.svg")
    LAYOUT_BOTTOMBAR = _pair("layout-bottombar.svg")
    LAYOUT_BOTTOMBAR_INSET = _pair("layout-bottombar-inset.svg")
    LIGHT_MODE = _pair("brightness-high.svg")
    DARK_MODE = _pair("moon.svg")
    FILE = _pair("file-earmark-text.svg")
    FUNNEL = _pair("funnel.svg")
    INFO = _pair("info-circle.svg")
    CHECK = _pair("check-circle.svg")
    EXCLAMATION = _pair("exclamation-circle.svg")
    X_CIRCLE = _pair("x-circle.svg")
    HAND_INDEX = _pair("hand-index.svg")
    SAVE_AS = _pair("save-as.svg")
    PLUS = _pair("plus.svg")
    X = _pair("x.svg")
    TRASH = _pair("trash.svg")
    HAND_RAISED = _pair("person-raised-hand.svg")


class OperatingSystemIcons(Enum):
    """Icons that are used to represent operating systems."""

    ANDROID = _pair("android-icon.svg")
    MACOS = _pair("apple.svg")
    WINDOWS = _pair("windows.svg")
    LINUX = _pair("linux.svg")


class ApplicationIcons(Enum):
    """Icons that are used to represent the application."""

    LOGO = _pair("logo.png", has_both_themes=False)
    LOGO_UI = _pair("logo-ui.png", has_both_themes=False)
    NAME = _pair("app-name.svg")
