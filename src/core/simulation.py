from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final, Iterable

from core.collection import Repository
from core.devices import Phone, PhoneRepository
from core.location import Location
from logger import logger

SIMULATION_REPOSITORY_SCHEMA_VERSION: Final[int] = 1  # JSON file schema version
INDEX_FILENAME: Final[str] = (
    "index.json"  # File name of the index file; This file contains the list of all simulation IDs
)
SIMULATION_FILENAME: Final[str] = (
    "simulation.json"  # File name of the simulation file; This file contains the metadata of the simulation
)


@dataclass(unsafe_hash=True, match_args=True, frozen=False)
class Simulation:
    """Simulation."""

    id: Final[str] = field(
        default_factory=lambda: uuid.uuid4().hex,
        metadata={"description": "The id of the simulation"},
        hash=True,
    )
    real_location: Location = field(
        default_factory=lambda: Location(lat=0.0, lon=0.0, label=None),
        metadata={"description": "The real location of the device"},
    )
    fake_location: Location = field(
        default_factory=lambda: Location(lat=0.0, lon=0.0, label=None),
        metadata={"description": "The fake location to simulate on the device"},
    )
    device: Phone | None = field(
        default=None, metadata={"description": "The device of the simulation"}
    )
    map_file: Path | None = field(
        default=None, metadata={"description": "The map file of the simulation"}
    )
    log_file: Path | None = field(
        default=None, metadata={"description": "The log file of the simulation"}
    )
    active: bool = field(
        default=False, metadata={"description": "Whether the simulation is active"}
    )
    # When True, ``__setattr__`` logs changes to the public simulation fields.
    _fields_ready: bool = field(init=False, repr=False, compare=False, default=False)

    def to_payload(self, simulation_dir: Path) -> dict[str, object]:
        """
        Convert the simulation to a payload.
        """
        return {
            "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
            "id": self.id,
            "device": self.device.to_payload() if self.device is not None else None,
            "real_location": self.real_location.to_payload(),
            "fake_location": self.fake_location.to_payload(),
            "map_file": _relative_to_simulation_dir(self.map_file, simulation_dir),
            "log_file": _relative_to_simulation_dir(self.log_file, simulation_dir),
            "active": self.active,
        }

    @staticmethod
    def from_payload(payload: dict[str, object], simulation_dir: Path) -> Simulation:
        """
        Create a simulation from a persisted metadata payload.
        """
        schema_version = payload.get("schema_version")
        if schema_version != SIMULATION_REPOSITORY_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported simulation schema version: {schema_version!r}"
            )
        simulation_id = str(payload["id"])
        device_payload = payload.get("device")
        device: Phone | None = None
        if isinstance(device_payload, dict):
            device = Phone.from_payload(device_payload)
        real_location_payload = payload.get("real_location")
        fake_location_payload = payload.get("fake_location")
        if not isinstance(real_location_payload, dict):
            raise ValueError("Simulation payload missing real_location")
        if not isinstance(fake_location_payload, dict):
            raise ValueError("Simulation payload missing fake_location")
        map_file_raw = payload.get("map_file")
        log_file_raw = payload.get("log_file")
        map_file = _absolute_in_simulation_dir(
            None if map_file_raw is None else str(map_file_raw),
            simulation_dir,
        )
        log_file = _absolute_in_simulation_dir(
            None if log_file_raw is None else str(log_file_raw),
            simulation_dir,
        )
        active_raw = payload.get("active", False)
        active = active_raw if isinstance(active_raw, bool) else bool(active_raw)
        return Simulation(
            id=simulation_id,
            device=device,
            real_location=Location.from_payload(real_location_payload),
            fake_location=Location.from_payload(fake_location_payload),
            map_file=map_file,
            log_file=log_file,
            active=active,
        )

    # Setting _fields_ready to True to allow __setattr__ to log changes to the public simulation fields
    # This is done in __post_init__ to avoid logging the initial values of the public simulation fields
    def __post_init__(self) -> None:
        object.__setattr__(self, "_fields_ready", True)

    # Overriding __setattr__ to log changes to the public simulation fields
    def __setattr__(self, name: str, value: object) -> None:
        if name in self.__class__.__dataclass_fields__ and name != "_fields_ready":
            if self._fields_ready and hasattr(self, name):
                old = getattr(self, name)
                if old != value:
                    logger.debug(
                        f"Simulation {self.id}: field updated",
                        field=name,
                        old=old,
                        new=value,
                    )
        object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class PersistedSimulationState:
    """Persisted simulation metadata loaded from disk for startup apply."""

    simulations: list[Simulation] = field(default_factory=list)
    last_active_device_id: str | None = None


def _relative_to_simulation_dir(path: Path | None, simulation_dir: Path) -> str | None:
    """
    Convert a path to a relative path to the simulation directory.
    """
    if path is None:
        return None
    try:
        return str(path.relative_to(simulation_dir))
    except ValueError:
        logger.warning(
            "SimulationDiskStore: artifact path is outside simulation directory",
            path=str(path),
            simulation_dir=str(simulation_dir),
        )
        return str(path)


def _absolute_in_simulation_dir(
    path_value: str | None, simulation_dir: Path
) -> Path | None:
    """Resolve a persisted relative artifact path against a simulation directory."""
    if path_value is None:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    return simulation_dir / path


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    """
    Write a JSON file atomically.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


class SimulationDiskStore:
    """Disk I/O for simulation metadata, index, and on-disk simulation directories."""

    def __init__(self, save_dir: Path) -> None:
        self._save_dir: Path = save_dir
        self._index_simulation_ids: list[str] = []
        self._last_active_device_id: str | None = None
        self._save_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_file.is_file():
            self.write_index([], None)
        else:
            self._load_index_from_disk()

    @property
    def save_dir(self) -> Path:
        """Root directory for persisted simulation data."""
        return self._save_dir

    @property
    def index_file(self) -> Path:
        """Path to the persisted simulation index file."""
        return self._save_dir / INDEX_FILENAME

    @property
    def last_active_device_id(self) -> str | None:
        """Last active device id read from or written to the index."""
        return self._last_active_device_id

    def simulation_dir(self, simulation_id: str) -> Path:
        """Directory for one simulation's on-disk artifacts."""
        return self._save_dir / simulation_id

    def simulation_metadata_file(self, simulation_id: str) -> Path:
        """Path to one simulation's metadata JSON file."""
        return self.simulation_dir(simulation_id) / SIMULATION_FILENAME

    def _read_index_file(self) -> dict[str, object] | None:
        """Read and parse the persisted index JSON file."""
        if not self.index_file.is_file():
            return None
        try:
            payload = json.loads(self.index_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            logger.warning(
                "SimulationDiskStore: failed to parse index file",
                path=str(self.index_file),
                error=str(error),
            )
            return None
        if not isinstance(payload, dict):
            logger.warning(
                "SimulationDiskStore: index file is not a JSON object",
                path=str(self.index_file),
            )
            return None
        return payload

    def _parse_index_payload(
        self, payload: dict[str, object]
    ) -> tuple[list[str], str | None] | None:
        """Extract simulation ids and last active device id from a parsed index payload."""
        schema_version = payload.get("schema_version")
        if schema_version != SIMULATION_REPOSITORY_SCHEMA_VERSION:
            logger.warning(
                "SimulationDiskStore: unsupported index schema version",
                schema_version=schema_version,
            )
            return None
        simulation_ids_raw = payload.get("simulations", [])
        if not isinstance(simulation_ids_raw, list):
            logger.warning(
                "SimulationDiskStore: index simulations entry is not a list",
                path=str(self.index_file),
            )
            return None
        simulation_ids = [str(simulation_id) for simulation_id in simulation_ids_raw]
        last_active_raw = payload.get("last_active_device_id")
        if last_active_raw is None:
            last_active_device_id: str | None = None
        else:
            last_active_device_id = str(last_active_raw).strip() or None
        return simulation_ids, last_active_device_id

    def _load_index_from_disk(self) -> None:
        """Load index metadata and simulation ids from disk in a single read."""
        payload = self._read_index_file()
        if payload is None:
            return
        parsed = self._parse_index_payload(payload)
        if parsed is None:
            return
        self._index_simulation_ids, self._last_active_device_id = parsed

    def _load_simulation_from_disk(self, simulation_id: str) -> Simulation | None:
        """Read one simulation metadata file from disk."""
        metadata_path = self.simulation_metadata_file(simulation_id)
        if not metadata_path.is_file():
            logger.warning(
                "SimulationDiskStore: simulation metadata file missing",
                simulation_id=simulation_id,
                path=str(metadata_path),
            )
            return None
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            logger.warning(
                "SimulationDiskStore: failed to parse simulation metadata",
                simulation_id=simulation_id,
                path=str(metadata_path),
                error=str(error),
            )
            return None
        if not isinstance(payload, dict):
            logger.warning(
                "SimulationDiskStore: simulation metadata is not a JSON object",
                simulation_id=simulation_id,
                path=str(metadata_path),
            )
            return None
        simulation_dir = self.simulation_dir(simulation_id)
        return Simulation.from_payload(payload, simulation_dir)

    def _delete_persisted_simulation_dir(self, simulation_id: str) -> None:
        """Delete a simulation directory from disk."""
        simulation_dir = self.simulation_dir(simulation_id)
        if simulation_dir.is_dir():
            shutil.rmtree(simulation_dir)
            logger.info(
                "SimulationDiskStore: deleted stale persisted simulation directory",
                simulation_id=simulation_id,
                path=str(simulation_dir),
            )

    def load_for_devices(self, devices: PhoneRepository) -> PersistedSimulationState:
        """
        Load persisted simulations from disk and bind each to a paired device instance.

        Simulations whose device id is not in ``devices`` are deleted from disk.
        """
        loaded: list[Simulation] = []
        for simulation_id in self._index_simulation_ids:
            try:
                simulation = self._load_simulation_from_disk(simulation_id)
            except (TypeError, ValueError) as error:
                logger.warning(
                    "SimulationDiskStore: failed to deserialize simulation",
                    simulation_id=simulation_id,
                    error=str(error),
                )
                self._delete_persisted_simulation_dir(simulation_id)
                continue
            if simulation is None:
                self._delete_persisted_simulation_dir(simulation_id)
                continue
            if simulation.device is None:
                logger.warning(
                    "SimulationDiskStore: persisted simulation has no device",
                    simulation_id=simulation_id,
                )
                self._delete_persisted_simulation_dir(simulation_id)
                continue
            paired_device = devices.get(simulation.device.id)
            if paired_device is None:
                logger.info(
                    "SimulationDiskStore: deleting simulation for unavailable device",
                    simulation_id=simulation_id,
                    device_id=simulation.device.id,
                )
                self._delete_persisted_simulation_dir(simulation_id)
                continue
            simulation.device = paired_device
            loaded.append(simulation)
        if (
            self._last_active_device_id is not None
            and devices.get(self._last_active_device_id) is None
        ):
            logger.info(
                "SimulationDiskStore: clearing last active device (not paired)",
                device_id=self._last_active_device_id,
            )
            self._last_active_device_id = None
            self.write_index(
                [simulation.id for simulation in loaded],
                self._last_active_device_id,
            )
        else:
            self.write_index(
                [simulation.id for simulation in loaded],
                self._last_active_device_id,
            )
        return PersistedSimulationState(
            simulations=loaded,
            last_active_device_id=self._last_active_device_id,
        )

    def write_index(
        self,
        simulation_ids: Iterable[str],
        last_active_device_id: str | None,
    ) -> Path:
        """Write the index file from explicit simulation ids and last active device id."""
        self._index_simulation_ids = list(simulation_ids)
        self._last_active_device_id = last_active_device_id
        payload: dict[str, object] = {
            "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
            "simulations": self._index_simulation_ids,
            "last_active_device_id": self._last_active_device_id,
        }
        _write_json_atomic(self.index_file, payload)
        return self.index_file

    def write_simulation(self, simulation: Simulation) -> Path:
        """Write one simulation metadata file."""
        simulation_dir = self.simulation_dir(simulation.id)
        simulation_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = self.simulation_metadata_file(simulation.id)
        payload = simulation.to_payload(simulation_dir)
        _write_json_atomic(metadata_path, payload)
        return metadata_path

    def write_all(
        self,
        simulations: Iterable[Simulation],
        last_active_device_id: str | None,
    ) -> None:
        """Write every simulation metadata file and the index."""
        for simulation in simulations:
            self.write_simulation(simulation)
        self.write_index(
            [simulation.id for simulation in simulations], last_active_device_id
        )

    def delete_simulation_dir(self, simulation_id: str) -> None:
        """Remove a simulation directory from disk."""
        simulation_dir = self.simulation_dir(simulation_id)
        if simulation_dir.is_dir():
            shutil.rmtree(simulation_dir)


class SimulationRepository(Repository[Simulation]):
    """In-memory repository for simulations; persistence delegated to SimulationDiskStore."""

    def __init__(self, save_dir: Path) -> None:
        super().__init__()
        self._store = SimulationDiskStore(save_dir)
        self._last_active_device_id: str | None = self._store.last_active_device_id

    @property
    def last_active_device_id(self) -> str | None:
        """Return the persisted last selected device id, if any."""
        return self._last_active_device_id

    @last_active_device_id.setter
    def last_active_device_id(self, device_id: str | None) -> None:
        """Persist the last selected device id in the repository index."""
        normalized = (device_id or "").strip() or None
        self._last_active_device_id = normalized
        self.write_index()

    def sync_last_active_device_id(self, device_id: str | None) -> None:
        """Update the in-memory last active device id without writing the index."""
        self._last_active_device_id = (device_id or "").strip() or None

    def restore(self, simulation: Simulation) -> None:
        """Load a simulation into memory without creating new on-disk artifacts."""
        if simulation.id in self._repository:
            raise ValueError(f"Simulation with id {simulation.id} already exists")
        self._repository[simulation.id] = simulation
        logger.debug(
            "SimulationRepository.restore: repository snapshot ({} item(s))",
            len(self._repository),
        )

    def load_all_for_devices(self, devices: PhoneRepository) -> list[Simulation]:
        """
        Load persisted simulations from disk into this repository.

        Simulations whose device id is not in ``devices`` are deleted from disk.
        """
        state = self._store.load_for_devices(devices)
        for simulation in state.simulations:
            try:
                self.restore(simulation)
            except ValueError as error:
                logger.warning(
                    "SimulationRepository: failed to restore simulation",
                    simulation_id=simulation.id,
                    error=str(error),
                )
        self.sync_last_active_device_id(state.last_active_device_id)
        return list(state.simulations)

    @property
    def save_dir(self) -> Path:
        """Get the save directory."""
        return self._store.save_dir

    @property
    def index_file(self) -> Path:
        """Get the index file."""
        return self._store.index_file

    def simulation_dir(self, simulation_id: str) -> Path:
        """Get the simulation directory."""
        return self._store.simulation_dir(simulation_id)

    def simulation_metadata_file(self, simulation_id: str) -> Path:
        """Get the simulation metadata file."""
        return self._store.simulation_metadata_file(simulation_id)

    def write_index(self) -> Path:
        """Write the index file from in-memory repository state."""
        return self._store.write_index(
            [simulation.id for simulation in self],
            self._last_active_device_id,
        )

    def write_simulation(self, simulation: Simulation) -> Path:
        """Write the simulation metadata file."""
        return self._store.write_simulation(simulation)

    def write_all(self) -> None:
        """Write all simulations and the index."""
        self._store.write_all(self, self._last_active_device_id)

    def add(self, item: Simulation) -> None:
        """Add a simulation to the repository."""
        super().add(item)
        simulation_dir = self.simulation_dir(item.id)
        simulation_dir.mkdir(parents=True, exist_ok=True)
        item.log_file = simulation_dir / f"{item.id}.log"
        with open(item.log_file, "w") as f:
            f.write(f"Simulation {item.id} created at {datetime.now().isoformat()}\n")
        self.write_simulation(item)
        self.write_index()

    def remove(self, item: Simulation) -> None:
        """Remove a simulation from the repository."""
        super().remove(item)
        self._store.delete_simulation_dir(item.id)
        self.write_index()
