"""Tests for typed application page routing."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtWidgets import QWidget

from gui.constants.icons import GenericIcons
from gui.routing import PageRoute, PageRouter


def _register_pages(router: PageRouter) -> dict[PageRoute, QWidget]:
    pages = {route: QWidget() for route in PageRoute}
    router.register(
        PageRoute.WELCOME,
        pages[PageRoute.WELCOME],
        title="Welcome",
        icon=GenericIcons.HAND_RAISED,
    )
    router.register(
        PageRoute.MAP,
        pages[PageRoute.MAP],
        title="Map",
        icon=GenericIcons.MAP,
    )
    router.register(
        PageRoute.DEVICE,
        pages[PageRoute.DEVICE],
        title="Device",
        icon=GenericIcons.DEVICE,
        visible=False,
    )
    return pages


def test_router_registers_named_pages_and_preserves_visibility(qtbot) -> None:
    router = PageRouter()
    qtbot.addWidget(router)

    pages = _register_pages(router)

    assert router.current_route is PageRoute.WELCOME
    assert router.page(PageRoute.MAP) is pages[PageRoute.MAP]
    assert router.is_route_visible(PageRoute.WELCOME) is True
    assert router.is_route_visible(PageRoute.DEVICE) is False


def test_router_navigates_by_route_and_emits_route_change(qtbot) -> None:
    router = PageRouter()
    qtbot.addWidget(router)
    _register_pages(router)

    with qtbot.waitSignal(router.route_changed) as blocker:
        router.navigate(PageRoute.MAP)

    assert blocker.args == [PageRoute.MAP]
    assert router.current_route is PageRoute.MAP


def test_router_rejects_duplicate_and_unknown_routes(qtbot) -> None:
    router = PageRouter()
    qtbot.addWidget(router)
    _register_pages(router)

    with pytest.raises(ValueError, match="already registered"):
        router.register(
            PageRoute.MAP,
            QWidget(),
            title="Map again",
            icon=GenericIcons.MAP,
        )

    with pytest.raises(KeyError, match="Unknown page route"):
        router.navigate(cast(PageRoute, "missing"))


def test_router_can_show_a_hidden_route(qtbot) -> None:
    router = PageRouter()
    qtbot.addWidget(router)
    _register_pages(router)

    router.set_route_visible(PageRoute.DEVICE, True)

    assert router.is_route_visible(PageRoute.DEVICE) is True
