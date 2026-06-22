"""
Folium / geo map HTML generation on a worker process; core-bus emit on the Qt main thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from core.exceptions import CoreException
from core.geo.renderer import MapRenderer
from core.signals import (
    CoreSignal,
    MapRenderedPayload,
    MapRenderFailedPayload,
)
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from logger import logger

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint


class RenderMapError(CoreException):
    """Map rendering failed; preserves simulation id for user-facing reporting."""

    def __init__(self, *, simulation_id: str, reason: str) -> None:
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

    def __init__(self, *, simulation_id: str, application_dir: Path) -> None:
        self._simulation_id = simulation_id
        self._application_dir = application_dir

    def run(self) -> RenderMapOutcome:
        """
        Render the map HTML for a simulation (AsyncRunner worker process).

        Returns:
            RenderMapOutcome: ``simulation_id`` and written ``html_path``.

        Raises:
            RenderMapError: When map rendering or HTML export fails.
        """
        output_dir = self._application_dir / "simulations" / self._simulation_id / "map"
        try:
            manager = MapRenderer()
            html_path = manager.to_html(path=output_dir, prefix=self._simulation_id)
        except Exception as error:
            logger.error(
                "RenderMapWork: failed to render map",
                simulation_id=self._simulation_id,
                output_dir=str(output_dir),
                error=str(error),
                exc_info=True,
            )
            raise RenderMapError(
                simulation_id=self._simulation_id,
                reason=f"Failed to render map for simulation {self._simulation_id}",
            ) from error
        logger.info(
            "RenderMapWork: map rendered",
            simulation_id=self._simulation_id,
            html_path=str(html_path),
        )
        return RenderMapOutcome(
            simulation_id=self._simulation_id,
            html_path=html_path,
        )

    @staticmethod
    def apply_main_thread(
        model_entrypoint: ModelEntrypoint,
        outcome: RenderMapOutcome,
    ) -> None:
        from core.entrypoint import ModelEntrypoint as _ModelEntrypoint

        if not isinstance(model_entrypoint, _ModelEntrypoint):
            raise TypeError("apply_main_thread() requires ModelEntrypoint")
        simulation = model_entrypoint.get_simulation(outcome.simulation_id)
        if simulation is None:
            logger.warning(
                "RenderMapWork: simulation missing on render success",
                simulation_id=outcome.simulation_id,
            )
            return
        simulation.map_file = outcome.html_path
        model_entrypoint._signal_bus.emit(
            CoreSignal.MAP_RENDERED,
            MapRenderedPayload(
                simulation_id=outcome.simulation_id,
                html_path=outcome.html_path,
            ),
        )

    @staticmethod
    def apply_failure_main_thread(
        model_entrypoint: ModelEntrypoint, error: BaseException
    ) -> None:
        from core.entrypoint import ModelEntrypoint as _ModelEntrypoint

        if not isinstance(model_entrypoint, _ModelEntrypoint):
            raise TypeError("apply_failure_main_thread() requires ModelEntrypoint")
        if isinstance(error, RenderMapError):
            simulation = model_entrypoint.get_simulation(error.simulation_id)
            if simulation is not None:
                simulation.map_file = None
                model_entrypoint._signal_bus.emit(
                    CoreSignal.MAP_RENDER_FAILED,
                    MapRenderFailedPayload(
                        simulation_id=error.simulation_id,
                        reason=error.reason,
                    ),
                )
            else:
                logger.warning(
                    "RenderMapWork: simulation missing on render failure",
                    simulation_id=error.simulation_id,
                )
            return
        RenderMapWork.emit_generic_error(
            model_entrypoint,
            source="RenderMapWork",
            message=str(error),
            error=error,
        )
