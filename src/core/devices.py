import datetime
import platform
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Self

from collection import Repository


@dataclass
class DeviceDescriptor:
    """
    Metadata about the device
    """

    id: str = field(metadata={"description": "The id of the device"}, default="")
    name: str = field(metadata={"description": "The name of the device"}, default="")
    os: str = field(
        metadata={"description": "The operating system of the device"}, default=""
    )
    ip: str = field(
        metadata={"description": "The ip address of the device"}, default=""
    )
    port: Optional[int] = field(
        metadata={"description": "The port of the device"}, default=None
    )


@dataclass
class PhoneDescriptor(DeviceDescriptor):
    """
    Metadata about the phone device
    """

    product: str = field(
        metadata={"description": "The product of the phone"}, default=""
    )
    model: str = field(metadata={"description": "The model of the phone"}, default="")
    transport_id: str = field(
        metadata={"description": "The transport id of the phone"}, default=""
    )
    state: str = field(metadata={"description": "The state of the phone"}, default="")
    last_communication: datetime.datetime = field(
        metadata={"description": "The last communication time of the phone"},
        default=datetime.datetime.now(),
    )

    def __str__(self):
        return f"{self.id} - {self.name} - {self.os} - {self.ip}:{self.port} - {self.product} - {self.model} - {self.transport_id} - {self.state} - {self.last_communication}"

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id}, name={self.name}, os={self.os}, ip={self.ip}, port={self.port}, product={self.product}, model={self.model}, transport_id={self.transport_id}, state={self.state}, last_communication={self.last_communication})"


@dataclass
class ComputerDescriptor(DeviceDescriptor):
    """
    Metadata about the computer device
    """

    state: Optional[str] = field(
        metadata={"description": "The state of the computer"}, default=None
    )
    last_communication: Optional[datetime.datetime] = field(
        metadata={"description": "The last communication time of the computer"},
        default=None,
    )

    def __str__(self):
        return f"{self.id} - {self.name} - {self.os} - {self.ip}:{self.port} - {self.state} - {self.last_communication}"

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id}, name={self.name}, os={self.os}, ip={self.ip}, port={self.port}, state={self.state}, last_communication={self.last_communication})"


class Device(ABC):
    """
    Device
    """

    def __init__(
        self,
        id: str,
        name: str,
        os: str,
        ip: str,
        port: Optional[int],
    ) -> None:
        self._descriptor = DeviceDescriptor(id, name, os, ip, port)

    @property
    def descriptor(self) -> DeviceDescriptor:
        return self._descriptor

    @descriptor.setter
    def descriptor(self, value: DeviceDescriptor) -> None:
        if not isinstance(value, DeviceDescriptor):
            raise TypeError("descriptor must be an instance of DeviceDescriptor")
        self._descriptor = value

    @property
    def id(self) -> str:
        return self._descriptor.id

    @property
    def name(self) -> str:
        return self._descriptor.name

    @property
    def os(self) -> str:
        return self._descriptor.os

    @property
    def ip(self) -> str:
        return self._descriptor.ip

    @property
    def port(self) -> Optional[int]:
        return self._descriptor.port

    def update_state(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self._descriptor, key, value)

    @classmethod
    @abstractmethod
    def from_string(cls, string: str) -> Self:
        raise NotImplementedError

    def __str__(self):
        return f"{self._descriptor.name} - {self._descriptor.os} - {self._descriptor.ip}:{self._descriptor.port}"

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self._descriptor.id}, name={self._descriptor.name}, os={self._descriptor.os}, ip={self._descriptor.ip}, port={self._descriptor.port})"


class Phone(Device):
    """
    Phone device
    """

    def __init__(
        self,
        id: str,
        name: str,
        os: str | None = None,
        ip: str | None = None,
        port: int | None = None,
        product: str | None = None,
        model: str | None = None,
        state: str | None = None,
    ) -> None:
        super().__init__(
            id=id,
            name=name,
            os=os or "",
            ip=ip or "",
            port=port,
        )
        self._descriptor: PhoneDescriptor = PhoneDescriptor(
            id=id,
            name=name,
            os=os or "",
            ip=ip or "",
            port=port,
            product=product or "",
            model=model or "",
            state=state or "",
            last_communication=datetime.datetime.now(),
        )

    @property
    def product(self) -> str:
        return self._descriptor.product

    @property
    def descriptor(self) -> PhoneDescriptor:
        return self._descriptor

    @descriptor.setter
    def descriptor(self, value: PhoneDescriptor) -> None:
        if not isinstance(value, PhoneDescriptor):
            raise TypeError("descriptor must be an instance of PhoneDescriptor")
        self._descriptor = value

    @property
    def state(self) -> str:
        return self._descriptor.state

    @state.setter
    def state(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("state must be a string")
        self._descriptor.state = value

    @property
    def model(self) -> str:
        return self._descriptor.model

    @property
    def last_communication(self) -> datetime.datetime:
        return self._descriptor.last_communication

    @last_communication.setter
    def last_communication(self, value: datetime.datetime) -> None:
        if not isinstance(value, datetime.datetime):
            raise TypeError("last_communication must be a datetime")
        self._descriptor.last_communication = value

    @property
    def transport_id(self) -> str:
        return self._descriptor.transport_id

    @classmethod
    def from_string(cls, string: str) -> Self:
        id, state, product, model, device, transport_id = string.strip().split()
        return cls(id=id, name=device, product=product, model=model, state=state)


class Computer(Device):
    """
    Computer device
    """

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
        resolved_name = name or platform.node()
        resolved_os = os or platform.system()
        resolved_ip = ip if ip is not None else self._resolve_ip()
        super().__init__(
            id=id,
            name=resolved_name,
            os=resolved_os,
            ip=resolved_ip,
            port=port,
        )
        self.descriptor = ComputerDescriptor(
            id=id,
            name=resolved_name,
            os=resolved_os,
            ip=resolved_ip,
            port=port,
            state=state,
            last_communication=last_communication,
        )

    def get_name(self) -> str:
        return self._descriptor.name

    def get_os(self) -> str:
        return self._descriptor.os

    def get_ip(self) -> str:
        return self._descriptor.ip

    def get_port(self) -> int:
        return self._descriptor.port

    def get_state(self) -> str:
        return self._descriptor.state

    def get_last_communication(self) -> datetime.datetime:
        return self._descriptor.last_communication

    def _resolve_ip(self) -> str:
        ip = socket.gethostbyname(socket.gethostname())
        if ip.startswith("127."):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        return ip

    @classmethod
    def from_string(cls, string: str) -> Self:
        raise NotImplementedError("Computer.from_string is not implemented yet.")


def connect_to_device(ip: str, port: int, association_code: str) -> Phone:
    """
    Connect to a device
    """
    return Phone(id="", name="", os="", ip=ip, port=port, state="")


class PhoneRepository(Repository[Phone]):
    """
    Phone repository. Tracks a working device: the first added phone is selected until cleared.
    """

    def __init__(self) -> None:
        super().__init__()
        self._working_device: Phone | None = None

    @property
    def working_device(self) -> Phone | None:
        return self.__dict__.get("_working_device", None)

    @working_device.setter
    def working_device(self, device: Phone) -> None:
        self._working_device = device

    def add(self, item: Phone) -> None:
        super().add(item)
        if self._working_device is None:
            self._working_device = item

    def remove(self, item: Phone) -> None:
        super().remove(item)
        if self._working_device == item:
            self._working_device = None


class ComputerRepository(Repository[Computer]):
    """
    Computer repository. Tracks a working device: the first added computer is selected until cleared.
    """

    def __init__(self) -> None:
        super().__init__()
        self._working_device: Computer | None = None

    @property
    def working_device(self) -> Computer | None:
        return self.__dict__.get("_working_device", None)

    @working_device.setter
    def working_device(self, device: Computer) -> None:
        self._working_device = device

    def add(self, item: Computer) -> None:
        super().add(item)
        if self._working_device is None:
            self._working_device = item

    def remove(self, item: Computer) -> None:
        super().remove(item)
        if self._working_device == item:
            self._working_device = None
