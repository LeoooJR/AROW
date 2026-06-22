from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final

from core.collection import Repository
from core.devices import Phone
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


def _location_to_payload(location: Location) -> dict[str, object]:
    return {
        "lat": location.lat,
        "lon": location.lon,
        "label": location.label,
    }


def _device_to_payload(device: Phone | None) -> dict[str, object] | None:
    if device is None:
        return None
    return {
        "id": device.id,
        "name": device.name,
        "os": device.os,
        "ip": device.ip,
        "port": device.port,
        "state": device.state,
        "stable_key": device.stable_key,
    }


def _relative_to_simulation_dir(path: Path | None, simulation_dir: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(simulation_dir))
    except ValueError:
        logger.warning(
            "SimulationRepository: artifact path is outside simulation directory",
            path=str(path),
            simulation_dir=str(simulation_dir),
        )
        return str(path)


def _simulation_to_payload(
    simulation: Simulation, simulation_dir: Path
) -> dict[str, object]:
    return {
        "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
        "id": simulation.id,
        "device": _device_to_payload(simulation.device),
        "real_location": _location_to_payload(simulation.real_location),
        "fake_location": _location_to_payload(simulation.fake_location),
        "map_file": _relative_to_simulation_dir(simulation.map_file, simulation_dir),
        "log_file": _relative_to_simulation_dir(simulation.log_file, simulation_dir),
        "active": simulation.active,
    }


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


class SimulationRepository(Repository[Simulation]):
    """Repository for the simulations."""

    def __init__(self, save_dir: Path) -> None:
        super().__init__()
        self._save_dir: Path = save_dir
        self._save_dir.mkdir(parents=True, exist_ok=True)
        self.write_index()

    @property
    def save_dir(self) -> Path:
        return self._save_dir

    @property
    def index_file(self) -> Path:
        return self._save_dir / INDEX_FILENAME

    def simulation_dir(self, simulation_id: str) -> Path:
        return self._save_dir / simulation_id

    def simulation_metadata_file(self, simulation_id: str) -> Path:
        return self.simulation_dir(simulation_id) / SIMULATION_FILENAME

    def write_index(self) -> Path:
        payload: dict[str, object] = {
            "schema_version": SIMULATION_REPOSITORY_SCHEMA_VERSION,
            "simulations": [simulation.id for simulation in self],
        }
        _write_json_atomic(self.index_file, payload)
        return self.index_file

    def write_simulation(self, simulation: Simulation) -> Path:
        simulation_dir = self.simulation_dir(simulation.id)
        simulation_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = self.simulation_metadata_file(simulation.id)
        payload = _simulation_to_payload(simulation, simulation_dir)
        _write_json_atomic(metadata_path, payload)
        return metadata_path

    def write_all(self) -> None:
        for simulation in self:
            self.write_simulation(simulation)
        self.write_index()

    def add(self, item: Simulation) -> None:
        super().add(item)
        simulation_dir = self.simulation_dir(item.id)
        simulation_dir.mkdir(parents=True, exist_ok=True)
        item.log_file = simulation_dir / f"{item.id}.log"
        with open(item.log_file, "w") as f:
            f.write(f"Simulation {item.id} created at {datetime.now().isoformat()}\n")
        self.write_index()

    def remove(self, item: Simulation) -> None:
        super().remove(item)
        simulation_dir = self.simulation_dir(item.id)
        if simulation_dir.is_dir():
            shutil.rmtree(simulation_dir)
        self.write_index()
