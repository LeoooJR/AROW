"""
Map milestone validation on a worker thread; core-bus emit on the Qt main thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from shapely.geometry import Point

from core.geo.element import Milestone, Railway
from core.geo.exceptions import MilestoneValidationError, RailwayValidationError
from core.signals import (
    CoreSignals,
    SimulationLocationRejectedPayload,
    SimulationLocationValidatedPayload,
)
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint


@dataclass(frozen=True, slots=True)
class ValidateSimulationMarkerLocationOutcome(CoreRuntimeWorkOutcome):
    """Result of :meth:`ValidateSimulationMarkerLocationWork.run` (worker thread)."""

    validated: SimulationLocationValidatedPayload | None = None
    rejected: SimulationLocationRejectedPayload | None = None

    def __post_init__(self) -> None:
        if (self.validated is None) == (self.rejected is None):
            raise ValueError(
                "ValidateSimulationMarkerLocationOutcome requires exactly one of "
                "validated or rejected payload"
            )


class ValidateSimulationMarkerLocationWork(
    CoreRuntimeWork[ValidateSimulationMarkerLocationOutcome]
):
    """
    Blocking geo validation on a worker thread; apply emits location validated/rejected.
    """

    def __init__(
        self,
        *,
        simulation_id: str,
        km: int,
        line: str,
        latitude: float,
        longitude: float,
    ) -> None:
        self._simulation_id = simulation_id
        self._km = km
        self._line = line
        self._latitude = latitude
        self._longitude = longitude

    def run(self) -> ValidateSimulationMarkerLocationOutcome:
        """
        Validate a map milestone against referentiel datasets (AsyncRunner worker thread).

        Returns:
            ValidateSimulationMarkerLocationOutcome: Validated or rejected payload for
            :meth:`apply_main_thread`; validation failures are outcomes, not exceptions.

        Raises:
            ValueError: When ``line`` cannot be parsed into code and troncon.
            Exception: Unexpected failures propagate to AsyncRunner.
        """
        try:
            code, troncon_raw = self._line.rsplit("-", maxsplit=1)
            validated_line = Railway.validate(
                code=code,
                troncon=int(troncon_raw),
            )
            validated_milestone = Milestone.validate(
                self._km,
                validated_line,
                Point(self._longitude, self._latitude),
            )
            return ValidateSimulationMarkerLocationOutcome(
                validated=SimulationLocationValidatedPayload(
                    simulation_id=self._simulation_id,
                    lat=validated_milestone.geometry.y,
                    lon=validated_milestone.geometry.x,
                    poi=validated_milestone.serialize(),
                ),
            )
        except (MilestoneValidationError, RailwayValidationError) as error:
            return ValidateSimulationMarkerLocationOutcome(
                rejected=SimulationLocationRejectedPayload(
                    simulation_id=self._simulation_id,
                    km=self._km,
                    line=self._line,
                    lat=self._latitude,
                    lon=self._longitude,
                    reason=str(error),
                ),
            )

    @staticmethod
    def apply_main_thread(
        model_entrypoint: ModelEntrypoint,
        outcome: ValidateSimulationMarkerLocationOutcome,
    ) -> None:
        from core.entrypoint import ModelEntrypoint as _ModelEntrypoint

        if not isinstance(model_entrypoint, _ModelEntrypoint):
            raise TypeError("apply_main_thread() requires ModelEntrypoint")
        if outcome.validated is not None:
            model_entrypoint.emit_core_signal(
                CoreSignals.SIMULATION_LOCATION_VALIDATED,
                outcome.validated,
            )
            return
        if outcome.rejected is not None:
            model_entrypoint.emit_core_signal(
                CoreSignals.SIMULATION_LOCATION_REJECTED,
                outcome.rejected,
            )

    @staticmethod
    def apply_failure_main_thread(
        model_entrypoint: ModelEntrypoint, error: BaseException
    ) -> None:
        from core.entrypoint import ModelEntrypoint as _ModelEntrypoint

        if not isinstance(model_entrypoint, _ModelEntrypoint):
            raise TypeError("apply_failure_main_thread() requires ModelEntrypoint")
        ValidateSimulationMarkerLocationWork.emit_generic_error(
            model_entrypoint,
            source="ValidateSimulationMarkerLocationWork",
            message=str(error),
            error=error,
        )
