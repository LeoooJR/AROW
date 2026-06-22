"""
Map-oriented orchestration (Folium / geo / location UI).

Heavy map rendering runs in a worker process via AsyncRunner; completion is
applied on the main thread and forwarded to the view.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

from controller.core_work_callbacks import MapAsyncJobCallbacks, RenderMapCallback
from controller.domains.app_sub_controller import AppSubController
from controller.helper import validate_model_entrypoint, validate_view
from core.signals import (
    CoreSignal,
    MapRenderedPayload,
    MapRenderFailedPayload,
)
from gui.signals import signals
from logger import logger

if TYPE_CHECKING:
    from controller.orchestration.app_controller import AppController


class MapSubController(AppSubController):
    """Subcontroller for map flows; does not own an AsyncRunner."""

    def __init__(self, app: AppController) -> None:
        super().__init__(app)
        self._async_job_callbacks: MapAsyncJobCallbacks = (
            MapAsyncJobCallbacks.for_subcontroller(self)
        )

    def _submit_model_entrypoint_async_call(self, *args, **kwargs):
        return self._app._submit_model_entrypoint_async_call(*args, **kwargs)

    def connect_view_signals(self) -> None:
        """Connect map-relevant :data:`gui.signals.signals` when map UI is ready."""
        signals.UI.RenderMapRequested.connect(self._on_render_map_requested)

    def connect_model_signals(self) -> None:
        """Subscribe to map-relevant :class:`CoreSignal` values when needed."""
        self.model_entrypoint.subscribe(CoreSignal.MAP_RENDERED, self._on_map_rendered)
        self.model_entrypoint.subscribe(
            CoreSignal.MAP_RENDER_FAILED, self._on_map_render_failed
        )

    @validate_model_entrypoint
    @Slot(str)
    def _on_render_map_requested(self, simulation_id: str) -> None:
        """Submit map rendering to a worker process."""
        logger.debug(
            "MapSubController: render map requested",
            simulation_id=simulation_id,
        )
        callback: RenderMapCallback = self._async_job_callbacks.render_map
        application_dir = self.model_entrypoint.application_dir
        # Check if map already exists, if so, lazy load it
        html_path = (
            application_dir
            / "simulations"
            / simulation_id
            / "map"
            / f"{simulation_id}.html"
        )
        if html_path.exists():
            logger.debug(
                "MapSubController: map already rendered",
                simulation_id=simulation_id,
            )
            self.view.forward_map_rendered(
                simulation_id,
                application_dir
                / "simulations"
                / simulation_id
                / "map"
                / f"{simulation_id}.html",
            )
        else:
            self._submit_model_entrypoint_async_call(
                name="render_map",
                fn=self.model_entrypoint.render_map,
                args=(simulation_id, application_dir),
                description="Render Folium map HTML for simulation",
                job_type="process",
                coalesce_key=f"render_map:{simulation_id}",
                on_completed=callback.on_completed,
                on_failed=callback.on_failed,
            )

    @validate_view
    def _on_map_rendered(self, payload: MapRenderedPayload) -> None:
        logger.info(
            "MapSubController: map rendered",
            simulation_id=payload.simulation_id,
            html_path=str(payload.html_path),
        )
        self.view.forward_map_rendered(
            payload.simulation_id,
            payload.html_path,
        )

    @validate_view
    def _on_map_render_failed(self, payload: MapRenderFailedPayload) -> None:
        logger.warning(
            "MapSubController: map render failed",
            simulation_id=payload.simulation_id,
            reason=payload.reason,
        )
        self.view.forward_map_render_failed(payload.simulation_id, payload.reason)
