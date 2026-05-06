from abc import ABC
from pprint import pformat
from typing import Generic, Iterator, TypeVar

from loguru import logger

RepositoryObject = TypeVar("RepositoryObject")


class Repository(ABC, Generic[RepositoryObject]):
    """Repository for the collection."""

    def __init__(self):
        self._repository: dict[str, RepositoryObject] = dict()

    def get(self, id: str) -> RepositoryObject | None:
        """Get the item for the repository."""
        return self._repository.get(id, None)

    def add(self, item: RepositoryObject) -> None:
        """Add an item to the repository."""
        if item.id in self._repository:
            raise ValueError(f"Item with id {item.id} already exists")
        self._repository[item.id] = item
        logger.debug(
            "{}.add: repository snapshot ({} item(s))\n{}",
            self.__class__.__name__,
            len(self._repository),
            pformat(self._repository),
        )

    def remove(self, item: RepositoryObject) -> None:
        """Remove an item from the repository."""
        if item.id not in self._repository:
            raise ValueError(f"Item with id {item.id} does not exist")
        self._repository.pop(item.id)
        logger.debug(
            "{}.remove: repository snapshot ({} item(s))\n{}",
            self.__class__.__name__,
            len(self._repository),
            pformat(self._repository),
        )

    def __len__(self) -> int:
        """Get the number of items in the repository."""
        return len(self._repository)

    def __iter__(self) -> Iterator[RepositoryObject]:
        """Iterate over the items in the repository."""
        return iter(self._repository.values())

    def __contains__(self, item: RepositoryObject) -> bool:
        """Check if an item is in the repository."""
        return item.id in self._repository
