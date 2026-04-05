from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, unsafe_hash=True)
class Location:
    lat: float = field(
        metadata={"description": "The latitude of the location"}, default=0.0
    )
    lon: float = field(
        metadata={"description": "The longitude of the location"}, default=0.0
    )
    label: Optional[str] = field(
        metadata={"description": "The label of the location"}, default=None
    )
