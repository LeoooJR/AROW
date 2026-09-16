"""Android phone model, identity helpers, and repository."""

from __future__ import annotations

import datetime
import ipaddress
from dataclasses import dataclass, field
from typing import Iterable, Literal, cast

from loguru import logger

from core.collection import Repository
from core.devices.base import Device, DeviceDescriptor
from core.devices.stable_key import compute_phone_stable_key
from core.payload import Payload

DEFAULT_PHONE_DISPLAY_NAME = "Android device"
_PHONE_DISPLAY_ID_TAIL_LEN = 8
ConnectivityType = Literal["usb", "wifi"]


def _connection_id_is_wifi(connection_id: str) -> bool:
    normalized = connection_id.strip()
    if normalized.casefold().endswith("._adb-tls-connect._tcp"):
        return True
    if ":" not in normalized:
        return False
    host, port_value = normalized.rsplit(":", 1)
    try:
        ipaddress.IPv4Address(host)
        port = int(port_value)
    except (ipaddress.AddressValueError, ValueError):
        return False
    return 1 <= port <= 65535


def _resolve_connectivity_type(
    *,
    connection_id: str,
    ip: str | None,
    port: int | None,
    connectivity_type: ConnectivityType | None,
) -> ConnectivityType:
    if connectivity_type is not None:
        if connectivity_type not in ("usb", "wifi"):
            raise ValueError("connectivity_type must be 'usb' or 'wifi'")
        return connectivity_type
    if (ip or "").strip() and port is not None:
        return "wifi"
    return "wifi" if _connection_id_is_wifi(connection_id) else "usb"


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

    id: str = field(
        metadata={"description": "The id of the device"},
        default="",
        compare=False,
        hash=False,
    )
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
    connectivity_type: ConnectivityType = field(
        metadata={"description": "Whether ADB reaches the phone over USB or Wi-Fi"},
        default="usb",
        compare=False,
        hash=False,
    )
    state: str = field(
        metadata={"description": "The state of the phone"},
        default="",
        compare=False,
        hash=False,
    )
    last_communication: datetime.datetime = field(
        metadata={"description": "The last communication time of the phone"},
        default_factory=datetime.datetime.now,
        compare=False,
        hash=False,
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
        metadata={"description": "Friendly getprop device name"},
        default="",
    )
    _stable_key_sync_enabled: bool = field(
        init=False,
        default=False,
        repr=False,
        compare=False,
        hash=False,
    )

    _STABLE_KEY_INPUT_FIELDS = frozenset(
        {"hardware_serial", "manufacturer", "product", "model"}
    )
    _DISPLAY_NAME_INPUT_FIELDS = frozenset(
        {"id", "product", "model", "device", "manufacturer", "shell_device_name"}
    )

    def __post_init__(self) -> None:
        """Enable synchronization after construction preserves ADB-list key timing."""
        object.__setattr__(self, "_stable_key_sync_enabled", True)
        self._sync_display_name()

    def __setattr__(self, name: str, value: object) -> None:
        """Synchronize derived stable-key and display-name fields after input changes."""
        object.__setattr__(self, name, value)
        if not self.__dict__.get("_stable_key_sync_enabled", False):
            return
        if name in self._STABLE_KEY_INPUT_FIELDS:
            stable_key = compute_phone_stable_key(
                hardware_serial=self.hardware_serial or None,
                product=self.product,
                model=self.model,
                manufacturer=self.manufacturer or None,
                fingerprint_when_no_serial=True,
            )
            object.__setattr__(
                self,
                "stable_key",
                stable_key.value if stable_key is not None else "",
            )
        if name in self._DISPLAY_NAME_INPUT_FIELDS:
            self._sync_display_name()

    def _sync_display_name(self) -> None:
        """Derive the user-facing label from enriched and ADB-list metadata."""
        shell, manufacturer, model, product, device = (
            (self.shell_device_name or "").strip(),
            (self.manufacturer or "").strip(),
            (self.model or "").strip(),
            (self.product or "").strip(),
            (self.device or "").strip(),
        )
        if shell:
            name = shell
        elif manufacturer and model:
            name = f"{manufacturer} {model}"
        elif model:
            name = model
        elif product:
            name = product
        elif device:
            name = device
        elif self.id and _adb_connection_id_is_human_readable(self.id):
            name = self.id
        elif self.id and len(self.id) > _PHONE_DISPLAY_ID_TAIL_LEN:
            name = f"{DEFAULT_PHONE_DISPLAY_NAME} ({self.id[-_PHONE_DISPLAY_ID_TAIL_LEN:]})"
        else:
            name = DEFAULT_PHONE_DISPLAY_NAME if not self.id else self.id
        object.__setattr__(self, "name", name)

    def __str__(self) -> str:
        return f"{self.id} - {self.name} - {self.os} - {self.ip}:{self.port} - {self.product} - {self.model} - {self.transport_id} - {self.connectivity_type} - {self.state} - {self.hardware_serial} - {self.stable_key} - {self.manufacturer} - {self.android_api_level} - {self.last_communication}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id}, name={self.name}, os={self.os}, ip={self.ip}, port={self.port}, product={self.product}, model={self.model}, transport_id={self.transport_id}, connectivity_type={self.connectivity_type!r}, state={self.state}, hardware_serial={self.hardware_serial!r}, stable_key={self.stable_key!r}, manufacturer={self.manufacturer!r}, android_api_level={self.android_api_level!r}, shell_device_name={self.shell_device_name!r}, last_communication={self.last_communication})"


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
        connectivity_type: ConnectivityType | None = None,
    ) -> None:
        """Initialize an Android phone from ADB and enrichment metadata.

        Args:
            id: Current ADB connection identifier.
            name: Optional fallback display name or ADB device column.
            os: Android release string.
            ip: Network address for a Wi-Fi connection.
            port: Network port for a Wi-Fi connection.
            device: Device value reported by ``adb devices -l``.
            product: Product value reported by ADB.
            model: Commercial model value reported by ADB.
            state: Current ADB connection state.
            hardware_serial: Hardware serial reported by ``ro.serialno``.
            manufacturer: Device manufacturer reported by ADB.
            transport_id: Transport identifier reported by ADB.
            android_api_level: Android SDK API level.
            connectivity_type: Explicit ``usb`` or ``wifi`` transport type.

        Raises:
            ValueError: If ``connectivity_type`` is unsupported.
        """
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
            connectivity_type=_resolve_connectivity_type(
                connection_id=id,
                ip=ip,
                port=port,
                connectivity_type=connectivity_type,
            ),
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Phone):
            return NotImplemented
        return self.descriptor == other.descriptor

    def __hash__(self) -> int:
        return hash(self.descriptor)

    @property
    def product(self) -> str:
        """Return the ADB product identifier."""
        return self._descriptor.product

    @property
    def os(self) -> str:
        """Return the Android release string."""
        return self._descriptor.os

    @os.setter
    def os(self, value: str) -> None:
        """Set a non-empty Android release string."""
        value = value.strip()
        if value:
            self._descriptor.os = value

    @property
    def state(self) -> str:
        """Return the current ADB connection state."""
        return self._descriptor.state

    @state.setter
    def state(self, value: str) -> None:
        """Set the current ADB connection state.

        Raises:
            TypeError: If ``value`` is not a string.
        """
        if not isinstance(value, str):
            raise TypeError("state must be a string")
        self._descriptor.state = value

    @property
    def model(self) -> str:
        """Return the commercial device model."""
        return self._descriptor.model

    @model.setter
    def model(self, value: str) -> None:
        """Set a non-empty commercial device model."""
        value = value.strip()
        if value:
            self._descriptor.model = value

    @property
    def last_communication(self) -> datetime.datetime:
        """Return the time of the latest device communication."""
        return self._descriptor.last_communication

    @last_communication.setter
    def last_communication(self, value: datetime.datetime) -> None:
        """Set the time of the latest device communication.

        Raises:
            TypeError: If ``value`` is not a datetime.
        """
        if not isinstance(value, datetime.datetime):
            raise TypeError("last_communication must be a datetime")
        self._descriptor.last_communication = value

    @property
    def transport_id(self) -> str:
        """Return the current ADB transport identifier."""
        return self._descriptor.transport_id

    @property
    def connectivity_type(self) -> ConnectivityType:
        """Return whether ADB reaches the phone over USB or Wi-Fi."""
        return self._descriptor.connectivity_type

    @property
    def stable_key(self) -> str:
        """Return the stable logical phone identity."""
        return self._descriptor.stable_key

    @property
    def hardware_serial(self) -> str:
        """Return the enriched hardware serial."""
        return self._descriptor.hardware_serial

    @hardware_serial.setter
    def hardware_serial(self, value: str) -> None:
        """Set a valid hardware serial and refresh derived identity."""
        value = value.strip()
        if value and value.casefold() != "unknown":
            self._descriptor.hardware_serial = value
        elif not self._descriptor.hardware_serial:
            # Assigning the known-empty input lets descriptor-level sync derive Tier 2.
            self._descriptor.hardware_serial = ""

    @property
    def manufacturer(self) -> str:
        """Return the enriched device manufacturer."""
        return self._descriptor.manufacturer

    @manufacturer.setter
    def manufacturer(self, value: str) -> None:
        """Set a non-empty device manufacturer."""
        value = value.strip()
        if value:
            self._descriptor.manufacturer = value

    @property
    def android_api_level(self) -> int | None:
        """Return the enriched Android SDK API level."""
        return self._descriptor.android_api_level

    @android_api_level.setter
    def android_api_level(self, value: int | None) -> None:
        """Set the Android SDK API level when available."""
        if value is not None:
            self._descriptor.android_api_level = value

    @property
    def shell_device_name(self) -> str:
        """Return the enriched user-facing shell device name."""
        return self._descriptor.shell_device_name

    @shell_device_name.setter
    def shell_device_name(self, value: str) -> None:
        """Set the normalized shell device name."""
        self._descriptor.shell_device_name = value.strip()

    def serialize(self, **kwargs: object) -> dict[str, object]:
        """Serialize persisted phone state.

        Args:
            **kwargs: Serialization options. ``json_compatible`` converts the
                communication timestamp to ISO 8601 text.

        Returns:
            Persistable phone state keyed by field name.
        """
        return {
            "id": self.id,
            "name": self.name,
            "os": self.os,
            "ip": self.ip,
            "port": self.port,
            "state": self.state,
            "connectivity_type": self.connectivity_type,
            "stable_key": self.stable_key,
            "last_communication": (
                self.last_communication.isoformat()
                if kwargs.get("json_compatible", False)
                else self.last_communication
            ),
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs: object) -> Phone:
        """Deserialize persisted phone state.

        Args:
            payload: Persisted phone fields.
            **kwargs: Reserved deserialization options.

        Returns:
            Reconstructed phone instance.

        Raises:
            KeyError: If the required ``id`` field is absent.
            ValueError: If a serialized port or timestamp is invalid.
        """
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
            connectivity_type=(
                cast(ConnectivityType, payload["connectivity_type"])
                if payload.get("connectivity_type") is not None
                else None
            ),
        )
        if payload.get("stable_key") is not None:
            phone.descriptor.stable_key = str(payload["stable_key"])
        if last_communication is not None:
            phone.descriptor.last_communication = last_communication
        return phone


def serialize_phone_collection(phones: Iterable[Phone]) -> list[dict[str, object]]:
    """Serialize a phone collection while preserving datetime values."""
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
    "connectivity_type",
    "state",
    "hardware_serial",
    "stable_key",
    "manufacturer",
    "android_api_level",
    "shell_device_name",
)


def apply_discovered_phone_state(paired: Phone, discovered: Phone) -> None:
    """Apply fresh discovery metadata to an existing paired phone.

    Args:
        paired: Tracked phone instance to update in place.
        discovered: Newly discovered phone supplying current metadata.
    """
    for field_name in _DISCOVERED_PHONE_DESCRIPTOR_FIELDS:
        setattr(
            paired.descriptor, field_name, getattr(discovered.descriptor, field_name)
        )
    paired.descriptor.id = discovered.id
    paired.descriptor.last_communication = discovered.descriptor.last_communication


class PhoneRepository(Repository[Phone]):
    """Repository that tracks the first added phone as its working device."""

    def __init__(self) -> None:
        """Initialize an empty repository without a working phone."""
        super().__init__()
        self._working_device: Phone | None = None

    @property
    def working_device(self) -> Phone | None:
        """Return the currently selected phone."""
        return self.__dict__.get("_working_device", None)

    @working_device.setter
    def working_device(self, device: Phone | None) -> None:
        """Select a tracked phone or clear the selection.

        Raises:
            ValueError: If ``device`` is not stored in the repository.
        """
        if device is None:
            self._working_device = None
        elif device.id in self._repository:
            self._working_device = device
        else:
            raise ValueError(f"Device with id {device.id} is not in the repository")

    def add(self, item: Phone) -> None:
        """Add a phone and select the first successful addition."""
        try:
            super().add(item)
        except ValueError as error:
            logger.error("Phone could not be added to repository", error=str(error))
            return
        if self._working_device is None:
            self._working_device = item

    def remove(self, item: Phone) -> None:
        """Remove a phone and clear it when currently selected."""
        try:
            super().remove(item)
        except ValueError as error:
            logger.error("Phone could not be removed from repository", error=str(error))
            return
        if self._working_device == item:
            self._working_device = None

    def index_by_stable_key(self) -> dict[str, Phone]:
        """Return the first phone stored for each non-empty stable identity.

        Keeping the first phone makes duplicate stable identities deterministic. The
        reconciliation engine decides separately whether a key is collision-resistant
        enough to use for matching.
        """
        indexed: dict[str, Phone] = {}
        for phone in self:
            stable_key = (phone.stable_key or "").strip()
            if stable_key and stable_key not in indexed:
                indexed[stable_key] = phone
        return indexed

    def clear(self) -> None:
        """Remove all phones and clear the working-device selection."""
        super().clear()
        self._working_device = None
