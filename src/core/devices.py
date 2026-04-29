import datetime
import hashlib
import platform
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Self

from collection import Repository

# Prefixes so stored keys remain version-migratable and distinguish Tier 1 vs Tier 2.
_STABLE_HW_PREFIX = "hw:v1:"
_STABLE_FP_PREFIX = "fp:v1:"
_FINGERPRINT_V1_MARKER = "|fp|v1|"


def _tier1_stable_key_from_serial(normalized_serial: str) -> str:
    """Build Tier-1 stable key from ro.serialno text (caller validates)."""
    return f"{_STABLE_HW_PREFIX}{normalized_serial}"


def _tier2_stable_key(product: str, model: str, manufacturer: Optional[str]) -> str:
    """
    deterministic fingerprint when ro.serialno is unavailable; collisions possible across
    identical devices (documented limitation).
    """
    man = manufacturer or ""
    payload = (
        _FINGERPRINT_V1_MARKER
        + (man.strip().lower())
        + "|"
        + product.strip().lower()
        + "|"
        + model.strip().lower()
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{_STABLE_FP_PREFIX}{digest}"


def compute_phone_stable_key(
    *,
    hardware_serial: Optional[str],
    product: str,
    model: str,
    manufacturer: Optional[str] = None,
    fingerprint_when_no_serial: bool = False,
) -> str:
    """
    Stable logical identity for stats / reconciliation across ADB reconnects.

    **Tier 1:** ``ro.serialno`` from ``adb shell getprop ro.serialno`` (non-empty, not ``unknown``).
    **Tier 2:** Only when ``fingerprint_when_no_serial`` is True and Tier 1 is unavailable:
    salted SHA-256 over manufacturer + product + model (may collide for identical SKUs).

    From ``devices -l`` only (before enrichment), omit fingerprint so the key stays empty until serial is fetched.
    """
    if hardware_serial:
        cand = hardware_serial.strip()
        if cand and cand.casefold() != "unknown":
            return _tier1_stable_key_from_serial(cand)
    if fingerprint_when_no_serial and (
        product.strip() or model.strip() or (manufacturer or "").strip()
    ):
        return _tier2_stable_key(product, model, manufacturer)
    return ""


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
        default_factory=datetime.datetime.now,
    )
    hardware_serial: str = field(
        metadata={
            "description": "ro.serialno from the device after enrichment (not the ADB connection id)"
        },
        default="",
    )
    stable_key: str = field(
        metadata={
            "description": "Stable logical identity across ADB reconnects (hw or fingerprint Tier)"
        },
        default="",
    )
    manufacturer: str = field(
        metadata={
            "description": "Hardware manufacturer label if filled (optional; improves Tier-2 fingerprints)"
        },
        default="",
    )

    def __str__(self):
        return (
            f"{self.id} - {self.name} - {self.os} - {self.ip}:{self.port} - "
            f"{self.product} - {self.model} - {self.transport_id} - {self.state} - "
            f"{self.hardware_serial} - {self.stable_key} - {self.last_communication}"
        )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(id={self.id}, name={self.name}, os={self.os}, "
            f"ip={self.ip}, port={self.port}, product={self.product}, model={self.model}, "
            f"transport_id={self.transport_id}, state={self.state}, "
            f"hardware_serial={self.hardware_serial!r}, stable_key={self.stable_key!r}, "
            f"last_communication={self.last_communication})"
        )


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
        hardware_serial: str | None = None,
        manufacturer: str | None = None,
    ) -> None:
        super().__init__(
            id=id,
            name=name,
            os=os or "",
            ip=ip or "",
            port=port,
        )
        prod = product or ""
        mod = model or ""
        man_u = manufacturer or ""
        hs = (hardware_serial.strip() if hardware_serial else "") or ""
        stable = compute_phone_stable_key(
            hardware_serial=hs if hs else None,
            product=prod,
            model=mod,
            manufacturer=man_u if man_u.strip() else None,
            fingerprint_when_no_serial=False,
        )
        self._descriptor: PhoneDescriptor = PhoneDescriptor(
            id=id,
            name=name,
            os=os or "",
            ip=ip or "",
            port=port,
            product=prod,
            model=mod,
            state=state or "",
            last_communication=datetime.datetime.now(),
            hardware_serial=hs if hs else "",
            stable_key=stable,
            manufacturer=man_u,
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

    @property
    def stable_key(self) -> str:
        return self._descriptor.stable_key

    @property
    def hardware_serial(self) -> str:
        return self._descriptor.hardware_serial

    @classmethod
    def from_string(cls, string: str) -> Self:
        id, state, product, model, device, transport_id = string.strip().split()
        return cls(id=id, name=device, product=product, model=model, state=state)


def apply_phone_ro_serial_enrichment(phone: Phone, ro_serial_stdout: str) -> None:
    """
    After ``adb shell getprop ro.serialno``, update ``hardware_serial`` and ``stable_key``.

    When stdout is blank or unusable (or ``unknown``), keeps prior ``hardware_serial`` if set;
    recomputes ``stable_key`` with Tier 2 fingerprint if Tier 1 is still unavailable.
    """
    raw = (ro_serial_stdout or "").strip()
    if raw and raw.casefold() != "unknown":
        phone.descriptor.hardware_serial = raw
    man = (phone.descriptor.manufacturer or "").strip()
    hs = (phone.descriptor.hardware_serial or "").strip()
    phone.descriptor.stable_key = compute_phone_stable_key(
        hardware_serial=hs if hs else None,
        product=phone.descriptor.product,
        model=phone.descriptor.model,
        manufacturer=man or None if man else None,
        fingerprint_when_no_serial=True,
    )


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
            os=resolved_os.lower(),
            ip=resolved_ip,
            port=port,
        )
        self.descriptor = ComputerDescriptor(
            id=id,
            name=resolved_name,
            os=resolved_os.lower(),
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
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if not ip.startswith("127."):  # 127.0.0.1 is the loopback address
                return ip
        except OSError:
            pass

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # 8.8.8.8 is a public DNS server
            ip = s.getsockname()[0]
            s.close()
            return ip
        except OSError:
            return "127.0.0.1"  # fallback to loopback address

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
