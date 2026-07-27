"""
Map milestone validation on a worker thread; core-bus emit on the Qt main thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from shapely.geometry import Point

from core.entrypoint_protocol import CoreSignalEmitter
from core.geo.exceptions import MilestoneValidationError, RailwayValidationError
from core.geo.milestone import Milestone
from core.geo.railway import Railway
from core.signals import (
    CoreSignals,
    SimulationLocationRejectedPayload,
    SimulationLocationValidatedPayload,
)
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from logger import logger


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


def _rejected_payload(
    *,
    simulation_id: str,
    km: int,
    line_code: str,
    line_troncon: int,
    latitude: float,
    longitude: float,
    reason: str,
) -> ValidateSimulationMarkerLocationOutcome:
    """Return a typed rejected outcome for validation or parse failures."""
    return ValidateSimulationMarkerLocationOutcome(
        rejected=SimulationLocationRejectedPayload(
            simulation_id=simulation_id,
            km=km,
            line_code=line_code,
            line_troncon=line_troncon,
            lat=latitude,
            lon=longitude,
            reason=reason,
        ),
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
        line_code: str,
        line_troncon: int,
        latitude: float,
        longitude: float,
    ) -> None:
        self._simulation_id = simulation_id
        self._km = km
        self._line_code = line_code
        self._line_troncon = line_troncon
        self._latitude = latitude
        self._longitude = longitude

    def run(self) -> ValidateSimulationMarkerLocationOutcome:
        """
        Validate a map milestone against referentiel datasets (AsyncRunner worker thread).

        Returns:
            ValidateSimulationMarkerLocationOutcome: Validated or rejected payload for
            :meth:`apply_main_thread`; validation failures are outcomes, not exceptions.

        Raises:
            Exception: Unexpected failures propagate to AsyncRunner.
        """
        try:
            validated_line = Railway.validate(
                code=self._line_code,
                troncon=self._line_troncon,
            )
            validated_milestone = Milestone.validate(
                self._km,
                validated_line,
                Point(self._longitude, self._latitude),
            )
            return ValidateSimulationMarkerLocationOutcome(
                validated=Milestone.to_validated_payload(
                    simulation_id=self._simulation_id,
                    milestone=validated_milestone,
                    line=validated_line,
                ),
            )
        except (MilestoneValidationError, RailwayValidationError) as error:
            return _rejected_payload(
                simulation_id=self._simulation_id,
                km=self._km,
                line_code=self._line_code,
                line_troncon=self._line_troncon,
                latitude=self._latitude,
                longitude=self._longitude,
                reason=str(error),
            )

    @staticmethod
    def apply_main_thread(
        model_entrypoint: CoreSignalEmitter,
        outcome: ValidateSimulationMarkerLocationOutcome,
    ) -> None:
        if outcome.validated is not None:
            logger.info(
                "Simulation location validated",
                simulation_id=outcome.validated.simulation_id,
                km=outcome.validated.km,
                line_code=outcome.validated.line_code,
                line_troncon=outcome.validated.line_troncon,
            )
            model_entrypoint.emit_core_signal(
                CoreSignals.SIMULATION_LOCATION_VALIDATED,
                outcome.validated,
            )
            return
        if outcome.rejected is not None:
            logger.warning(
                "Simulation location rejected",
                simulation_id=outcome.rejected.simulation_id,
                km=outcome.rejected.km,
                line_code=outcome.rejected.line_code,
                line_troncon=outcome.rejected.line_troncon,
                reason=outcome.rejected.reason,
            )
            model_entrypoint.emit_core_signal(
                CoreSignals.SIMULATION_LOCATION_REJECTED,
                outcome.rejected,
            )

    @staticmethod
    def apply_failure_main_thread(
        model_entrypoint: CoreSignalEmitter, error: BaseException
    ) -> None:
        ValidateSimulationMarkerLocationWork.emit_generic_error(
            model_entrypoint,
            source="ValidateSimulationMarkerLocationWork",
            message=str(error),
            error=error,
        )
