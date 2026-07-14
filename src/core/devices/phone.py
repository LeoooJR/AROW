"""Android phone model, identity helpers, and repository."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Iterable

from loguru import logger

from core.collection import Repository
from core.devices.base import Device, DeviceDescriptor
from core.devices.stable_key import compute_phone_stable_key
from core.payload import Payload

DEFAULT_PHONE_DISPLAY_NAME = "Android device"
_PHONE_DISPLAY_ID_TAIL_LEN = 8


def _adb_connection_id_is_human_readable(connection_id: str) -> bool:
    cid = connection_id.strip()
    if not cid:
        return False
    if cid.startswith("emulator-"):
        return True
    if "." in cid:
        return False
    return len(cid) <= 24


@dataclass(unsafe_hash=True, match_args=True)
class PhoneDescriptor(DeviceDescriptor):
    """Metadata about an Android phone."""

    product: str = field(
        metadata={"description": "The product of the phone"}, default=""
    )
    model: str = field(metadata={"description": "The model of the phone"}, default="")
    device: str = field(
        metadata={"description": "The device column from adb devices -l"}, default=""
    )
    transport_id: str = field(
        metadata={"description": "The transport id of the phone"}, default=""
    )
    state: str = field(metadata={"description": "The state of the phone"}, default="")
    last_communication: datetime.datetime = field(
        metadata={"description": "The last communication time of the phone"},
        default_factory=datetime.datetime.now,
    )
    hardware_serial: str = field(
        metadata={"description": "ro.serialno after enrichment"}, default=""
    )
    stable_key: str = field(
        metadata={"description": "Stable logical phone identity"}, default="", hash=True
    )
    manufacturer: str = field(
        metadata={"description": "Hardware manufacturer"}, default=""
    )
    android_api_level: int | None = field(
        metadata={"description": "Android API level"}, default=None
    )
    shell_device_name: str = field(
        metadata={"description": "Friendly getprop device name"}, default="", hash=False
    )

    def __str__(self) -> str:
        return f"{self.id} - {self.name} - {self.os} - {self.ip}:{self.port} - {self.product} - {self.model} - {self.transport_id} - {self.state} - {self.hardware_serial} - {self.stable_key} - {self.manufacturer} - {self.android_api_level} - {self.last_communication}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id}, name={self.name}, os={self.os}, ip={self.ip}, port={self.port}, product={self.product}, model={self.model}, transport_id={self.transport_id}, state={self.state}, hardware_serial={self.hardware_serial!r}, stable_key={self.stable_key!r}, manufacturer={self.manufacturer!r}, android_api_level={self.android_api_level!r}, shell_device_name={self.shell_device_name!r}, last_communication={self.last_communication})"


class Phone(Device[PhoneDescriptor], Payload):
    """Android phone device."""

    def __init__(
        self,
        id: str,
        name: str | None = None,
        os: str | None = None,
        ip: str | None = None,
        port: int | None = None,
        device: str | None = None,
        product: str | None = None,
        model: str | None = None,
        state: str | None = None,
        hardware_serial: str | None = None,
        manufacturer: str | None = None,
        transport_id: str | None = None,
        android_api_level: int | None = None,
    ) -> None:
        prod, mod, man = product or "", model or "", manufacturer or ""
        serial = (hardware_serial.strip() if hardware_serial else "") or ""
        device_column = (device.strip() if device else "") or ""
        if not device_column and name:
            device_column = name.strip()
        stable_key = compute_phone_stable_key(
            hardware_serial=serial or None,
            product=prod,
            model=mod,
            manufacturer=man.strip() or None,
        )
        descriptor = PhoneDescriptor(
            id=id,
            name="",
            os=os or "",
            ip=ip or "",
            port=port,
            product=prod,
            model=mod,
            device=device_column,
            transport_id=(transport_id.strip() if transport_id else "") or "",
            state=state or "",
            last_communication=datetime.datetime.now(),
            hardware_serial=serial,
            stable_key=stable_key.value if stable_key is not None else "",
            manufacturer=man,
            android_api_level=android_api_level,
            shell_device_name="",
        )
        super().__init__(
            id=id, name="", os=os or "", ip=ip or "", port=port, descriptor=descriptor
        )
        sync_phone_display_name(self)

    @property
    def product(self) -> str:
        return self._descriptor.product

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

    @property
    def manufacturer(self) -> str:
        return self._descriptor.manufacturer

    @property
    def android_api_level(self) -> int | None:
        return self._descriptor.android_api_level

    @property
    def shell_device_name(self) -> str:
        return self._descriptor.shell_device_name

    def serialize(self, **kwargs: object) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "os": self.os,
            "ip": self.ip,
            "port": self.port,
            "state": self.state,
            "stable_key": self.stable_key,
            "last_communication": (
                self.last_communication.isoformat()
                if kwargs.get("json_compatible", False)
                else self.last_communication
            ),
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs: object) -> Phone:
        port_raw = payload.get("port")
        port = (
            port_raw
            if isinstance(port_raw, int)
            else (
                int(port_raw)
                if isinstance(port_raw, str) and port_raw.strip()
                else None
            )
        )
        value = payload.get("last_communication")
        last_communication = (
            datetime.datetime.fromisoformat(value)
            if isinstance(value, str) and value.strip()
            else value if isinstance(value, datetime.datetime) else None
        )
        phone = cls(
            id=str(payload["id"]),
            name=str(payload["name"]) if payload.get("name") is not None else None,
            os=str(payload["os"]) if payload.get("os") is not None else None,
            ip=str(payload["ip"]) if payload.get("ip") is not None else None,
            port=port,
            state=str(payload["state"]) if payload.get("state") is not None else None,
        )
        if payload.get("stable_key") is not None:
            phone.descriptor.stable_key = str(payload["stable_key"])
        if last_communication is not None:
            phone.descriptor.last_communication = last_communication
        return phone


def serialize_phone_collection(phones: Iterable[Phone]) -> list[dict[str, object]]:
    return [phone.serialize(json_compatible=False) for phone in phones]


_DISCOVERED_PHONE_DESCRIPTOR_FIELDS = (
    "name",
    "os",
    "ip",
    "port",
    "product",
    "model",
    "device",
    "transport_id",
    "state",
    "hardware_serial",
    "stable_key",
    "manufacturer",
    "android_api_level",
    "shell_device_name",
)


def apply_discovered_phone_state(paired: Phone, discovered: Phone) -> None:
    for field_name in _DISCOVERED_PHONE_DESCRIPTOR_FIELDS:
        setattr(
            paired.descriptor, field_name, getattr(discovered.descriptor, field_name)
        )
    paired.descriptor.id = discovered.id
    paired.descriptor.last_communication = discovered.descriptor.last_communication


def paired_phone_matches_discovery(paired: Phone, discovered: Phone) -> bool:
    return paired.id == discovered.id and all(
        getattr(paired.descriptor, name) == getattr(discovered.descriptor, name)
        for name in _DISCOVERED_PHONE_DESCRIPTOR_FIELDS
    )


def sync_phone_display_name(phone: Phone) -> None:
    descriptor = phone.descriptor
    shell, manufacturer, model, product, device = (
        (descriptor.shell_device_name or "").strip(),
        (descriptor.manufacturer or "").strip(),
        (descriptor.model or "").strip(),
        (descriptor.product or "").strip(),
        (descriptor.device or "").strip(),
    )
    if shell:
        descriptor.name = shell
    elif manufacturer and model:
        descriptor.name = f"{manufacturer} {model}"
    elif model:
        descriptor.name = model
    elif product:
        descriptor.name = product
    elif device:
        descriptor.name = device
    elif descriptor.id and _adb_connection_id_is_human_readable(descriptor.id):
        descriptor.name = descriptor.id
    elif descriptor.id and len(descriptor.id) > _PHONE_DISPLAY_ID_TAIL_LEN:
        descriptor.name = f"{DEFAULT_PHONE_DISPLAY_NAME} ({descriptor.id[-_PHONE_DISPLAY_ID_TAIL_LEN:]})"
    else:
        descriptor.name = (
            DEFAULT_PHONE_DISPLAY_NAME if not descriptor.id else descriptor.id
        )


def _recompute_phone_stable_key_descriptor(phone: Phone) -> None:
    descriptor = phone.descriptor
    manufacturer, serial = (
        descriptor.manufacturer.strip(),
        descriptor.hardware_serial.strip(),
    )
    stable_key = compute_phone_stable_key(
        hardware_serial=serial or None,
        product=descriptor.product,
        model=descriptor.model,
        manufacturer=manufacturer or None,
        fingerprint_when_no_serial=True,
    )
    descriptor.stable_key = stable_key.value if stable_key is not None else ""


def apply_phone_ro_serial_enrichment(phone: Phone, ro_serial_stdout: str) -> None:
    raw = (ro_serial_stdout or "").strip()
    if raw and raw.casefold() != "unknown":
        phone.descriptor.hardware_serial = raw
    _recompute_phone_stable_key_descriptor(phone)


def apply_phone_device_name_enrichment(phone: Phone, value: str) -> None:
    phone.descriptor.shell_device_name = (value or "").strip()
    sync_phone_display_name(phone)
    _recompute_phone_stable_key_descriptor(phone)


def apply_phone_android_release_enrichment(phone: Phone, value: str) -> None:
    value = (value or "").strip()
    if value:
        phone.descriptor.os = value
        _recompute_phone_stable_key_descriptor(phone)


def apply_phone_manufacturer_enrichment(phone: Phone, value: str) -> None:
    value = (value or "").strip()
    if value:
        phone.descriptor.manufacturer = value
        sync_phone_display_name(phone)
        _recompute_phone_stable_key_descriptor(phone)


def apply_phone_product_model_enrichment(phone: Phone, value: str) -> None:
    value = (value or "").strip()
    if value:
        phone.descriptor.model = value
        sync_phone_display_name(phone)
        _recompute_phone_stable_key_descriptor(phone)


def apply_phone_android_api_level_enrichment(phone: Phone, value: int | None) -> None:
    if value is not None:
        phone.descriptor.android_api_level = value
        _recompute_phone_stable_key_descriptor(phone)


class PhoneRepository(Repository[Phone]):
    """Repository that tracks the first added phone as its working device."""

    def __init__(self) -> None:
        super().__init__()
        self._working_device: Phone | None = None

    @property
    def working_device(self) -> Phone | None:
        return self.__dict__.get("_working_device", None)

    @working_device.setter
    def working_device(self, device: Phone | None) -> None:
        if device is None:
            self._working_device = None
        elif device.id in self._repository:
            self._working_device = device
        else:
            raise ValueError(f"Device with id {device.id} is not in the repository")

    def add(self, item: Phone) -> None:
        try:
            super().add(item)
        except ValueError as error:
            logger.error("PhoneRepository: failed to add phone", error=str(error))
            return
        if self._working_device is None:
            self._working_device = item

    def remove(self, item: Phone) -> None:
        try:
            super().remove(item)
        except ValueError as error:
            logger.error("PhoneRepository: failed to remove phone", error=str(error))
            return
        if self._working_device == item:
            self._working_device = None

    def clear(self) -> None:
        super().clear()
        self._working_device = None
