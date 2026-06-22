from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final

from core.collection import Repository
from core.devices import Phone
from core.location import Location
from logger import logger


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


class SimulationRepository(Repository[Simulation]):
    """Repository for the simulations."""

    def __init__(self, save_dir: Path) -> None:
        super().__init__()
        self._save_dir: Path = save_dir
        self._save_dir.mkdir(parents=True, exist_ok=True)

    def add(self, item: Simulation) -> None:
        super().add(item)
        simulation_dir = Path(self._save_dir / item.id)
        simulation_dir.mkdir(parents=True, exist_ok=True)
        item.log_file = simulation_dir / f"{item.id}.log"
        with open(item.log_file, "w") as f:
            f.write(f"Simulation {item.id} created at {datetime.now().isoformat()}\n")
