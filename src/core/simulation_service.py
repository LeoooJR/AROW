"""Simulation lifecycle operations owned by the core model entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from core.devices import Phone
from core.geo.location import Location
from core.geo.milestone import Milestone
from core.signals import (
    CoreSignals,
    SimulationCreatedPayload,
    SimulationCreationFailedPayload,
    SimulationDeletedPayload,
    SimulationDeleteSkippedPayload,
    SimulationLocationValidatedPayload,
    SimulationLocationValidationRequestedPayload,
    SimulationMapFileChangedPayload,
    SimulationPositionChangedPayload,
    SimulationRestoredPayload,
    SimulationStateChangedPayload,
)
from core.simulation import Simulation, SimulationRepository
from logger import logger

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint


class SimulationService:
    """Own simulation CRUD, location setters, and related core signal emission."""

    def __init__(self, entrypoint: ModelEntrypoint, *, save_dir: Path) -> None:
        self._entrypoint = entrypoint
        self._simulations = SimulationRepository(save_dir)

    @property
    def _adb_server(self):
        return self._entrypoint._adb_server

    @property
    def _adb_client(self):
        return self._entrypoint._adb_client

    def restore_persisted_simulation(self, simulation: Simulation) -> None:
        """
        Restore one persisted simulation into the in-memory repository.

        Disk deserialization validates milestone/railway data synchronously via
        ``Milestone.deserialize``; async map revalidation is requested later when
        the restored simulation is selected through ``create_simulation``.
        """
        try:
            self._simulations.restore(simulation)
        except ValueError as error:
            logger.warning(
                "SimulationService: failed to restore persisted simulation",
                simulation_id=simulation.id,
                error=str(error),
            )

    def sync_last_active_device_id(self, device_id: str | None) -> None:
        """Update the in-memory last-active device id without writing the index."""
        self._simulations.sync_last_active_device_id(device_id)

    def create_simulation(self, device_id: str) -> None:
        """
        Create a new simulation or restore an existing one for a paired device.

        Emits ``SIMULATION_CREATED``, ``SIMULATION_RESTORED``, or
        ``SIMULATION_CREATION_FAILED``.
        """
        device: Phone | None = None
        if self._adb_server is None or self._adb_client is None:
            self._emit_simulation_creation_failed(
                device_id,
                device=None,
                reason="ADB server must be initialized before creating a simulation",
            )
            return
        device = self._adb_server.paired_devices.get(device_id)
        if device is None:
            self._emit_simulation_creation_failed(
                device_id,
                device=None,
                reason=f"Device with id {device_id} not found",
            )
            return
        try:
            self._adb_server.set_working_device(device)
            simulation = self._get_simulation_for_device(device_id)
            if simulation is None:
                simulation = Simulation(device=device)
                self._simulations.add(simulation)
                self._entrypoint.emit_core_signal(
                    CoreSignals.SIMULATION_CREATED,
                    SimulationCreatedPayload(
                        simulation_id=simulation.id,
                        device_id=device.id,
                        device_name=device.name,
                    ),
                )
            else:
                self._emit_simulation_restored(simulation, device)
            self._simulations.last_active_device_id = device_id
        except ValueError as error:
            self._emit_simulation_creation_failed(
                device_id,
                device=device,
                reason=str(error),
            )

    def _emit_simulation_restored(self, simulation: Simulation, device: Phone) -> None:
        """
        Emit restore signals and request async marker revalidation when needed.

        Persisted simulations are validated synchronously during
        ``Simulation.deserialize`` (referentiel lookup on disk load). When a
        restored simulation already has a spoofed milestone, we still emit
        ``SIMULATION_LOCATION_VALIDATION_REQUESTED`` so map/UI consumers refresh
        through the canonical async validation path on the main-thread bus.
        """
        logger.info(
            "SimulationService: reusing existing simulation for device",
            simulation_id=simulation.id,
            device_id=device.id,
        )
        self._entrypoint.emit_core_signal(
            CoreSignals.SIMULATION_RESTORED,
            SimulationRestoredPayload(
                simulation_id=simulation.id,
                device_id=device.id,
                device_name=device.name,
            ),
        )
        if simulation.spoofed_location.poi is None:
            return
        poi = simulation.spoofed_location.poi
        self._entrypoint.emit_core_signal(
            CoreSignals.SIMULATION_LOCATION_VALIDATION_REQUESTED,
            SimulationLocationValidationRequestedPayload(
                simulation_id=simulation.id,
                km=poi.km,
                line_code=poi.line.code,
                line_troncon=poi.line.troncon,
                lat=poi.geometry.y,
                lon=poi.geometry.x,
            ),
        )

    def _emit_simulation_creation_failed(
        self,
        device_id: str,
        *,
        device: Phone | None,
        reason: str,
    ) -> None:
        """Publish a typed simulation creation failure for controller bridging."""
        device_name = device.name if device is not None else device_id
        logger.error(
            "SimulationService: simulation creation failed",
            device_id=device_id,
            device_name=device_name,
            reason=reason,
        )
        self._entrypoint.emit_core_signal(
            CoreSignals.SIMULATION_CREATION_FAILED,
            SimulationCreationFailedPayload(
                device_id=device_id,
                device_name=device_name,
                reason=reason,
            ),
        )

    def get_simulation(self, simulation_id: str) -> Simulation | None:
        """Get a simulation by id."""
        return self._simulations.get(simulation_id)

    def is_simulation_active(self, simulation_id: str) -> bool:
        """Check if a simulation is active."""
        simulation = self._simulations.get(simulation_id)
        if simulation is None:
            raise ValueError(f"Simulation with id {simulation_id} not found")
        return simulation.active

    def set_simulation_active(self, simulation_id: str, active: bool) -> None:
        """Set a simulation active or inactive."""
        simulation = self._simulations.get(simulation_id)
        if simulation is None:
            raise ValueError(f"Simulation with id {simulation_id} not found")
        if simulation.active == active:
            return
        simulation.active = active
        self._entrypoint.emit_core_signal(
            CoreSignals.SIMULATION_STATE_CHANGED,
            SimulationStateChangedPayload(
                simulation_id=simulation.id,
                active=simulation.active,
            ),
        )

    def set_simulation_real_location(
        self, simulation_id: str, lat: float, lon: float
    ) -> None:
        """Set the simulation real device location and emit position changed."""
        simulation = self._simulations.get(simulation_id)
        if simulation is None:
            raise ValueError(f"Simulation with id {simulation_id} not found")
        self._set_simulation_location(
            simulation,
            "real_location",
            Location(lat=lat, lon=lon, poi=None),
        )

    def set_simulation_spoofed_location(
        self,
        simulation_id: str,
        lat: float,
        lon: float,
        marker: SimulationLocationValidatedPayload | None = None,
    ) -> None:
        """Set spoofed location; rebuild validated milestone from payload when provided."""
        simulation = self._simulations.get(simulation_id)
        if simulation is None:
            raise ValueError(f"Simulation with id {simulation_id} not found")
        poi: Milestone | None = None
        if marker is not None:
            poi = Milestone.from_validated_payload(marker)
        self._set_simulation_location(
            simulation,
            "spoofed_location",
            Location(lat=lat, lon=lon, poi=poi),
        )

    def set_simulation_map_file(self, simulation_id: str, map_file: Path) -> None:
        """Set the simulation map file path and emit map-file changed."""
        simulation = self._simulations.get(simulation_id)
        if simulation is None:
            raise ValueError(f"Simulation with id {simulation_id} not found")
        if simulation.map_file == map_file:
            return
        simulation.map_file = map_file
        self._entrypoint.emit_core_signal(
            CoreSignals.SIMULATION_MAP_FILE_CHANGED,
            SimulationMapFileChangedPayload(
                simulation_id=simulation.id,
                map_file_path=map_file,
            ),
        )

    def _set_simulation_location(
        self,
        simulation: Simulation,
        field_name: Literal["real_location", "spoofed_location"],
        location: Location,
    ) -> None:
        """Assign a location field when changed and emit position changed."""
        current = getattr(simulation, field_name)
        if current == location:
            return
        setattr(simulation, field_name, location)
        self._entrypoint.emit_core_signal(
            CoreSignals.SIMULATION_POSITION_CHANGED,
            SimulationPositionChangedPayload(simulation_id=simulation.id),
        )

    def persist_simulation(self, simulation_id: str) -> None:
        """Write one simulation metadata file to disk."""
        simulation = self._simulations.get(simulation_id)
        if simulation is None:
            logger.warning(
                "SimulationService: persist_simulation skipped (simulation not found)",
                simulation_id=simulation_id,
            )
            return
        self._simulations.write_simulation(simulation)

    def delete_simulation(self, simulation: Simulation) -> None:
        """Delete a simulation from the in-memory repository."""
        self._simulations.remove(simulation)

    def persist_simulations(self) -> None:
        """Persist every simulation and the repository index to disk."""
        self._simulations.write_all()

    def _get_simulation_for_device(self, device_id: str) -> Simulation | None:
        """Return the existing simulation for a device when one is already tracked."""
        for simulation in self._simulations:
            device = simulation.device
            if device is not None and device.id == device_id:
                return simulation
        return None

    def delete_simulation_for_device(self, device_id: str) -> None:
        """Delete a simulation for a device and emit deleted/skipped signals."""
        simulation = self._get_simulation_for_device(device_id)
        if simulation is None:
            logger.debug(
                "SimulationService: no simulation found for device, skipping deletion",
                device_id=device_id,
            )
            self._entrypoint.emit_core_signal(
                CoreSignals.SIMULATION_DELETE_SKIPPED,
                SimulationDeleteSkippedPayload(
                    device_id=device_id,
                    reason=f"Simulation for device with id {device_id} not found",
                ),
            )
            return
        simulation_id = simulation.id
        self.delete_simulation(simulation)
        self._entrypoint.emit_core_signal(
            CoreSignals.SIMULATION_DELETED,
            SimulationDeletedPayload(
                simulation_id=simulation_id,
                device_id=device_id,
            ),
        )
        if self._adb_server is not None:
            working_device = self._adb_server.get_working_device()
            if working_device is not None and working_device.id == device_id:
                self._adb_server.clear_working_device()
        if self._simulations.last_active_device_id == device_id:
            self._simulations.last_active_device_id = None
