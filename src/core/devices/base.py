"""Shared device model primitives."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Generic, TypeVar


@dataclass(frozen=True, match_args=True)
class DeviceDescriptor:
    """Metadata common to every device."""

    __hash__ = None  # type: ignore[assignment]

    name: str = field(
        metadata={
            "description": "The name of the device. This value is displayed to the user and should be human readable."
        },
        default="",
    )
    os: str = field(
        metadata={"description": "The operating system of the device"}, default=""
    )


D = TypeVar("D", bound=DeviceDescriptor)


class Device(ABC, Generic[D]):
    """Base device backed by a typed descriptor."""

    _descriptor: D

    def __init__(self, *, descriptor: D) -> None:
        """Initialize a device from its typed descriptor snapshot.

        Args:
            descriptor: Typed descriptor that owns the device state.
        """
        self._descriptor = descriptor

    @property
    def descriptor(self) -> D:
        """Return the typed descriptor that owns the device state."""
        return self._descriptor

    @property
    def name(self) -> str:
        """Return the user-facing device name."""
        return self._descriptor.name

    @property
    def os(self) -> str:
        """Return the device operating-system name or version."""
        return self._descriptor.os

    def __str__(self) -> str:
        return f"{self._descriptor.name} - {self._descriptor.os}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self._descriptor.name!r}, os={self._descriptor.os!r})"

    def __eq__(self, other: object) -> bool:
        """Compare devices by instance identity.

        Mutable device aggregates are deliberately unhashable. Logical identity belongs
        to immutable stable-key values rather than to the aggregate itself.
        """
        return self is other
