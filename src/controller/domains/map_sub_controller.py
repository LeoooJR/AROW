"""
Map-oriented orchestration (Folium / geo / location UI).

Heavy map rendering runs in a worker process via AsyncRunner; completion is
applied on the main thread and forwarded to the view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

from controller.core_work_callbacks import (
    MapAsyncJobCallbacks,
    RenderMapSimulationCallback,
)
from controller.domains.app_sub_controller import AppSubController
from controller.helper import validate_model_entrypoint, validate_view
from controller.runner import JobHandler
from core.signals import (
    CoreSignal,
    MapRenderedPayload,
    MapRenderFailedPayload,
    SimulationDeletedPayload,
    SimulationLocationRejectedPayload,
    SimulationLocationValidatedPayload,
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
        self._render_jobs_by_simulation_id: dict[str, JobHandler] = (
            {}
        )  # Mapping of simulation to job handler
        # Keep per-job callback objects alive until AsyncRunner emits completion.
        self._render_callbacks_by_simulation_id: dict[
            str, RenderMapSimulationCallback
        ] = {}

    def _submit_model_entrypoint_async_call(self, *args, **kwargs):
        return self._app._submit_model_entrypoint_async_call(*args, **kwargs)

    def connect_view_signals(self) -> None:
        """Connect map-relevant :data:`gui.signals.signals` when map UI is ready."""
        signals.UI.RenderMapRequested.connect(self._on_render_map_requested)
        signals.SIMULATION.SimulationLocationRequested.connect(
            self._on_simulation_location_requested
        )

    def persist_simulation_repository(self) -> None:
        """Persist map-aware simulation metadata at shutdown."""
        self.model_entrypoint.persist_simulations()

    def connect_model_signals(self) -> None:
        """Subscribe to map-relevant :class:`CoreSignal` values when needed."""
        self.model_entrypoint.subscribe(CoreSignal.MAP_RENDERED, self._on_map_rendered)
        self.model_entrypoint.subscribe(
            CoreSignal.MAP_RENDER_FAILED, self._on_map_render_failed
        )
        self.model_entrypoint.subscribe(
            CoreSignal.SIMULATION_DELETED,
            self._on_simulation_deleted,
        )
        self.model_entrypoint.subscribe(
            CoreSignal.SIMULATION_LOCATION_VALIDATED,
            self._on_simulation_location_validated,
        )
        self.model_entrypoint.subscribe(
            CoreSignal.SIMULATION_LOCATION_REJECTED,
            self._on_simulation_location_rejected,
        )

    @validate_model_entrypoint
    @Slot(str)
    def _on_render_map_requested(self, simulation_id: str) -> None:
        """Submit map rendering to a worker process."""
        logger.debug(
            "MapSubController: render map requested",
            simulation_id=simulation_id,
        )
        if self.model_entrypoint.get_simulation(simulation_id) is None:
            logger.error(
                "MapSubController: simulation not found",
                simulation_id=simulation_id,
            )
            return
        if self.model_entrypoint.is_map_rendered_for_simulation(simulation_id):
            html_path = self.model_entrypoint.get_map_file_for_simulation(simulation_id)
            if html_path is None:
                logger.error(
                    "MapSubController: map file not found",
                    simulation_id=simulation_id,
                )
                return
            self.view.forward_map_rendered(
                simulation_id,
                html_path,
            )
        else:
            render_callbacks = self._async_job_callbacks.render_map_for_simulation(
                simulation_id
            )
            self._render_callbacks_by_simulation_id[simulation_id] = render_callbacks
            if render_callbacks is None:
                logger.error(
                    "MapSubController: render_map_for_simulation is not set",
                    simulation_id=simulation_id,
                )
                return
            application_dir = self.model_entrypoint.application_dir
            handle = self._submit_model_entrypoint_async_call(
                name="render_map",
                fn=self.model_entrypoint.render_map,
                args=(simulation_id, application_dir),
                description="Render Folium map HTML for simulation",
                job_type="process",
                coalesce_key=f"render_map:{simulation_id}",
                on_completed=render_callbacks.on_completed,
                on_failed=render_callbacks.on_failed,
                on_cancelled=render_callbacks.on_cancelled,
            )
            if handle is not None:
                render_callbacks.bind_job(handle)
                self._render_jobs_by_simulation_id[simulation_id] = handle

    @validate_model_entrypoint
    @Slot(str, str, str, float, float)
    def _on_simulation_location_requested(
        self,
        simulation_id: str,
        marker_id: str,
        code_line: str,
        latitude: float,
        longitude: float,
    ) -> None:
        """Validate a map milestone selection for the given simulation."""
        logger.debug(
            "MapSubController: simulation location requested",
            simulation_id=simulation_id,
            marker_id=marker_id,
            latitude=latitude,
            longitude=longitude,
        )
        self.model_entrypoint.validate_simulation_marker_location(
            simulation_id,
            marker_id,
            code_line,
            latitude,
            longitude,
        )

    @validate_view
    def _on_simulation_location_validated(
        self, payload: SimulationLocationValidatedPayload
    ) -> None:
        """Forward validated simulation location to the map view."""
        poi = payload.poi
        line = poi.get("line")
        code_line = ""
        if isinstance(line, dict):
            code_line = str(line.get("code", ""))
        logger.debug(
            "MapSubController: simulation location validated",
            simulation_id=payload.simulation_id,
            id=poi.get("id"),
            code_line=code_line,
            type=poi.get("type"),
            lat=payload.lat,
            lon=payload.lon,
        )
        self.view.forward_simulation_location_validated(
            simulation_id=payload.simulation_id,
            marker_id=str(poi.get("id", "")),
            code_line=code_line,
            lat=payload.lat,
            lon=payload.lon,
            label=str(poi.get("label", "")),
        )

    @validate_view
    def _on_simulation_location_rejected(
        self, payload: SimulationLocationRejectedPayload
    ) -> None:
        logger.warning(
            "MapSubController: simulation location rejected",
            simulation_id=payload.simulation_id,
            id=payload.id,
            code_line=payload.code_line,
            lat=payload.lat,
            lon=payload.lon,
            reason=payload.reason,
        )
        self.view.forward_simulation_location_rejected(
            simulation_id=payload.simulation_id,
            marker_id=payload.id,
            code_line=payload.code_line or "",
            lat=payload.lat,
            lon=payload.lon,
            reason=payload.reason,
        )

    def _clear_render_job_if_current(
        self, simulation_id: str, job_id: str | None
    ) -> None:
        """Remove a tracked render job only when it still matches the given job id."""
        handle = self._render_jobs_by_simulation_id.get(simulation_id)
        if handle is None or job_id is None or handle.job_id != job_id:
            return
        self._render_jobs_by_simulation_id.pop(simulation_id, None)
        self._render_callbacks_by_simulation_id.pop(simulation_id, None)

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

    @validate_view
    def _on_simulation_deleted(self, payload: SimulationDeletedPayload) -> None:
        simulation_id = payload.simulation_id
        handle = self._render_jobs_by_simulation_id.pop(simulation_id, None)
        self._render_callbacks_by_simulation_id.pop(simulation_id, None)
        if handle is not None:
            logger.debug(
                "MapSubController: cancelling in-flight render map job",
                simulation_id=simulation_id,
                job_id=handle.job_id,
            )
            self._app.runner.cancel(handle.job_id)
        self.view.forward_simulation_deleted(simulation_id)
