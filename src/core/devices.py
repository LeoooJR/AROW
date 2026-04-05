import datetime
import platform
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional, Self


@dataclass
class DeviceState:
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
class PhoneState(DeviceState):
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
class ComputerState(DeviceState):
    """
    Metadata about the computer device
    """

    state: str = field(
        metadata={"description": "The state of the computer"}, default=""
    )
    last_communication: datetime.datetime = field(
        metadata={"description": "The last communication time of the computer"},
        default=datetime.datetime.now(),
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
        self._state = DeviceState(id, name, os, ip, port)

    @property
    def state(self) -> DeviceState:
        return self._state

    @state.setter
    def state(self, value: DeviceState) -> None:
        if not isinstance(value, DeviceState):
            raise TypeError("state must be an instance of DeviceState")
        self._state = value

    @property
    def id(self) -> str:
        return self._state.id

    @property
    def name(self) -> str:
        return self._state.name

    @property
    def os(self) -> str:
        return self._state.os

    @property
    def ip(self) -> str:
        return self._state.ip

    @property
    def port(self) -> Optional[int]:
        return self._state.port

    def update_state(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self._state, key, value)

    @classmethod
    @abstractmethod
    def from_string(cls, string: str) -> Self:
        raise NotImplementedError

    def __str__(self):
        return f"{self._state.name} - {self._state.os} - {self._state.ip}:{self._state.port}"

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self._state.id}, name={self._state.name}, os={self._state.os}, ip={self._state.ip}, port={self._state.port})"


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
        self.state = PhoneState(
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
        return self._state.product

    @property
    def model(self) -> str:
        return self._state.model

    @property
    def state(self) -> str:
        return self._state.state

    @state.setter
    def state(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("state must be a string")
        self._state.state = value

    @property
    def last_communication(self) -> datetime.datetime:
        return self._state.last_communication

    @last_communication.setter
    def last_communication(self, value: datetime.datetime) -> None:
        if not isinstance(value, datetime.datetime):
            raise TypeError("last_communication must be a datetime")
        self._state.last_communication = value

    @property
    def transport_id(self) -> str:
        return self._state.transport_id

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
        resolved_ip = ip if ip is not None else self._get_ip()
        super().__init__(
            id=id,
            name=resolved_name,
            os=resolved_os,
            ip=resolved_ip,
            port=port,
        )
        self.state = ComputerState(
            id=id,
            name=resolved_name,
            os=resolved_os,
            ip=resolved_ip,
            port=port,
            state=state,
            last_communication=last_communication,
        )

    def _get_ip(self) -> str:
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


class DeviceRepository(ABC):
    """
    Device repository
    """

    def __init__(self):
        self._devices: dict[str, Device] = {}
        self._working_device: Device | None = None

    @property
    def working_device(self) -> Device | None:
        return self.__dict__.get("_working_device", None)

    @working_device.setter
    def working_device(self, device: Device) -> None:
        self._working_device = device

    def add_device(self, device: Device) -> None:
        if device.state.id in self._devices:
            raise ValueError(f"Device with id {device.state.id} already exists")
        self._devices[device.state.id] = device
        if self._working_device is None:
            self._working_device = device

    def remove_device(self, device: Device) -> None:
        self._devices.pop(device.state.id)
        if self._working_device == device:
            self._working_device = None

    def get_all_devices(self) -> dict[str, Device]:
        return self._devices

    def get_device(self, id: str) -> Device | None:
        return self._devices.get(id, None)

    def __iter__(self) -> Iterator[Device]:
        return iter(self._devices.values())

    def __len__(self) -> int:
        return len(self._devices)

    def __contains__(self, device: Device) -> bool:
        return device.state.id in self._devices

    def __getitem__(self, id: str) -> Device:
        return self._devices[id]

    def __setitem__(self, id: str, device: Device) -> None:
        self._devices[id] = device

    def __delitem__(self, id: str) -> None:
        self._devices.pop(id)


class PhoneRepository(DeviceRepository):
    """
    Phone repository
    """

    def __init__(self):
        super().__init__()

    def add_phone(self, phone: Phone) -> None:
        super().add_device(phone)

    def remove_phone(self, phone: Phone) -> None:
        super().remove_device(phone)

    def get_all_phones(self) -> dict[str, Phone]:
        return {
            k: v for k, v in super().get_all_devices().items() if isinstance(v, Phone)
        }

    def get_phone(self, id: str) -> Phone | None:
        device = super().get_device(id)
        return device if isinstance(device, Phone) else None


class ComputerRepository(DeviceRepository):
    """
    Computer repository
    """

    def __init__(self):
        super().__init__()

    def add_computer(self, computer: Computer) -> None:
        super().add_device(computer)

    def remove_computer(self, computer: Computer) -> None:
        super().remove_device(computer)

    def get_all_computers(self) -> dict[str, Computer]:
        return {
            k: v
            for k, v in super().get_all_devices().items()
            if isinstance(v, Computer)
        }

    def get_computer(self, id: str) -> Computer | None:
        device = super().get_device(id)
        return device if isinstance(device, Computer) else None
