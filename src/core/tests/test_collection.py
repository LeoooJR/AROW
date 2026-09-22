"""Tests for identity ownership in the generic repository."""

from dataclasses import dataclass

import pytest

from core.collection import Repository


@dataclass
class _Item:
    id: str


def test_repository_membership_requires_the_stored_instance() -> None:
    repository = Repository[_Item]()
    stored = _Item(id="item-1")
    same_id_clone = _Item(id="item-1")
    repository.add(stored)

    assert stored in repository
    assert same_id_clone not in repository
    assert repository.get("item-1") is stored


def test_repository_rejects_removing_a_same_id_clone() -> None:
    repository = Repository[_Item]()
    stored = _Item(id="item-1")
    repository.add(stored)

    with pytest.raises(ValueError, match="not the stored repository instance"):
        repository.remove(_Item(id="item-1"))

    assert repository.get("item-1") is stored


def test_repository_distinguishes_missing_items_and_removes_the_stored_instance() -> (
    None
):
    repository = Repository[_Item]()
    stored = _Item(id="item-1")
    repository.add(stored)

    with pytest.raises(ValueError, match="does not exist"):
        repository.remove(_Item(id="missing"))

    repository.remove(stored)

    assert repository.get("item-1") is None
    assert len(repository) == 0
