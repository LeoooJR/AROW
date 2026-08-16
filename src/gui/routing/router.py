"""Typed Qt tab router for application pages."""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QTabWidget, QWidget

from gui.constants.colors import Theme
from gui.constants.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.routing.routes import PageRoute

PageIcon = GenericIcons | OperatingSystemIcons | ApplicationIcons


class PageRouter(QTabWidget):
    """Map stable route identifiers to tab-backed Qt pages."""

    route_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._route_indexes: dict[PageRoute, int] = {}
        self._index_routes: dict[int, PageRoute] = {}
        self._route_icons: dict[PageRoute, PageIcon] = {}
        self.currentChanged.connect(self._on_current_changed)

    def register(
        self,
        route: PageRoute,
        page: QWidget,
        *,
        title: str,
        icon: PageIcon,
        visible: bool = True,
    ) -> None:
        """Register one page and its tab metadata for ``route``."""
        if route in self._route_indexes:
            raise ValueError(f"Route is already registered: {route}")

        index = self.count()
        self._route_indexes[route] = index
        self._index_routes[index] = route
        self._route_icons[route] = icon
        self.addTab(page, QIcon(icon_qt_path(icon)), title)
        self.setTabVisible(index, visible)

    def navigate(self, route: PageRoute) -> None:
        """Display the page registered for ``route``."""
        self.setCurrentIndex(self._index_for(route))

    @property
    def current_route(self) -> PageRoute | None:
        """Return the active route, or ``None`` before any page is registered."""
        return self._index_routes.get(self.currentIndex())

    def page(self, route: PageRoute) -> QWidget:
        """Return the widget registered for ``route``."""
        page = self.widget(self._index_for(route))
        if page is None:  # pragma: no cover - guarded by the registration mapping
            raise RuntimeError(f"Registered route has no page: {route}")
        return page

    def set_route_visible(self, route: PageRoute, visible: bool) -> None:
        """Set whether ``route`` appears in the tab bar."""
        self.setTabVisible(self._index_for(route), visible)

    def is_route_visible(self, route: PageRoute) -> bool:
        """Return whether ``route`` appears in the tab bar."""
        return self.isTabVisible(self._index_for(route))

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh every registered route icon for ``theme``."""
        for route, icon in self._route_icons.items():
            self.setTabIcon(
                self._index_for(route), QIcon(icon_qt_path_for_theme(theme, icon))
            )

    def _index_for(self, route: PageRoute) -> int:
        try:
            return self._route_indexes[route]
        except KeyError as error:
            raise KeyError(f"Unknown page route: {route}") from error

    @Slot(int)
    def _on_current_changed(self, index: int) -> None:
        route = self._index_routes.get(index)
        if route is not None:
            self.route_changed.emit(route)
