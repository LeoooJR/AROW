"""
Folium / geo map HTML generation on a worker process; core-bus emit on the Qt main thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from core.entrypoint_protocol import CoreSignalEmitter, SimulationMutationEntrypoint
from core.exceptions import CoreException
from core.geo.renderer import MapRenderer
from core.signals import (
    CoreSignals,
    MapRenderedPayload,
    MapRenderFailedPayload,
)
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from logger import logger


class RenderMapError(CoreException):
    """Map rendering failed; preserves simulation id for user-facing reporting."""

    def __init__(self, *, simulation_id: str, reason: str) -> None:
        """Initialize a map-rendering failure.

        Args:
            simulation_id: Simulation whose map could not be rendered.
            reason: Human-readable failure reason.
        """
        self.simulation_id = simulation_id
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class RenderMapOutcome(CoreRuntimeWorkOutcome):
    """Result of :meth:`RenderMapWork.run` (worker process)."""

    simulation_id: str
    html_path: Path


class RenderMapWork(CoreRuntimeWork[RenderMapOutcome]):
    """
    Blocking Folium / dataset rendering on a worker process; apply emits ``MAP_RENDERED``.
    """

    def __init__(
        self,
        *,
        simulation_id: str,
        output_dir: Path,
    ) -> None:
        """Initialize map-rendering work.

        Args:
            simulation_id: Simulation that owns the rendered map.
            output_dir: Directory in which to write the HTML map.
        """
        self._simulation_id = simulation_id
        self._output_dir = output_dir

    def run(self) -> RenderMapOutcome:
        """
        Render the map HTML for a simulation (AsyncRunner worker process).

        Returns:
            RenderMapOutcome: ``simulation_id`` and written ``html_path``.

        Raises:
            RenderMapError: When map rendering or HTML export fails.
        """
        try:
            manager = MapRenderer()
            html_path = manager.to_html(
                path=self._output_dir,
                prefix=self._simulation_id,
            )
        except Exception as error:
            logger.exception(
                "Map render failed",
                simulation_id=self._simulation_id,
                output_dir=str(self._output_dir),
                error=str(error),
            )
            raise RenderMapError(
                simulation_id=self._simulation_id,
                reason=f"Failed to render map for simulation {self._simulation_id}",
            ) from error
        logger.info(
            "Map rendered",
            simulation_id=self._simulation_id,
            html_path=str(html_path),
        )
        return RenderMapOutcome(
            simulation_id=self._simulation_id,
            html_path=html_path,
        )

    @staticmethod
    def apply_main_thread(
        model_entrypoint: CoreSignalEmitter,
        outcome: RenderMapOutcome,
    ) -> None:
        """Persist a rendered map path and emit its completion event.

        Args:
            model_entrypoint: Main-thread simulation mutation boundary.
            outcome: Worker result containing the rendered map path.
        """
        mutation_entrypoint = cast(SimulationMutationEntrypoint, model_entrypoint)
        simulation = mutation_entrypoint.get_simulation(outcome.simulation_id)
        if simulation is None:
            try:
                outcome.html_path.unlink(missing_ok=True)
            except OSError as error:
                logger.warning(
                    "Orphan map file could not be removed",
                    simulation_id=outcome.simulation_id,
                    html_path=str(outcome.html_path),
                    error=str(error),
                )
            logger.warning(
                "Rendered map discarded because the simulation no longer exists",
                simulation_id=outcome.simulation_id,
            )
            return
        mutation_entrypoint.set_simulation_map_file(
            outcome.simulation_id, outcome.html_path
        )
        mutation_entrypoint.emit_core_signal(
            CoreSignals.MAP_RENDERED,
            MapRenderedPayload(
                simulation_id=outcome.simulation_id,
                html_path=outcome.html_path,
            ),
        )

    @staticmethod
    def apply_failure_main_thread(
        model_entrypoint: CoreSignalEmitter, error: BaseException
    ) -> None:
        """Clear failed map state and emit a render failure.

        Args:
            model_entrypoint: Main-thread simulation mutation boundary.
            error: Worker failure to translate.
        """
        mutation_entrypoint = cast(SimulationMutationEntrypoint, model_entrypoint)
        if isinstance(error, RenderMapError):
            simulation = mutation_entrypoint.get_simulation(error.simulation_id)
            if simulation is not None:
                mutation_entrypoint.clear_simulation_map_file(error.simulation_id)
                mutation_entrypoint.emit_core_signal(
                    CoreSignals.MAP_RENDER_FAILED,
                    MapRenderFailedPayload(
                        simulation_id=error.simulation_id,
                        reason=error.reason,
                    ),
                )
            else:
                logger.warning(
                    "Map failure event skipped because the simulation no longer exists",
                    simulation_id=error.simulation_id,
                )
            return
        RenderMapWork.emit_generic_error(
            model_entrypoint,
            source="RenderMapWork",
            message=str(error),
            error=error,
        )
