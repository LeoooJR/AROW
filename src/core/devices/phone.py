"""Android phone model, identity helpers, and repository."""

from __future__ import annotations

import datetime
import ipaddress
from dataclasses import dataclass, field, replace
from typing import Iterable, Literal, cast

from loguru import logger

from core.collection import Repository
from core.devices.base import Device, DeviceDescriptor
from core.devices.stable_key import (
    FirstTierStableKey,
    StableKey,
    compute_phone_stable_key,
)
from core.payload import Payload

DEFAULT_PHONE_DISPLAY_NAME = "Android device"
_PHONE_DISPLAY_ID_TAIL_LEN = 8
ConnectivityType = Literal["usb", "wifi"]


def _connection_id_is_wifi(connection_id: str) -> bool:
    """Return whether an ADB connection ID represents a Wi-Fi connection.

    Examples:
        ``192.168.1.20:5555`` and ``phone._adb-tls-connect._tcp`` return
        ``True``. ``emulator-5554`` and ``USB123456`` return ``False``.
    """
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
    """Return whether a connection ID is suitable for a display name.

    Examples:
        ``emulator-5554`` and ``USB123456`` return ``True``.
        ``phone._adb-tls-connect._tcp`` and long opaque IDs return ``False``.
    """
    cid = connection_id.strip()
    if not cid:
        return False
    if cid.startswith("emulator-"):
        return True
    if "." in cid:
        return False
    return len(cid) <= 24


def _derive_phone_display_name(
    *,
    connection_id: str,
    shell_device_name: str,
    manufacturer: str,
    model: str,
    product: str,
    device: str,
) -> str:
    """Derive the best user-facing name from available phone metadata."""
    shell = shell_device_name.strip()
    manufacturer = manufacturer.strip()
    model = model.strip()
    product = product.strip()
    device = device.strip()
    connection_id = connection_id.strip()

    if shell:
        return shell
    if manufacturer and model:
        return f"{manufacturer} {model}"
    if model:
        return model
    if product:
        return product
    if device:
        return device
    if connection_id and _adb_connection_id_is_human_readable(connection_id):
        return connection_id
    if len(connection_id) > _PHONE_DISPLAY_ID_TAIL_LEN:
        return (
            f"{DEFAULT_PHONE_DISPLAY_NAME} "
            f"({connection_id[-_PHONE_DISPLAY_ID_TAIL_LEN:]})"
        )
    return connection_id or DEFAULT_PHONE_DISPLAY_NAME


def _derive_stable_key_value(
    *,
    hardware_serial: str,
    product: str,
    model: str,
    manufacturer: str,
    fingerprint_when_no_serial: bool = False,
) -> str:
    """Return the serialized stable key derived from phone identity inputs."""
    stable_key = compute_phone_stable_key(
        hardware_serial=hardware_serial or None,
        product=product,
        model=model,
        manufacturer=manufacturer.strip() or None,
        fingerprint_when_no_serial=fingerprint_when_no_serial,
    )
    return stable_key.value if stable_key is not None else ""


@dataclass(frozen=True, match_args=True)
class PhoneDescriptor(DeviceDescriptor):
    """Metadata about an Android phone."""

    __hash__ = None

    id: str = field(
        metadata={"description": "The id of the device"},
        default="",
        compare=False,
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
    )
    state: str = field(
        metadata={"description": "The state of the phone"},
        default="",
        compare=False,
    )
    last_connection: datetime.datetime | None = field(
        metadata={"description": "The latest active ADB connection time"},
        default=None,
        compare=False,
    )
    hardware_serial: str = field(
        metadata={"description": "ro.serialno after enrichment"}, default=""
    )
    stable_key: str = field(
        metadata={"description": "Stable logical phone identity"}, default=""
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

    def __post_init__(self) -> None:
        """Derive the display name once when constructing the snapshot."""
        object.__setattr__(
            self,
            "name",
            _derive_phone_display_name(
                connection_id=self.id,
                shell_device_name=self.shell_device_name,
                manufacturer=self.manufacturer,
                model=self.model,
                product=self.product,
                device=self.device,
            ),
        )

    def __str__(self) -> str:
        """Return a concise, human-readable summary of the phone state."""
        details = [self.name]
        if self.os:
            android = f"Android {self.os}"
            if self.android_api_level is not None:
                android += f" (API {self.android_api_level})"
            details.append(android)
        elif self.android_api_level is not None:
            details.append(f"Android API {self.android_api_level}")

        connection_type = "Wi-Fi" if self.connectivity_type == "wifi" else "USB"
        details.append(f"{connection_type}: {self.id or 'unknown'}")
        if self.state:
            details.append(f"State: {self.state}")
        return " | ".join(details)


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
        stable_key = _derive_stable_key_value(
            hardware_serial=serial,
            product=prod,
            model=mod,
            manufacturer=man,
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
            last_connection=(
                datetime.datetime.now()
                if (state or "").strip().casefold() == "device"
                else None
            ),
            hardware_serial=serial,
            stable_key=stable_key,
            manufacturer=man,
            android_api_level=android_api_level,
            shell_device_name="",
        )
        super().__init__(descriptor=descriptor)

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
            self._descriptor = replace(self._descriptor, os=value)

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
        self._descriptor = replace(self._descriptor, state=value)

    @property
    def model(self) -> str:
        """Return the commercial device model."""
        return self._descriptor.model

    @model.setter
    def model(self, value: str) -> None:
        """Set a non-empty commercial device model."""
        value = value.strip()
        if value:
            stable_key = _derive_stable_key_value(
                hardware_serial=self.hardware_serial,
                product=self.product,
                model=value,
                manufacturer=self.manufacturer,
                fingerprint_when_no_serial=True,
            )
            self._descriptor = replace(
                self._descriptor,
                model=value,
                stable_key=stable_key,
            )

    @property
    def last_connection(self) -> datetime.datetime | None:
        """Return the latest time ADB reported this phone as active."""
        return self._descriptor.last_connection

    @last_connection.setter
    def last_connection(self, value: datetime.datetime | None) -> None:
        """Set the latest active ADB connection time.

        Raises:
            TypeError: If ``value`` is neither a datetime nor ``None``.
        """
        if value is not None and not isinstance(value, datetime.datetime):
            raise TypeError("last_connection must be a datetime or None")
        self._descriptor = replace(self._descriptor, last_connection=value)

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
            hardware_serial = value
        elif not self._descriptor.hardware_serial:
            hardware_serial = ""
        else:
            return
        stable_key = _derive_stable_key_value(
            hardware_serial=hardware_serial,
            product=self.product,
            model=self.model,
            manufacturer=self.manufacturer,
            fingerprint_when_no_serial=True,
        )
        self._descriptor = replace(
            self._descriptor,
            hardware_serial=hardware_serial,
            stable_key=stable_key,
        )

    @property
    def manufacturer(self) -> str:
        """Return the enriched device manufacturer."""
        return self._descriptor.manufacturer

    @manufacturer.setter
    def manufacturer(self, value: str) -> None:
        """Set a non-empty device manufacturer."""
        value = value.strip()
        if value:
            stable_key = _derive_stable_key_value(
                hardware_serial=self.hardware_serial,
                product=self.product,
                model=self.model,
                manufacturer=value,
                fingerprint_when_no_serial=True,
            )
            self._descriptor = replace(
                self._descriptor,
                manufacturer=value,
                stable_key=stable_key,
            )

    @property
    def android_api_level(self) -> int | None:
        """Return the enriched Android SDK API level."""
        return self._descriptor.android_api_level

    @android_api_level.setter
    def android_api_level(self, value: int | None) -> None:
        """Set the Android SDK API level when available."""
        if value is not None:
            self._descriptor = replace(self._descriptor, android_api_level=value)

    @property
    def shell_device_name(self) -> str:
        """Return the enriched user-facing shell device name."""
        return self._descriptor.shell_device_name

    @shell_device_name.setter
    def shell_device_name(self, value: str) -> None:
        """Set the normalized shell device name."""
        self._descriptor = replace(self._descriptor, shell_device_name=value.strip())

    def apply_shell_enrichment(
        self,
        *,
        manufacturer: str,
        model: str,
        shell_device_name: str,
        os: str,
        android_api_level: int | None,
        hardware_serial: str,
    ) -> None:
        """Atomically apply normalized metadata from one ADB shell observation."""
        current = self._descriptor
        normalized_manufacturer = manufacturer.strip() or current.manufacturer
        normalized_model = model.strip() or current.model
        normalized_os = os.strip() or current.os
        normalized_serial = hardware_serial.strip()
        if not normalized_serial or normalized_serial.casefold() == "unknown":
            normalized_serial = current.hardware_serial
        stable_key = _derive_stable_key_value(
            hardware_serial=normalized_serial,
            product=current.product,
            model=normalized_model,
            manufacturer=normalized_manufacturer,
            fingerprint_when_no_serial=True,
        )
        self._descriptor = replace(
            current,
            manufacturer=normalized_manufacturer,
            model=normalized_model,
            shell_device_name=shell_device_name.strip(),
            os=normalized_os,
            android_api_level=(
                android_api_level
                if android_api_level is not None
                else current.android_api_level
            ),
            hardware_serial=normalized_serial,
            stable_key=stable_key,
        )

    def apply_discovery(self, discovered: Phone) -> None:
        """Replace this phone's state from one complete discovery observation."""
        if discovered.last_connection is not None:
            self._descriptor = discovered.descriptor
            return
        self._descriptor = replace(
            discovered.descriptor,
            last_connection=self.last_connection,
        )

    def _restore_persisted_state(
        self,
        *,
        stable_key: str | None,
        last_connection: datetime.datetime | None,
    ) -> None:
        """Restore fields persisted independently from live ADB discovery metadata."""
        self._descriptor = replace(
            self._descriptor,
            stable_key=(
                stable_key if stable_key is not None else self._descriptor.stable_key
            ),
            last_connection=last_connection,
        )

    def serialize(self, **kwargs: object) -> dict[str, object]:
        """Serialize persisted phone state.

        Args:
            **kwargs: Serialization options. ``json_compatible`` converts the
                connection timestamp to ISO 8601 text.

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
            "last_connection": (
                self.last_connection.isoformat()
                if kwargs.get("json_compatible", False)
                and self.last_connection is not None
                else self.last_connection
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
        value = payload.get("last_connection")
        last_connection = (
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
        phone._restore_persisted_state(
            stable_key=(
                str(payload["stable_key"])
                if payload.get("stable_key") is not None
                else None
            ),
            last_connection=last_connection,
        )
        return phone


def serialize_phone_collection(phones: Iterable[Phone]) -> list[dict[str, object]]:
    """Serialize a phone collection while preserving datetime values."""
    return [phone.serialize(json_compatible=False) for phone in phones]


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
        elif device in self:
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
        if self._working_device is item:
            self._working_device = None

    def index_by_stable_identity(self) -> dict[FirstTierStableKey, Phone]:
        """Return the first phone stored for each Tier-1 stable identity.

        Tier-2 fingerprints are deliberately excluded because they can collide across
        similar handsets and are unsafe for connection-ID rebinding.
        """
        indexed: dict[FirstTierStableKey, Phone] = {}
        for phone in self:
            stable_identity = StableKey.from_value(phone.stable_key)
            if (
                isinstance(stable_identity, FirstTierStableKey)
                and stable_identity not in indexed
            ):
                indexed[stable_identity] = phone
        return indexed

    def clear(self) -> None:
        """Remove all phones and clear the working-device selection."""
        super().clear()
        self._working_device = None
