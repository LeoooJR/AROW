"""
Map-oriented orchestration (Folium / geo / location UI) — extension point.

Wiring for map-related view and model signals can be added here; heavy work
stays in core and is submitted through AppController's async API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

from controller.domains.app_sub_controller import AppSubController
from gui.signals import signals

if TYPE_CHECKING:
    from controller.orchestration.app_controller import AppController


class MapSubController(AppSubController):
    """Subcontroller for map flows; does not own an AsyncRunner."""

    def __init__(self, app: AppController) -> None:
        super().__init__(app)

    def connect_view_signals(self) -> None:
        """Connect map-relevant :data:`gui.signals.signals` when map UI is ready."""
        signals.UI.RenderMapRequested.connect(self._on_render_map_requested)

    def connect_model_signals(self) -> None:
        """Subscribe to map-relevant :class:`CoreSignal` values when needed."""
        return

    @Slot(str)
    def _on_render_map_requested(self, simulation_id: str) -> None:
        """Render the map."""
        self.model_entrypoint.render_map(simulation_id)
