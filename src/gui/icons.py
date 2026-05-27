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


def _create_icon(filename: str, *, has_both_themes: bool = True) -> Icon:
    """Build an Icon with references to light and dark theme asset files.

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

    LOCATION = _create_icon("location.svg")
    FAKE_LOCATION = _create_icon("fake-location.svg")
    CROSSHAIR = _create_icon("crosshair.svg")
    MILESTONE = _create_icon("milestone.svg")
    RAILWAY = _create_icon("railway.svg")
    MAP = _create_icon("globe-central-south-asia.svg")
    MAP_PLACEHOLDER = _create_icon("globe-central-south-asia-placeholder.svg")
    GEO = _create_icon("geo-fill.svg")
    LAPTOP = _create_icon("laptop.svg")
    DEVICE = _create_icon("phone.svg")
    DEVICE_PLACEHOLDER = _create_icon("device-placeholder.svg")
    ARROW_CLOCKWISE = _create_icon("arrow-clockwise.svg")
    LOGS = _create_icon("substack.svg")
    UPLOAD = _create_icon("upload.svg")
    START = _create_icon("start.svg")
    OFF = _create_icon("off.svg")
    ON = _create_icon("on.svg")
    PLAY = _create_icon("play-circle.svg")
    PAUSE = _create_icon("pause-circle.svg")
    LAYOUT_SIDEBAR = _create_icon("layout-sidebar.svg")
    LAYOUT_SIDEBAR_REVERSE = _create_icon("layout-sidebar-reverse.svg")
    LAYOUT_SIDEBAR_INSET = _create_icon("layout-sidebar-inset.svg")
    LAYOUT_SIDEBAR_INSET_REVERSE = _create_icon("layout-sidebar-inset-reverse.svg")
    LAYOUT_TOPBAR = _create_icon("layout-topbar.svg")
    LAYOUT_TOPBAR_INSET = _create_icon("layout-topbar-inset.svg")
    LAYOUT_BOTTOMBAR = _create_icon("layout-bottombar.svg")
    LAYOUT_BOTTOMBAR_INSET = _create_icon("layout-bottombar-inset.svg")
    LIGHT_MODE = _create_icon("brightness-high.svg")
    DARK_MODE = _create_icon("moon.svg")
    FILE = _create_icon("file-earmark-text.svg")
    FUNNEL = _create_icon("funnel.svg")
    INFO = _create_icon("info-circle.svg")
    CHECK = _create_icon("check-circle.svg")
    EXCLAMATION = _create_icon("exclamation-circle.svg")
    X_CIRCLE = _create_icon("x-circle.svg")
    HAND_INDEX = _create_icon("hand-index.svg")
    SAVE_AS = _create_icon("save-as.svg")
    WIFI = _create_icon("wifi.svg")
    USB = _create_icon("usb.svg")
    PLUS = _create_icon("plus.svg")
    X = _create_icon("x.svg")
    TRASH = _create_icon("trash.svg")
    HAND_RAISED = _create_icon("person-raised-hand.svg")


class OperatingSystemIcons(Enum):
    """Icons that are used to represent operating systems."""

    ANDROID = _create_icon("android-icon.svg")
    MACOS = _create_icon("apple.svg")
    WINDOWS = _create_icon("windows.svg")
    LINUX = _create_icon("linux.svg")


class ApplicationIcons(Enum):
    """Icons that are used to represent the application."""

    LOGO = _create_icon("logo.png", has_both_themes=False)
    LOGO_UI = _create_icon("logo-ui.png", has_both_themes=False)
    NAME = _create_icon("app-name.svg")
