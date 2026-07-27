from abc import ABC
from typing import Generic, Iterator, Protocol, TypeVar

from loguru import logger


class Identifiable(Protocol):
    """Objects stored in a repository must expose a stable string id."""

    @property
    def id(self) -> str: ...


RepositoryObject = TypeVar("RepositoryObject", bound=Identifiable)


class Repository(ABC, Generic[RepositoryObject]):
    """Repository for the collection."""

    def __init__(self) -> None:
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
            "Repository item added",
            repository_type=self.__class__.__name__,
            item_id=item.id,
            item_count=len(self._repository),
        )

    def add_all(self, items: list[RepositoryObject]) -> None:
        """Add all items to the repository."""
        for item in items:
            self.add(item)
        logger.debug(
            "Repository items added",
            repository_type=self.__class__.__name__,
            added_count=len(items),
            item_count=len(self._repository),
        )

    def remove(self, item: RepositoryObject) -> None:
        """Remove an item from the repository."""
        if item.id not in self._repository:
            raise ValueError(f"Item with id {item.id} does not exist")
        self._repository.pop(item.id)
        logger.debug(
            "Repository item removed",
            repository_type=self.__class__.__name__,
            item_id=item.id,
            item_count=len(self._repository),
        )

    def clear(self) -> None:
        """Clear the repository."""
        self._repository.clear()
        logger.debug(
            "Repository cleared",
            repository_type=self.__class__.__name__,
            item_count=0,
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
