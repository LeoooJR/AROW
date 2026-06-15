"""
Simulation state and lifecycle (active device, locations, start/stop/resume/pause).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from controller.domains.app_sub_controller import AppSubController
from controller.helper import validate_model_entrypoint, validate_view
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
        # Simulation-specific model subscriptions (none yet) — extension point.
        return

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
                "SimulationSubController: failed to set simulation active",
                error=str(e),
                id=id,
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
                "SimulationSubController: failed to set simulation inactive",
                error=str(e),
                id=id,
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
                "SimulationSubController: failed to set simulation inactive",
                error=str(e),
                id=id,
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
                "SimulationSubController: failed to set simulation active",
                error=str(e),
                id=id,
            )
            return

    @validate_model_entrypoint
    def _on_device_selection_confirmed(self, device_id: str, device_name: str) -> None:
        """In-memory selection of the active device (UI thread)."""
        logger.debug(
            "SimulationSubController: device selection confirmed",
            input_device_id=device_id,
            input_device_name=device_name,
        )
        try:
            sim_id: str = self.model_entrypoint.create_simulation(device_id=device_id)
            logger.success(
                "SimulationSubController: active device set",
                sim_id=sim_id,
                device_id=device_id,
                device_name=device_name,
            )
            self.view.forward_device_selection_succeeded(device_id, device_name)
        except AttributeError as e:
            logger.error(
                "SimulationSubController: failed to get device",
                error=str(e),
                device_id=device_id,
            )
            self.view.forward_device_selection_failed(device_id, device_name)

    def _on_remove_device_requested(self, device_id: str) -> None:
        """Handle the remove device requested event."""
        try:
            self.model_entrypoint.delete_simulation_for_device(device_id)
            self.view.forward_remove_active_device_succeeded(device_id)
        except (
            ValueError
        ) as e:  # Simulation for device not found, the device was not active
            logger.debug(
                "SimulationSubController: no simulation found for device, safely ignoring",
                error=str(e),
                device_id=device_id,
            )
            return
        except Exception as e:
            logger.error(
                "SimulationSubController: failed to delete simulation for device",
                error=str(e),
                device_id=device_id,
            )
            return
