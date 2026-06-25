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

    @validate_model_entrypoint
    @Slot(str)
    def _on_render_map_requested(self, simulation_id: str) -> None:
        """Submit map rendering to a worker process."""
        logger.debug(
            "MapSubController: render map requested",
            simulation_id=simulation_id,
        )
        application_dir = self.model_entrypoint.application_dir
        simulation = self.model_entrypoint.get_simulation(simulation_id)
        if simulation is None:
            logger.warning(
                "MapSubController: simulation not found",
                simulation_id=simulation_id,
            )
            return
        # Check if map already exists, if so, lazy load it
        html_path = simulation.map_file
        if html_path is not None and html_path.exists():
            logger.debug(
                "MapSubController: map already rendered",
                simulation_id=simulation_id,
            )
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
