from abc import ABC
from typing import Tuple


class MapElement(ABC):
    """
    Abstract base class for all map elements.
    """

    def __init__(self, name: str, coordinates: Tuple[float, float]):
        self.name = name
        self._coordinates = coordinates

    @property
    def coordinates(self) -> Tuple[float, float]:
        """
        Return the coordinates of the map element.
        """
        return self._coordinates


class Station(MapElement):
    """
    A station on the map.
    """

    def __init__(self, name: str, coordinates: Tuple[float, float]):
        super().__init__(name, coordinates)


class Milestone(MapElement):
    """
    A milestone on the map.
    """

    def __init__(self, name: str, coordinates: Tuple[float, float]):
        super().__init__(name, coordinates)


class Railway(MapElement):
    """
    A railway on the map.
    """

    def __init__(self, name: str, coordinates: Tuple[float, float]):
        super().__init__(name, coordinates)
