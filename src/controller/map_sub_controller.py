"""
Map-oriented orchestration (Folium / geo / location UI) — extension point.

Wiring for map-related view and model signals can be added here; heavy work
stays in core and is submitted through AppController's async API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controller.app_controller import AppController


class MapSubController:
    """Subcontroller for map flows; does not own an AsyncRunner."""

    def __init__(self, app: AppController) -> None:
        self._app = app

    def connect_view_signals(self) -> None:
        """Connect map-relevant :data:`app_signals` when map UI is ready."""
        return

    def connect_model_signals(self) -> None:
        """Subscribe to map-relevant :class:`CoreSignal` values when needed."""
        return
