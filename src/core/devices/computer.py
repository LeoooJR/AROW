"""Computer model, identity helper, and repository."""

from __future__ import annotations

import datetime
import platform
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from core.collection import Repository
from core.devices.base import Device, DeviceDescriptor
from core.network import is_non_loopback_ipv4, resolve_network_identity

_STABLE_PC_INSTALL_PREFIX = "pc:v1:install:"


def compute_computer_stable_key(install_token: str) -> str:
    """Return the persisted-install-based logical host identity."""
    token = (install_token or "").strip()
    return f"{_STABLE_PC_INSTALL_PREFIX}{token.casefold()}" if token else ""


@dataclass(unsafe_hash=True, match_args=True)
class ComputerDescriptor(DeviceDescriptor):
    """Metadata about the host computer."""

    state: Optional[str] = field(
        metadata={"description": "The state of the computer"},
        default=None,
        compare=False,
        hash=False,
    )
    last_communication: Optional[datetime.datetime] = field(
        metadata={"description": "The last communication time of the computer"},
        default=None,
        compare=False,
        hash=False,
    )
    stable_key: str = field(
        metadata={"description": "Stable install-scoped host identity"},
        default="",
        hash=True,
    )
    network_available: bool = field(
        metadata={
            "description": "Whether the host has a usable non-loopback IPv4 address"
        },
        default=False,
        compare=False,
        hash=False,
    )

    def __str__(self) -> str:
        return f"{self.id} - {self.name} - {self.os} - {self.ip}:{self.port} - {self.state} - {self.stable_key} - {self.network_available} - {self.last_communication}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id}, name={self.name}, os={self.os}, ip={self.ip}, port={self.port}, state={self.state}, stable_key={self.stable_key!r}, network_available={self.network_available!r}, last_communication={self.last_communication})"


class Computer(Device[ComputerDescriptor]):
    """Host computer device."""

    def __init__(
        self,
        id: str,
        name: str | None = None,
        os: str | None = None,
        ip: str | None = None,
        port: int | None = None,
        state: str | None = None,
        last_communication: datetime.datetime | None = None,
    ) -> None:
        """Initialize the host computer and resolve missing local metadata.

        Args:
            id: Stable runtime identifier for the host.
            name: Host name, or ``None`` to use the platform node name.
            os: Operating-system name, or ``None`` to detect it.
            ip: Host IP address, or ``None`` to resolve the network identity.
            port: Optional host communication port.
            state: Optional host connection state.
            last_communication: Time of the latest host communication.
        """
        resolved_name, resolved_os = name or platform.node(), os or platform.system()
        resolved_ip, network_available = (
            (ip, is_non_loopback_ipv4(ip))
            if ip is not None
            else self._resolve_network_identity()
        )
        descriptor = ComputerDescriptor(
            id=id,
            name=resolved_name,
            os=resolved_os.lower(),
            ip=resolved_ip,
            port=port,
            state=state,
            last_communication=last_communication,
            stable_key="",
            network_available=network_available,
        )
        super().__init__(
            id=id,
            name=resolved_name,
            os=resolved_os.lower(),
            ip=resolved_ip,
            port=port,
            descriptor=descriptor,
        )

    @property
    def stable_key(self) -> str:
        """Return the persisted install-scoped host identity."""
        return self._descriptor.stable_key

    @property
    def state(self) -> str | None:
        """Return the current host state."""
        return self._descriptor.state

    @state.setter
    def state(self, value: str | None) -> None:
        """Set the current host state."""
        self._descriptor.state = value

    @property
    def last_communication(self) -> datetime.datetime | None:
        """Return the time of the latest host communication."""
        return self._descriptor.last_communication

    @last_communication.setter
    def last_communication(self, value: datetime.datetime | None) -> None:
        """Set the time of the latest host communication."""
        self._descriptor.last_communication = value

    @property
    def network_available(self) -> bool:
        """Return whether the host has a usable network identity."""
        return self._descriptor.network_available

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Computer):
            return NotImplemented
        return self.descriptor == other.descriptor

    def __hash__(self) -> int:
        return hash(self.descriptor)

    def refresh_network_identity(self) -> None:
        """Refresh the host IP address and network availability flag."""
        self._descriptor.ip, self._descriptor.network_available = (
            self._resolve_network_identity()
        )

    def _resolve_network_identity(self) -> tuple[str, bool]:
        return resolve_network_identity()


class ComputerRepository(Repository[Computer]):
    """Repository that tracks the first added computer as its working device."""

    def __init__(self) -> None:
        """Initialize an empty repository without a working computer."""
        super().__init__()
        self._working_device: Computer | None = None

    @property
    def working_device(self) -> Computer | None:
        """Return the currently selected host computer."""
        return self.__dict__.get("_working_device", None)

    @working_device.setter
    def working_device(self, device: Computer) -> None:
        """Set the currently selected host computer."""
        self._working_device = device

    def add(self, item: Computer) -> None:
        """Add a computer and select the first successful addition."""
        try:
            super().add(item)
        except ValueError as error:
            logger.error("Computer could not be added to repository", error=str(error))
            return
        if self._working_device is None:
            self._working_device = item

    def remove(self, item: Computer) -> None:
        """Remove a computer and clear it when currently selected."""
        try:
            super().remove(item)
        except ValueError as error:
            logger.error(
                "Computer could not be removed from repository", error=str(error)
            )
            return
        if self._working_device == item:
            self._working_device = None
