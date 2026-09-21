"""Physical Android phone aggregate and ADB connection value objects."""

from __future__ import annotations

import datetime
import ipaddress
import uuid
from dataclasses import dataclass, replace
from typing import Iterable, Iterator, Literal, cast

from loguru import logger

from core.devices.base import Device, DeviceDescriptor
from core.devices.stable_key import (
    FirstTierStableKey,
    StableKey,
    compute_phone_stable_key,
)
from core.payload import Payload

DEFAULT_PHONE_DISPLAY_NAME = "Android device"
_PHONE_DISPLAY_ID_TAIL_LEN = 8
_PROVISIONAL_PHONE_ID_PREFIX = "phone:v1:provisional:"
ConnectivityType = Literal["usb", "wifi"]


def _connection_id_is_wifi(connection_id: str) -> bool:
    """Return whether an ADB id identifies a network connection.

    Args:
        connection_id: ADB endpoint identifier to classify.

    Returns:
        ``True`` for IPv4 endpoints and mDNS TLS service identifiers; otherwise
        ``False``. For example, ``192.168.1.20:5555`` returns ``True`` while
        ``emulator-5554`` and ``USB123456`` return ``False``.
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
    """Resolve explicit or inferred ADB connectivity.

    Args:
        connection_id: ADB endpoint identifier used for fallback inference.
        ip: Optional endpoint IPv4 address.
        port: Optional endpoint TCP port.
        connectivity_type: Explicit transport type, when supplied by discovery.

    Returns:
        The explicit connectivity type, or an inferred ``"usb"``/``"wifi"``
        value.

    Raises:
        ValueError: If ``connectivity_type`` is neither ``"usb"`` nor
            ``"wifi"``.
    """
    if connectivity_type is not None:
        if connectivity_type not in ("usb", "wifi"):
            raise ValueError("connectivity_type must be 'usb' or 'wifi'")
        return connectivity_type
    if (ip or "").strip() and port is not None:
        return "wifi"
    return "wifi" if _connection_id_is_wifi(connection_id) else "usb"


def _adb_connection_id_is_human_readable(connection_id: str) -> bool:
    """Return whether an ADB id is suitable for direct display.

    Args:
        connection_id: ADB endpoint identifier to inspect.

    Returns:
        ``True`` for concise USB or emulator identifiers; otherwise ``False``.
        For example, ``emulator-5554`` and ``USB123456`` return ``True``, while
        mDNS service identifiers and long opaque ids return ``False``.
    """
    cid = connection_id.strip()
    return bool(cid) and (
        cid.startswith("emulator-") or ("." not in cid and len(cid) <= 24)
    )


def _derive_phone_display_name(
    *,
    connection_id: str,
    shell_device_name: str,
    manufacturer: str,
    model: str,
    product: str,
    device: str,
) -> str:
    """Derive the best available human-readable physical-phone name.

    Args:
        connection_id: Endpoint identifier used as the final naming fallback.
        shell_device_name: Friendly name read from Android properties.
        manufacturer: Hardware manufacturer name.
        model: Hardware model name.
        product: Product identifier from ADB discovery.
        device: Device codename from ADB discovery.

    Returns:
        A normalized name selected by display precedence.
    """
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
        return f"{DEFAULT_PHONE_DISPLAY_NAME} ({connection_id[-_PHONE_DISPLAY_ID_TAIL_LEN:]})"
    return connection_id or DEFAULT_PHONE_DISPLAY_NAME


def _derive_stable_key_value(
    *,
    hardware_serial: str,
    product: str,
    model: str,
    manufacturer: str,
    fingerprint_when_no_serial: bool = False,
) -> str:
    """Derive the serialized stable key from physical metadata.

    Args:
        hardware_serial: Tier-1 hardware serial, when known.
        product: Product identifier used by Tier-2 fingerprinting.
        model: Model name used by Tier-2 fingerprinting.
        manufacturer: Manufacturer used by Tier-2 fingerprinting.
        fingerprint_when_no_serial: Whether to produce a Tier-2 fallback when
            the hardware serial is unavailable.

    Returns:
        The serialized stable key, or an empty string when no key is available.
    """
    stable_key = compute_phone_stable_key(
        hardware_serial=hardware_serial or None,
        product=product,
        model=model,
        manufacturer=manufacturer.strip() or None,
        fingerprint_when_no_serial=fingerprint_when_no_serial,
    )
    return stable_key.value if stable_key is not None else ""


@dataclass(frozen=True, slots=True)
class PhoneIdentity:
    """Immutable physical-phone identity used outside the transport layer.

    Attributes:
        value: Non-empty serialized physical identity.
    """

    value: str

    def __post_init__(self) -> None:
        """Normalize and validate the serialized identity.

        Raises:
            ValueError: If the identity is blank after normalization.
        """
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("phone identity must not be blank")
        object.__setattr__(self, "value", normalized)

    @classmethod
    def provisional(cls) -> PhoneIdentity:
        """Create a process-independent provisional physical identity.

        Returns:
            A UUID-backed identity awaiting Tier-1 enrichment.
        """
        return cls(f"{_PROVISIONAL_PHONE_ID_PREFIX}{uuid.uuid4().hex}")

    @classmethod
    def from_stable_key(cls, stable_key: str) -> PhoneIdentity | None:
        """Create a physical identity from a collision-resistant stable key.

        Args:
            stable_key: Serialized stable-key value to parse.

        Returns:
            A physical identity for a Tier-1 key, or ``None`` for missing,
            malformed, or Tier-2 keys.
        """
        parsed = StableKey.from_value(stable_key)
        return cls(parsed.value) if isinstance(parsed, FirstTierStableKey) else None

    @property
    def is_provisional(self) -> bool:
        """Return whether this identity is awaiting Tier-1 enrichment."""
        return self.value.startswith(_PROVISIONAL_PHONE_ID_PREFIX)


@dataclass(frozen=True, slots=True)
class AdbConnection:
    """One immutable observation of an ADB endpoint.

    Attributes:
        id: Non-empty ADB endpoint identifier.
        state: Normalized ADB connection state.
        transport_id: ADB transport identifier from discovery.
        connectivity_type: Whether the endpoint uses USB or Wi-Fi.
        ip: Optional endpoint IPv4 address.
        port: Optional endpoint TCP port.
        last_connection: Latest time this endpoint was observed as active.
    """

    __hash__ = None  # type: ignore[assignment]

    id: str
    state: str = ""
    transport_id: str = ""
    connectivity_type: ConnectivityType = "usb"
    ip: str = ""
    port: int | None = None
    last_connection: datetime.datetime | None = None

    def __post_init__(self) -> None:
        """Normalize and validate the immutable connection snapshot.

        Raises:
            ValueError: If the endpoint id is blank, connectivity is invalid, or
                the port falls outside the valid TCP range.
            TypeError: If ``last_connection`` is not a datetime or ``None``.
        """
        connection_id = self.id.strip()
        if not connection_id:
            raise ValueError("ADB connection id must not be blank")
        if self.connectivity_type not in ("usb", "wifi"):
            raise ValueError("connectivity_type must be 'usb' or 'wifi'")
        if self.port is not None and (
            isinstance(self.port, bool) or not 1 <= self.port <= 65535
        ):
            raise ValueError("port must be between 1 and 65535")
        if self.last_connection is not None and not isinstance(
            self.last_connection, datetime.datetime
        ):
            raise TypeError("last_connection must be a datetime or None")
        object.__setattr__(self, "id", connection_id)
        object.__setattr__(self, "state", self.state.strip())
        object.__setattr__(self, "transport_id", self.transport_id.strip())
        object.__setattr__(self, "ip", self.ip.strip())

    @classmethod
    def observed(
        cls,
        id: str,
        *,
        state: str = "",
        transport_id: str = "",
        connectivity_type: ConnectivityType | None = None,
        ip: str | None = None,
        port: int | None = None,
        observed_at: datetime.datetime | None = None,
    ) -> AdbConnection:
        """Build a connection snapshot from one ADB observation.

        Args:
            id: ADB endpoint identifier.
            state: ADB state reported for the endpoint.
            transport_id: ADB transport identifier from discovery.
            connectivity_type: Explicit transport type, or ``None`` to infer it.
            ip: Optional endpoint IPv4 address.
            port: Optional endpoint TCP port.
            observed_at: Observation time used for an active endpoint. Defaults
                to the current local time.

        Returns:
            A normalized immutable connection snapshot. Inactive observations
            have no new ``last_connection`` timestamp.

        Raises:
            ValueError: If endpoint metadata violates connection invariants.
        """
        normalized_state = state.strip()
        last_connection = None
        if normalized_state.casefold() == "device":
            last_connection = observed_at or datetime.datetime.now()
        return cls(
            id=id,
            state=normalized_state,
            transport_id=transport_id,
            connectivity_type=_resolve_connectivity_type(
                connection_id=id,
                ip=ip,
                port=port,
                connectivity_type=connectivity_type,
            ),
            ip=ip or "",
            port=port,
            last_connection=last_connection,
        )

    @property
    def is_active(self) -> bool:
        """Return whether ADB reported the endpoint in the ``device`` state."""
        return self.state.casefold() == "device"

    def serialize(self, *, json_compatible: bool = False) -> dict[str, object]:
        """Serialize the connection snapshot.

        Args:
            json_compatible: Whether to encode the timestamp as ISO 8601 text.

        Returns:
            A payload containing all endpoint state.
        """
        return {
            "id": self.id,
            "state": self.state,
            "transport_id": self.transport_id,
            "connectivity_type": self.connectivity_type,
            "ip": self.ip,
            "port": self.port,
            "last_connection": (
                self.last_connection.isoformat()
                if json_compatible and self.last_connection is not None
                else self.last_connection
            ),
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object]) -> AdbConnection:
        """Restore a connection snapshot from a serialized payload.

        Args:
            payload: Connection data containing at least an ``id`` field.

        Returns:
            The validated immutable connection snapshot.

        Raises:
            KeyError: If the required connection id is absent.
            ValueError: If a timestamp, port, or connection field is invalid.
            TypeError: If a parsed timestamp violates the connection contract.
        """
        raw_timestamp = payload.get("last_connection")
        timestamp = (
            datetime.datetime.fromisoformat(raw_timestamp)
            if isinstance(raw_timestamp, str) and raw_timestamp.strip()
            else raw_timestamp if isinstance(raw_timestamp, datetime.datetime) else None
        )
        raw_port = payload.get("port")
        port = (
            raw_port
            if isinstance(raw_port, int) and not isinstance(raw_port, bool)
            else (
                int(raw_port)
                if isinstance(raw_port, str) and raw_port.strip()
                else None
            )
        )
        return cls(
            id=str(payload["id"]),
            state=str(payload.get("state") or ""),
            transport_id=str(payload.get("transport_id") or ""),
            connectivity_type=cast(
                ConnectivityType, payload.get("connectivity_type") or "usb"
            ),
            ip=str(payload.get("ip") or ""),
            port=port,
            last_connection=timestamp,
        )


@dataclass(frozen=True, match_args=True)
class PhoneDescriptor(DeviceDescriptor):
    """Physical metadata shared by all connections to a phone.

    Attributes:
        product: Product identifier reported by ADB discovery.
        model: Commercial hardware model.
        device: Android device codename.
        hardware_serial: Hardware serial used for Tier-1 identity.
        stable_key: Serialized stable identity derived from physical metadata.
        manufacturer: Hardware manufacturer.
        android_api_level: Android SDK API level, when known.
        shell_device_name: Friendly name reported by Android properties.
    """

    __hash__ = None

    product: str = ""
    model: str = ""
    device: str = ""
    hardware_serial: str = ""
    stable_key: str = ""
    manufacturer: str = ""
    android_api_level: int | None = None
    shell_device_name: str = ""


class Phone(Device[PhoneDescriptor], Payload):
    """Mutable physical-phone aggregate backed by immutable snapshots."""

    def __init__(
        self,
        connection: AdbConnection,
        *,
        identity: PhoneIdentity | None = None,
        name: str | None = None,
        os: str | None = None,
        device: str | None = None,
        product: str | None = None,
        model: str | None = None,
        hardware_serial: str | None = None,
        manufacturer: str | None = None,
        android_api_level: int | None = None,
    ) -> None:
        """Initialize a physical phone from one observed ADB connection.

        Args:
            connection: Initial ADB endpoint observation.
            identity: Existing physical identity, or ``None`` to derive one.
            name: Legacy fallback name used as the device codename.
            os: Android release string.
            device: Android device codename reported by discovery.
            product: Product identifier reported by discovery.
            model: Commercial hardware model.
            hardware_serial: Hardware serial reported by Android properties.
            manufacturer: Hardware manufacturer.
            android_api_level: Android SDK API level, when known.
        """
        serial = (hardware_serial or "").strip()
        if serial.casefold() == "unknown":
            serial = ""
        stable_key = _derive_stable_key_value(
            hardware_serial=serial,
            product=product or "",
            model=model or "",
            manufacturer=manufacturer or "",
        )
        self._identity = (
            PhoneIdentity.from_stable_key(stable_key)
            or identity
            or PhoneIdentity.provisional()
        )
        self._connections: tuple[AdbConnection, ...] = (connection,)
        self._preferred_connection_id: str | None = None
        descriptor = PhoneDescriptor(
            name="",
            os=os or "",
            product=product or "",
            model=model or "",
            device=(device or name or "").strip(),
            hardware_serial=serial,
            stable_key=stable_key,
            manufacturer=manufacturer or "",
            android_api_level=android_api_level,
        )
        super().__init__(descriptor=descriptor)
        self._preferred_connection_id = self._choose_target_connection_id()
        self._descriptor = self._with_derived_name(self._descriptor)

    @property
    def identity(self) -> PhoneIdentity:
        """Return the immutable physical-phone identity."""
        return self._identity

    @property
    def id(self) -> str:
        """Return the physical identity used by repositories and UI payloads."""
        return self._identity.value

    @property
    def connections(self) -> tuple[AdbConnection, ...]:
        """Return all current ADB connection snapshots in identifier order."""
        return self._connections

    @property
    def preferred_connection_id(self) -> str | None:
        """Return the explicitly preferred active ADB endpoint identifier."""
        return self._preferred_connection_id

    @property
    def target_connection(self) -> AdbConnection | None:
        """Return the active connection selected for ADB commands, if any."""
        if self._preferred_connection_id is not None:
            preferred = self.connection_by_id(self._preferred_connection_id)
            if preferred is not None and preferred.is_active:
                return preferred
        target_id = self._choose_target_connection_id()
        return self.connection_by_id(target_id) if target_id is not None else None

    @property
    def display_connection(self) -> AdbConnection:
        """Return the connection used for human-readable aggregate presentation."""
        return (
            self.target_connection
            or sorted(self._connections, key=lambda connection: connection.id)[0]
        )

    def connection_by_id(self, connection_id: str) -> AdbConnection | None:
        """Find a connection owned by this phone.

        Args:
            connection_id: ADB endpoint identifier to resolve.

        Returns:
            The matching connection snapshot, or ``None`` when it is not owned.
        """
        normalized = connection_id.strip()
        return next(
            (
                connection
                for connection in self._connections
                if connection.id == normalized
            ),
            None,
        )

    def select_connection(self, connection_id: str) -> None:
        """Select an active owned connection for subsequent ADB commands.

        Args:
            connection_id: ADB endpoint identifier to prefer.

        Raises:
            ValueError: If the connection is not owned or is not active.
        """
        connection = self.connection_by_id(connection_id)
        if connection is None:
            raise ValueError(f"ADB connection {connection_id!r} is not owned by phone")
        if not connection.is_active:
            raise ValueError(f"ADB connection {connection_id!r} is not active")
        self._preferred_connection_id = connection.id
        self._descriptor = self._with_derived_name(self._descriptor)

    def _choose_target_connection_id(self) -> str | None:
        """Choose the deterministic USB-first active connection identifier."""
        active = sorted(
            (connection for connection in self._connections if connection.is_active),
            key=lambda connection: (
                connection.connectivity_type != "usb",
                connection.id,
            ),
        )
        return active[0].id if active else None

    def _with_derived_name(self, descriptor: PhoneDescriptor) -> PhoneDescriptor:
        """Return a descriptor with its display name recomputed.

        Args:
            descriptor: Metadata snapshot whose derived name must be refreshed.

        Returns:
            A new descriptor containing the best human-readable name.
        """
        return replace(
            descriptor,
            name=_derive_phone_display_name(
                connection_id=self.display_connection.id,
                shell_device_name=descriptor.shell_device_name,
                manufacturer=descriptor.manufacturer,
                model=descriptor.model,
                product=descriptor.product,
                device=descriptor.device,
            ),
        )

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
        """Replace the Android release when ``value`` is non-blank.

        Args:
            value: Android release string to normalize and apply.
        """
        normalized = value.strip()
        if normalized:
            self._descriptor = replace(self._descriptor, os=normalized)

    @property
    def model(self) -> str:
        """Return the commercial hardware model."""
        return self._descriptor.model

    @model.setter
    def model(self, value: str) -> None:
        """Replace a non-blank model and refresh derived identity metadata.

        Args:
            value: Model name to normalize and apply.
        """
        normalized = value.strip()
        if normalized:
            self._replace_identity_metadata(model=normalized)

    @property
    def stable_key(self) -> str:
        """Return the serialized physical stable key."""
        return self._descriptor.stable_key

    @property
    def hardware_serial(self) -> str:
        """Return the normalized hardware serial."""
        return self._descriptor.hardware_serial

    @hardware_serial.setter
    def hardware_serial(self, value: str) -> None:
        """Replace the serial without discarding a known value for an unknown one.

        Args:
            value: Hardware serial to normalize and apply.
        """
        normalized = value.strip()
        if not normalized or normalized.casefold() == "unknown":
            if self.hardware_serial:
                return
            normalized = ""
        self._replace_identity_metadata(hardware_serial=normalized)

    @property
    def manufacturer(self) -> str:
        """Return the hardware manufacturer."""
        return self._descriptor.manufacturer

    @manufacturer.setter
    def manufacturer(self, value: str) -> None:
        """Replace a non-blank manufacturer and refresh derived metadata.

        Args:
            value: Manufacturer name to normalize and apply.
        """
        normalized = value.strip()
        if normalized:
            self._replace_identity_metadata(manufacturer=normalized)

    @property
    def android_api_level(self) -> int | None:
        """Return the Android SDK API level, when known."""
        return self._descriptor.android_api_level

    @android_api_level.setter
    def android_api_level(self, value: int | None) -> None:
        """Replace the Android SDK API level when one is provided.

        Args:
            value: API level to apply, or ``None`` to preserve current state.
        """
        if value is not None:
            self._descriptor = replace(self._descriptor, android_api_level=value)

    @property
    def shell_device_name(self) -> str:
        """Return the friendly device name reported by Android properties."""
        return self._descriptor.shell_device_name

    @shell_device_name.setter
    def shell_device_name(self, value: str) -> None:
        """Replace the friendly device name and recompute the display name.

        Args:
            value: Friendly name to normalize and apply. A blank value clears it.
        """
        self._descriptor = self._with_derived_name(
            replace(self._descriptor, shell_device_name=value.strip())
        )

    def _replace_identity_metadata(
        self,
        *,
        hardware_serial: str | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
    ) -> None:
        """Replace identity inputs and recompute derived metadata once.

        Args:
            hardware_serial: Replacement serial, or ``None`` to preserve it.
            manufacturer: Replacement manufacturer, or ``None`` to preserve it.
            model: Replacement model, or ``None`` to preserve it.
        """
        updated = replace(
            self._descriptor,
            hardware_serial=(
                self.hardware_serial if hardware_serial is None else hardware_serial
            ),
            manufacturer=(self.manufacturer if manufacturer is None else manufacturer),
            model=self.model if model is None else model,
        )
        stable_key = _derive_stable_key_value(
            hardware_serial=updated.hardware_serial,
            product=updated.product,
            model=updated.model,
            manufacturer=updated.manufacturer,
            fingerprint_when_no_serial=True,
        )
        updated = replace(updated, stable_key=stable_key)
        tier_one_identity = PhoneIdentity.from_stable_key(stable_key)
        if tier_one_identity is not None:
            self._identity = tier_one_identity
        self._descriptor = self._with_derived_name(updated)

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
        """Atomically apply normalized Android shell properties.

        Blank enrichment values preserve existing metadata except for the friendly
        device name, which may be cleared. Derived identity and display state are
        recomputed once after all inputs have been merged.

        Args:
            manufacturer: Hardware manufacturer reported by Android properties.
            model: Commercial model reported by Android properties.
            shell_device_name: Friendly device name, which may be blank.
            os: Android release string.
            android_api_level: Android SDK API level, or ``None`` when unknown.
            hardware_serial: Hardware serial; blank and ``"unknown"`` preserve a
                previously known serial.
        """
        current = self._descriptor
        serial = hardware_serial.strip()
        if not serial or serial.casefold() == "unknown":
            serial = current.hardware_serial
        updated = replace(
            current,
            manufacturer=manufacturer.strip() or current.manufacturer,
            model=model.strip() or current.model,
            shell_device_name=shell_device_name.strip(),
            os=os.strip() or current.os,
            android_api_level=(
                android_api_level
                if android_api_level is not None
                else current.android_api_level
            ),
            hardware_serial=serial,
        )
        stable_key = _derive_stable_key_value(
            hardware_serial=updated.hardware_serial,
            product=updated.product,
            model=updated.model,
            manufacturer=updated.manufacturer,
            fingerprint_when_no_serial=True,
        )
        updated = replace(updated, stable_key=stable_key)
        tier_one_identity = PhoneIdentity.from_stable_key(stable_key)
        if tier_one_identity is not None:
            self._identity = tier_one_identity
        self._descriptor = self._with_derived_name(updated)

    def add_connection(self, connection: AdbConnection) -> None:
        """Add or replace one ADB connection snapshot by endpoint identifier.

        Args:
            connection: Immutable endpoint snapshot to attach to this phone.
        """
        by_id = {item.id: item for item in self._connections}
        by_id[connection.id] = connection
        self._connections = tuple(by_id[key] for key in sorted(by_id))
        if self._preferred_connection_id is None:
            self._preferred_connection_id = self._choose_target_connection_id()
        self._descriptor = self._with_derived_name(self._descriptor)

    def apply_discovery(self, discovered: Phone) -> None:
        """Apply a complete discovery aggregate while preserving this instance.

        Inactive observations retain the previous connection timestamp for the
        same endpoint. Connections absent from the new snapshot are removed.

        Args:
            discovered: Fresh physical-phone aggregate from ADB discovery.
        """
        previous = {connection.id: connection for connection in self._connections}
        connections: list[AdbConnection] = []
        for connection in discovered.connections:
            old = previous.get(connection.id)
            if connection.last_connection is None and old is not None:
                connection = replace(connection, last_connection=old.last_connection)
            connections.append(connection)
        self._connections = tuple(sorted(connections, key=lambda item: item.id))
        self._descriptor = discovered.descriptor
        if not discovered.identity.is_provisional:
            self._identity = discovered.identity
        preferred = self.connection_by_id(self._preferred_connection_id or "")
        if preferred is None or not preferred.is_active:
            self._preferred_connection_id = self._choose_target_connection_id()
        self._descriptor = self._with_derived_name(self._descriptor)

    def serialize(self, **kwargs: object) -> dict[str, object]:
        """Serialize physical metadata and all ADB connections.

        Args:
            **kwargs: Serialization options. ``json_compatible=True`` converts
                connection timestamps to ISO 8601 strings.

        Returns:
            A payload suitable for persistence or application events.
        """
        json_compatible = bool(kwargs.get("json_compatible", False))
        return {
            "id": self.identity.value,
            "name": self.name,
            "os": self.os,
            "product": self.product,
            "model": self.model,
            "device": self.descriptor.device,
            "stable_key": self.stable_key,
            "hardware_serial": self.hardware_serial,
            "manufacturer": self.manufacturer,
            "android_api_level": self.android_api_level,
            "shell_device_name": self.shell_device_name,
            "preferred_connection_id": self.preferred_connection_id,
            "connections": [
                connection.serialize(json_compatible=json_compatible)
                for connection in self.connections
            ],
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs: object) -> Phone:
        """Restore a phone aggregate from current or legacy serialized data.

        Args:
            payload: Serialized phone data. Current payloads contain a
                ``connections`` list; legacy payloads describe one endpoint.
            **kwargs: Reserved deserialization options accepted by the payload
                protocol.

        Returns:
            A validated phone aggregate with restored connection preference.

        Raises:
            KeyError: If a required physical identity or connection id is absent.
            TypeError: If connection fields violate their value-object contract.
            ValueError: If the payload has no valid connections or contains
                malformed connection data.
        """
        raw_connections = payload.get("connections")
        if isinstance(raw_connections, list) and raw_connections:
            connections = [
                AdbConnection.deserialize(item)
                for item in raw_connections
                if isinstance(item, dict)
            ]
            if not connections:
                raise ValueError("phone payload contains no valid ADB connections")
            identity = PhoneIdentity(str(payload["id"]))
        else:
            connection = AdbConnection.deserialize(payload)
            connections = [connection]
            identity = (
                PhoneIdentity.from_stable_key(str(payload.get("stable_key") or ""))
                or PhoneIdentity.provisional()
            )
        phone = cls(
            connections[0],
            identity=identity,
            name=str(payload.get("name") or ""),
            os=str(payload.get("os") or ""),
            device=str(payload.get("device") or payload.get("name") or ""),
            product=str(payload.get("product") or ""),
            model=str(payload.get("model") or ""),
            hardware_serial=str(payload.get("hardware_serial") or ""),
            manufacturer=str(payload.get("manufacturer") or ""),
            android_api_level=(
                cast(int, payload["android_api_level"])
                if isinstance(payload.get("android_api_level"), int)
                else None
            ),
        )
        phone._identity = identity
        phone._connections = tuple(sorted(connections, key=lambda item: item.id))
        phone._descriptor = replace(
            phone._descriptor,
            stable_key=str(payload.get("stable_key") or phone.stable_key),
            shell_device_name=str(payload.get("shell_device_name") or ""),
        )
        preferred = payload.get("preferred_connection_id")
        phone._preferred_connection_id = (
            str(preferred)
            if preferred is not None
            and phone.connection_by_id(str(preferred)) is not None
            else phone._choose_target_connection_id()
        )
        phone._descriptor = phone._with_derived_name(phone._descriptor)
        return phone

    def __str__(self) -> str:
        """Return a concise human-readable phone and connection summary."""
        target = self.display_connection
        details = [self.name]
        if self.os:
            android = f"Android {self.os}"
            if self.android_api_level is not None:
                android += f" (API {self.android_api_level})"
            details.append(android)
        connection_type = "Wi-Fi" if target.connectivity_type == "wifi" else "USB"
        details.append(f"{connection_type}: {target.id}")
        if target.state:
            details.append(f"State: {target.state}")
        return " | ".join(details)

    def __repr__(self) -> str:
        """Return a developer-oriented aggregate representation."""
        return (
            f"Phone(identity={self.identity.value!r}, name={self.name!r}, "
            f"connections={self.connections!r})"
        )


def serialize_phone_collection(phones: Iterable[Phone]) -> list[dict[str, object]]:
    """Serialize phones while retaining native datetime values.

    Args:
        phones: Phone aggregates to serialize.

    Returns:
        Serialized payloads in input iteration order.
    """
    return [phone.serialize(json_compatible=False) for phone in phones]


class PhoneRepository:
    """Own physical phones and index every current ADB connection.

    Membership and mutation are identity-safe: only the exact stored ``Phone``
    instance is considered owned.
    """

    def __init__(self) -> None:
        """Initialize an empty repository without a working phone."""
        self._phones: dict[str, Phone] = {}
        self._connections: dict[str, Phone] = {}
        self._working_device: Phone | None = None

    def get(self, phone_id: str) -> Phone | None:
        """Resolve a physical identity to its canonical phone instance.

        Args:
            phone_id: Serialized physical-phone identity.

        Returns:
            The stored phone, or ``None`` when the identity is unknown.
        """
        return self._phones.get(phone_id)

    def get_by_connection_id(self, connection_id: str) -> Phone | None:
        """Resolve an ADB endpoint to its owning canonical phone.

        Args:
            connection_id: ADB endpoint identifier.

        Returns:
            The owning phone, or ``None`` when the endpoint is unknown.
        """
        return self._connections.get(connection_id)

    @property
    def working_device(self) -> Phone | None:
        """Return the currently selected canonical phone."""
        return self._working_device

    @working_device.setter
    def working_device(self, device: Phone | None) -> None:
        """Select an owned phone or clear the selection.

        Args:
            device: Exact stored instance to select, or ``None`` to clear it.

        Raises:
            ValueError: If ``device`` is not the exact stored instance.
        """
        if device is not None and device not in self:
            raise ValueError(
                f"Phone with identity {device.identity.value} is not in repository"
            )
        self._working_device = device

    def add(self, item: Phone) -> None:
        """Add a phone when its identity and endpoints are unclaimed.

        Rejected duplicates are logged and leave repository state unchanged.

        Args:
            item: Phone instance to own.
        """
        identity = item.identity.value
        if identity in self._phones:
            logger.error("Phone could not be added to repository", phone_id=identity)
            return
        duplicate = next(
            (item.id for item in item.connections if item.id in self._connections), None
        )
        if duplicate is not None:
            logger.error(
                "Phone could not be added to repository", connection_id=duplicate
            )
            return
        self._phones[identity] = item
        for connection in item.connections:
            self._connections[connection.id] = item
        if self._working_device is None:
            self._working_device = item

    def add_all(self, items: list[Phone]) -> None:
        """Attempt to add each phone in order.

        Args:
            items: Phone instances to add.
        """
        for item in items:
            self.add(item)

    def remove(self, item: Phone) -> None:
        """Remove an exact owned instance and all of its endpoint indexes.

        Rejected instances are logged and leave repository state unchanged.

        Args:
            item: Exact canonical instance to remove.
        """
        if self._phones.get(item.identity.value) is not item:
            logger.error(
                "Phone could not be removed from repository",
                phone_id=item.identity.value,
            )
            return
        self._phones.pop(item.identity.value)
        for connection_id, owner in list(self._connections.items()):
            if owner is item:
                self._connections.pop(connection_id)
        if self._working_device is item:
            self._working_device = None

    def reindex(
        self,
        item: Phone,
        *,
        old_identity: str,
        old_connection_ids: Iterable[str],
    ) -> None:
        """Atomically refresh indexes after mutating a canonical phone.

        Args:
            item: Exact stored phone instance whose indexes changed.
            old_identity: Identity under which the phone is currently stored.
            old_connection_ids: Endpoint identifiers indexed before mutation.

        Raises:
            ValueError: If the phone is not owned under ``old_identity`` or its
                new identity or endpoints collide with another phone.
        """
        if self._phones.get(old_identity) is not item:
            raise ValueError("phone is not owned under its previous identity")
        new_identity = item.identity.value
        owner = self._phones.get(new_identity)
        if owner is not None and owner is not item:
            raise ValueError(f"phone identity {new_identity!r} already exists")
        for connection in item.connections:
            owner = self._connections.get(connection.id)
            if owner is not None and owner is not item:
                raise ValueError(f"ADB connection {connection.id!r} already exists")
        self._phones.pop(old_identity)
        for connection_id in old_connection_ids:
            if self._connections.get(connection_id) is item:
                self._connections.pop(connection_id)
        self._phones[new_identity] = item
        for connection in item.connections:
            self._connections[connection.id] = item

    def index_by_stable_identity(self) -> dict[FirstTierStableKey, Phone]:
        """Index canonical phones by collision-resistant Tier-1 identity.

        Returns:
            The first stored phone for each parsed Tier-1 stable key. Tier-2
            fingerprints and missing keys are excluded.
        """
        indexed: dict[FirstTierStableKey, Phone] = {}
        for phone in self:
            stable_identity = StableKey.from_value(phone.stable_key)
            if isinstance(stable_identity, FirstTierStableKey):
                indexed.setdefault(stable_identity, phone)
        return indexed

    def clear(self) -> None:
        """Remove all phones, endpoint indexes, and working-device state."""
        self._phones.clear()
        self._connections.clear()
        self._working_device = None

    def __len__(self) -> int:
        """Return the number of owned physical phones."""
        return len(self._phones)

    def __iter__(self) -> Iterator[Phone]:
        """Iterate over canonical phones in insertion order."""
        return iter(self._phones.values())

    def __contains__(self, item: Phone) -> bool:
        """Return whether ``item`` is the exact canonical stored instance.

        Args:
            item: Phone instance to test for ownership.

        Returns:
            ``True`` only when the repository stores ``item`` under its identity.
        """
        return self._phones.get(item.identity.value) is item
