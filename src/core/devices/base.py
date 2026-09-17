"""Shared device model primitives."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Generic, Optional, TypeVar


@dataclass(frozen=True, match_args=True)
class DeviceDescriptor:
    """Metadata common to every device."""

    __hash__ = None  # type: ignore[assignment]

    id: str = field(metadata={"description": "The id of the device"}, default="")
    name: str = field(
        metadata={
            "description": "The name of the device. This value is displayed to the user and should be human readable."
        },
        default="",
    )
    os: str = field(
        metadata={"description": "The operating system of the device"}, default=""
    )
    ip: str = field(
        metadata={"description": "The ip address of the device"}, default=""
    )
    port: Optional[int] = field(
        metadata={"description": "The port of the device"}, default=None
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
    def id(self) -> str:
        """Return the device identifier."""
        return self._descriptor.id

    @property
    def name(self) -> str:
        """Return the user-facing device name."""
        return self._descriptor.name

    @property
    def os(self) -> str:
        """Return the device operating-system name or version."""
        return self._descriptor.os

    @property
    def ip(self) -> str:
        """Return the device IP address."""
        return self._descriptor.ip

    @property
    def port(self) -> Optional[int]:
        """Return the device network port, if available."""
        return self._descriptor.port

    def __str__(self) -> str:
        return f"{self._descriptor.name} - {self._descriptor.os} - {self._descriptor.ip}:{self._descriptor.port}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._descriptor.id}, name={self._descriptor.name}, os={self._descriptor.os}, ip={self._descriptor.ip}, port={self._descriptor.port})"

    def __eq__(self, other: object) -> bool:
        """Compare devices by instance identity.

        Mutable device aggregates are deliberately unhashable. Logical identity belongs
        to immutable stable-key values rather than to the aggregate itself.
        """
        return self is other
