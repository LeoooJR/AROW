"""
Simulation state and lifecycle (active device, locations, start/stop/resume/pause).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

from controller.domains.app_sub_controller import AppSubController
from core.signals import (
    CoreSignals,
    SimulationCreatedPayload,
    SimulationCreationFailedPayload,
    SimulationDeletedPayload,
    SimulationDeleteSkippedPayload,
    SimulationRestoredPayload,
)
from gui.signals import signals
from logger import logger

if TYPE_CHECKING:
    from controller.orchestration.app_controller import AppController


class SimulationSubController(AppSubController):
    """Subcontroller for the current simulation model state (no own AsyncRunner)."""

    def __init__(self, app: AppController) -> None:
        super().__init__(app)

    def connect_view_signals(self) -> None:
        signals.DEVICE.DeviceSelectionConfirmed.connect(
            self._on_device_selection_confirmed
        )  # Ensuring the device is selected when the user confirms the selection
        signals.DEVICE.RemoveDeviceRequested.connect(
            self._on_remove_device_requested
        )  # Ensuring no simulation is running before device is removed by adb subcontroller

    def connect_model_signals(self) -> None:
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.SIMULATION_CREATED,
            self._on_simulation_created,
        )
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.SIMULATION_RESTORED,
            self._on_simulation_restored,
        )
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.SIMULATION_CREATION_FAILED,
            self._on_simulation_creation_failed,
        )
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.SIMULATION_DELETED,
            self._on_simulation_deleted,
        )
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.SIMULATION_DELETE_SKIPPED,
            self._on_simulation_delete_skipped,
        )

    def persist_simulation_repository(self) -> None:
        """Persist simulation metadata and the repository index at shutdown."""
        self.model_entrypoint.persist_simulations()

    def is_simulation_active(self, id: str) -> bool:
        """Check if the simulation is active."""
        return self.model_entrypoint.is_simulation_active(id)

    def run(self, id: str) -> None:
        """Run the simulation by setting it active."""
        if self.is_simulation_active(id):
            return
        try:
            self.model_entrypoint.set_simulation_active(id, True)
            # self.view.forward_simulation_started() # TODO: Implement this
        except ValueError as e:
            logger.error(
                "Simulation could not be activated",
                error=str(e),
                simulation_id=id,
            )
            return

    def stop(self, id: str) -> None:
        """Stop the simulation by setting it inactive."""
        if not self.is_simulation_active(id):
            return
        try:
            self.model_entrypoint.set_simulation_active(id, False)
            # self.view.forward_simulation_stopped() # TODO: Implement this
        except ValueError as e:
            logger.error(
                "Simulation could not be deactivated",
                error=str(e),
                simulation_id=id,
            )
            return

    def pause(self, id: str) -> None:
        """Pause the simulation by setting it inactive."""
        if not self.is_simulation_active(id):
            return
        try:
            self.model_entrypoint.set_simulation_active(id, False)
            # self.view.forward_simulation_paused() # TODO: Implement this
        except ValueError as e:
            logger.error(
                "Simulation could not be paused",
                error=str(e),
                simulation_id=id,
            )
            return

    def resume(self, id: str) -> None:
        """Resume the simulation by setting it active."""
        if self.is_simulation_active(id):
            return
        try:
            self.model_entrypoint.set_simulation_active(id, True)
            # self.view.forward_simulation_resumed() # TODO: Implement this
        except ValueError as e:
            logger.error(
                "Simulation could not be resumed",
                error=str(e),
                simulation_id=id,
            )
            return

    @Slot(str, str)
    def _on_device_selection_confirmed(self, device_id: str, device_name: str) -> None:
        """In-memory selection of the active device (UI thread)."""
        logger.debug(
            "Simulation creation requested for selected device",
            device_id=device_id,
            device_name=device_name,
        )
        self.model_entrypoint.create_simulation(device_id=device_id)

    @Slot(str)
    def _on_remove_device_requested(self, device_id: str) -> None:
        """Handle the remove device requested event."""
        logger.debug(
            "Simulation deletion requested for device",
            device_id=device_id,
        )
        self.model_entrypoint.delete_simulation_for_device(device_id)

    def _on_simulation_created(self, payload: SimulationCreatedPayload) -> None:
        """Handle the simulation created event."""
        if not payload.device_id:
            logger.error(
                "Simulation creation event has no device",
                simulation_id=payload.simulation_id,
            )
            return
        self.view.forward_device_selection_succeeded(
            payload.simulation_id,
            payload.device_id,
            payload.device_name,
        )

    def _on_simulation_creation_failed(
        self, payload: SimulationCreationFailedPayload
    ) -> None:
        """Forward simulation creation failure to the device selection UI."""
        self.view.forward_device_selection_failed(
            payload.device_id,
            payload.device_name,
        )

    def _on_simulation_deleted(self, payload: SimulationDeletedPayload) -> None:
        """Forward active-device removal success when the payload carries device context."""
        if payload.device_id is None:
            logger.warning(
                "Simulation deletion event has no device",
                simulation_id=payload.simulation_id,
            )
            return
        self.view.forward_remove_active_device_succeeded(payload.device_id)

    def _on_simulation_delete_skipped(
        self, payload: SimulationDeleteSkippedPayload
    ) -> None:
        """Keep remove-device requests quiet when no active simulation exists."""
        logger.debug(
            "Simulation deletion event ignored",
            device_id=payload.device_id,
            reason=payload.reason,
        )

    def _on_simulation_restored(self, payload: SimulationRestoredPayload) -> None:
        """Handle the simulation restored event."""
        if not payload.device_id:
            logger.error(
                "Simulation restoration event has no device",
                simulation_id=payload.simulation_id,
            )
            return
        self.view.forward_device_selection_succeeded(
            payload.simulation_id,
            payload.device_id,
            payload.device_name,
        )
