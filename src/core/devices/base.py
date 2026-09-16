"""Shared device model primitives."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar


@dataclass(unsafe_hash=True, match_args=True)
class DeviceDescriptor:
    """Metadata common to every device."""

    id: str = field(
        metadata={"description": "The id of the device"}, default="", hash=True
    )
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

    def __init__(
        self,
        id: str,
        name: str,
        os: str,
        ip: str,
        port: Optional[int],
        *,
        descriptor: D,
    ) -> None:
        """Initialize a device from its typed descriptor.

        Args:
            id: Device identifier retained for constructor compatibility.
            name: Display name retained for constructor compatibility.
            os: Operating system retained for constructor compatibility.
            ip: IP address retained for constructor compatibility.
            port: Network port retained for constructor compatibility.
            descriptor: Typed descriptor that owns the device state.
        """
        self._descriptor = descriptor

    @property
    def descriptor(self) -> D:
        """Return the typed descriptor that owns the device state."""
        return self._descriptor

    @descriptor.setter
    def descriptor(self, value: D) -> None:
        """Replace the device descriptor.

        Args:
            value: Descriptor to bind to the device.

        Raises:
            TypeError: If ``value`` is not a device descriptor.
        """
        if not isinstance(value, DeviceDescriptor):
            raise TypeError("descriptor must be an instance of DeviceDescriptor")
        self._descriptor = value

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

    def update_state(self, **kwargs: Any) -> None:
        """Update descriptor fields from keyword arguments.

        Args:
            **kwargs: Descriptor field names and their new values.
        """
        for key, value in kwargs.items():
            setattr(self._descriptor, key, value)

    def __str__(self) -> str:
        return f"{self._descriptor.name} - {self._descriptor.os} - {self._descriptor.ip}:{self._descriptor.port}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._descriptor.id}, name={self._descriptor.name}, os={self._descriptor.os}, ip={self._descriptor.ip}, port={self._descriptor.port})"

    def __hash__(self) -> int:
        return hash(self._descriptor)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Device) and self._descriptor == other._descriptor
