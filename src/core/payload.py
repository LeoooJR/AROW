from abc import ABC, abstractmethod
from typing import Any, Self


class Payload(ABC):
    """
    Abstract base class for payload objects.

    A payload is any object whose state must be
    serialized—converted between an in-memory Python representation and a
    dictionary suitable for writing to or reading from the file system.

    Classes inheriting from `Payload` are responsible for fully defining
    how their data is serialized to a dictionary for persistence, and
    deserialized back from such a dictionary for use in memory.
    This ensures round-trip consistency between runtime objects and their
    stable file-based representations.
    """

    @abstractmethod
    def serialize(self, **kwargs) -> dict[str, Any]:
        """
        Serialize the object's current state into a dictionary form suitable
        for writing to disk or other storage.
        """
        ...

    @classmethod
    @abstractmethod
    def deserialize(cls, payload: dict[str, Any], **kwargs) -> Self:
        """
        Populate an object from a dictionary form (typically loaded from
        disk or external storage).

        Args:
            payload: The dictionary representation of the object to restore from.
            **kwargs: Additional keyword arguments to pass to the constructor.
        """
        ...
