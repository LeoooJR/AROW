import datetime
import hashlib
import platform
import socket
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

from loguru import logger

from core.collection import Repository
from core.network import is_non_loopback_ipv4

# Prefixes so stored keys remain version-migratable and distinguish Tier 1 vs Tier 2.
_STABLE_HW_PREFIX = "hw:v1:"
_STABLE_FP_PREFIX = "fp:v1:"
_STABLE_PC_INSTALL_PREFIX = "pc:v1:install:"
_FINGERPRINT_V1_MARKER = "|fp|v1|"

# User-visible fallback when manufacturer/model/device_name are unavailable.
DEFAULT_PHONE_DISPLAY_NAME = "Android device"
# When using the default label, append this many chars from the end of the ADB id to disambiguate.
_PHONE_DISPLAY_ID_TAIL_LEN = 8


def _adb_connection_id_is_human_readable(connection_id: str) -> bool:
    """
    True when the ADB connection id is suitable as a list title (emulator, short USB serial).

    Long dotted hostnames (typical of TLS discovery) are treated as not human-readable so we
    show a generic label plus a short suffix instead.
    """
    cid = connection_id.strip()
    if not cid:
        return False
    if cid.startswith("emulator-"):
        return True
    if "." in cid:
        return False
    return len(cid) <= 24


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


def compute_computer_stable_key(install_token: str) -> str:
    """
    Stable logical host identity from the persisted install UUID (controller-owned file).

    Prefix ``pc:v1:install:`` version-migrates independently of phone ``hw:v1:`` / ``fp:v1:`` keys.
    Returns empty when no token is available yet.
    """
    token = (install_token or "").strip()
    if not token:
        return ""
    return f"{_STABLE_PC_INSTALL_PREFIX}{token.casefold()}"


@dataclass(unsafe_hash=True, match_args=True)
class DeviceDescriptor:
    """
    Metadata about the device
    """

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


@dataclass(unsafe_hash=True, match_args=True)
class PhoneDescriptor(DeviceDescriptor):
    """
    Metadata about the phone device
    """

    product: str = field(
        metadata={"description": "The product of the phone"}, default=""
    )
    model: str = field(metadata={"description": "The model of the phone"}, default="")
    device: str = field(
        metadata={
            "description": (
                "Value of the device: column from adb devices -l (display fallback before enrichment)"
            )
        },
        default="",
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
        hash=True,
    )
    manufacturer: str = field(
        metadata={
            "description": "Hardware manufacturer label if filled (optional; improves Tier-2 fingerprints)"
        },
        default="",
    )
    android_api_level: int | None = field(
        metadata={
            "description": "Android API level from ro.build.version.sdk after enrichment (optional)"
        },
        default=None,
    )
    shell_device_name: str = field(
        metadata={
            "description": "Friendly name from getprop device_name after enrichment (optional)"
        },
        default="",
        hash=False,
    )

    def __str__(self):
        return (
            f"{self.id} - {self.name} - {self.os} - {self.ip}:{self.port} - "
            f"{self.product} - {self.model} - {self.transport_id} - {self.state} - "
            f"{self.hardware_serial} - {self.stable_key} - {self.manufacturer} - "
            f"{self.android_api_level} - {self.last_communication}"
        )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(id={self.id}, name={self.name}, os={self.os}, "
            f"ip={self.ip}, port={self.port}, product={self.product}, model={self.model}, "
            f"transport_id={self.transport_id}, state={self.state}, "
            f"hardware_serial={self.hardware_serial!r}, stable_key={self.stable_key!r}, "
            f"manufacturer={self.manufacturer!r}, android_api_level={self.android_api_level!r}, "
            f"shell_device_name={self.shell_device_name!r}, "
            f"last_communication={self.last_communication})"
        )


@dataclass(unsafe_hash=True, match_args=True)
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
    stable_key: str = field(
        metadata={
            "description": "Stable install-scoped host identity (set after startup from persisted UUID)"
        },
        default="",
        hash=True,
    )
    network_available: bool = field(
        metadata={
            "description": "Whether the host has a non-loopback IPv4 address usable for wireless ADB pairing"
        },
        default=False,
    )

    def __str__(self):
        return (
            f"{self.id} - {self.name} - {self.os} - {self.ip}:{self.port} - "
            f"{self.state} - {self.stable_key} - {self.network_available} - "
            f"{self.last_communication}"
        )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(id={self.id}, name={self.name}, os={self.os}, "
            f"ip={self.ip}, port={self.port}, state={self.state}, "
            f"stable_key={self.stable_key!r}, network_available={self.network_available!r}, "
            f"last_communication={self.last_communication})"
        )


D = TypeVar("D", bound=DeviceDescriptor)


class Device(ABC, Generic[D]):
    """
    Device
    """

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
        self._descriptor = descriptor

    @property
    def descriptor(self) -> D:
        return self._descriptor

    @descriptor.setter
    def descriptor(self, value: D) -> None:
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

    def __str__(self):
        return f"{self._descriptor.name} - {self._descriptor.os} - {self._descriptor.ip}:{self._descriptor.port}"

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self._descriptor.id}, name={self._descriptor.name}, os={self._descriptor.os}, ip={self._descriptor.ip}, port={self._descriptor.port})"

    def __hash__(self) -> int:
        return hash(self._descriptor)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Device) and self._descriptor == other._descriptor


class Phone(Device[PhoneDescriptor]):
    """
    Phone device
    """

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
        prod = product or ""
        mod = model or ""
        man_u = manufacturer or ""
        tid = (transport_id.strip() if transport_id else "") or ""
        hs = (hardware_serial.strip() if hardware_serial else "") or ""
        dev_col = (device.strip() if device else "") or ""
        if not dev_col and name:
            dev_col = (name.strip() if name else "") or ""
        stable = compute_phone_stable_key(
            hardware_serial=hs if hs else None,
            product=prod,
            model=mod,
            manufacturer=man_u if man_u.strip() else None,
            fingerprint_when_no_serial=False,
        )
        phone_descriptor = PhoneDescriptor(
            id=id,
            name="",
            os=os or "",
            ip=ip or "",
            port=port,
            product=prod,
            model=mod,
            device=dev_col,
            transport_id=tid,
            state=state or "",
            last_communication=datetime.datetime.now(),
            hardware_serial=hs if hs else "",
            stable_key=stable,
            manufacturer=man_u,
            android_api_level=android_api_level,
            shell_device_name="",
        )
        super().__init__(
            id=id,
            name="",
            os=os or "",
            ip=ip or "",
            port=port,
            descriptor=phone_descriptor,
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


def sync_phone_display_name(phone: Phone) -> None:
    """
    Set ``PhoneDescriptor.name`` from enrichment and list data using a fixed precedence.

    Order: ``getprop device_name`` shell value, ``manufacturer`` + ``model``, ``model`` alone,
    ``product``, ``PhoneDescriptor.device`` (``devices -l`` device column), human-readable connection ``id``, then a default
    label (optionally with a short ``id`` suffix for disambiguation).
    """
    d = phone.descriptor
    shell = (d.shell_device_name or "").strip()
    if shell:
        d.name = shell
        return

    man = (d.manufacturer or "").strip()
    mod = (d.model or "").strip()
    if man and mod:
        d.name = f"{man} {mod}"
        return
    if mod:
        d.name = mod
        return

    prod = (d.product or "").strip()
    if prod:
        d.name = prod
        return

    tok = (d.device or "").strip()
    if tok:
        d.name = tok
        return

    cid = (d.id or "").strip()
    if cid and _adb_connection_id_is_human_readable(cid):
        d.name = cid
        return

    if cid and len(cid) > _PHONE_DISPLAY_ID_TAIL_LEN:
        tail = cid[-_PHONE_DISPLAY_ID_TAIL_LEN:]
        d.name = f"{DEFAULT_PHONE_DISPLAY_NAME} ({tail})"
        return

    d.name = DEFAULT_PHONE_DISPLAY_NAME if not cid else cid


def _recompute_phone_stable_key_descriptor(phone: Phone) -> None:
    """
    After descriptor fields used in Tier-1 / Tier-2 identity change, refresh ``stable_key``.
    """
    man = (phone.descriptor.manufacturer or "").strip()
    hs = (phone.descriptor.hardware_serial or "").strip()
    phone.descriptor.stable_key = compute_phone_stable_key(
        hardware_serial=hs if hs else None,
        product=phone.descriptor.product,
        model=phone.descriptor.model,
        manufacturer=man or None if man else None,
        fingerprint_when_no_serial=True,
    )


def apply_phone_ro_serial_enrichment(phone: Phone, ro_serial_stdout: str) -> None:
    """
    After ``adb shell getprop ro.serialno``, update ``hardware_serial`` and ``stable_key``.

    When stdout is blank or unusable (or ``unknown``), keeps prior ``hardware_serial`` if set;
    recomputes ``stable_key`` with Tier 2 fingerprint if Tier 1 is still unavailable.
    """
    raw = (ro_serial_stdout or "").strip()
    if raw and raw.casefold() != "unknown":
        phone.descriptor.hardware_serial = raw
    _recompute_phone_stable_key_descriptor(phone)


def apply_phone_device_name_enrichment(phone: Phone, value: str) -> None:
    """Apply ``getprop device_name`` to ``shell_device_name`` and refresh the display label."""
    name = (value or "").strip()
    if name:
        phone.descriptor.shell_device_name = name
    else:
        phone.descriptor.shell_device_name = ""
    sync_phone_display_name(phone)
    _recompute_phone_stable_key_descriptor(phone)


def apply_phone_android_release_enrichment(phone: Phone, value: str) -> None:
    """Apply ``ro.build.version.release`` to ``PhoneDescriptor.os`` (Android release string)."""
    rel = (value or "").strip()
    if not rel:
        return
    phone.descriptor.os = rel
    _recompute_phone_stable_key_descriptor(phone)


def apply_phone_manufacturer_enrichment(phone: Phone, value: str) -> None:
    """Apply ``ro.product.manufacturer``; affects Tier-2 ``stable_key`` and display label."""
    man = (value or "").strip()
    if not man:
        return
    phone.descriptor.manufacturer = man
    sync_phone_display_name(phone)
    _recompute_phone_stable_key_descriptor(phone)


def apply_phone_product_model_enrichment(phone: Phone, value: str) -> None:
    """Apply ``ro.product.model`` to ``PhoneDescriptor.model`` and refresh display label."""
    mod = (value or "").strip()
    if not mod:
        return
    phone.descriptor.model = mod
    sync_phone_display_name(phone)
    _recompute_phone_stable_key_descriptor(phone)


def apply_phone_android_api_level_enrichment(phone: Phone, value: int | None) -> None:
    """Apply ``ro.build.version.sdk`` as API level; skip when ``value`` is ``None``."""
    if value is None:
        return
    phone.descriptor.android_api_level = value
    _recompute_phone_stable_key_descriptor(phone)


class Computer(Device[ComputerDescriptor]):
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
        if ip is not None:
            resolved_ip = ip
            network_available = is_non_loopback_ipv4(ip)
        else:
            resolved_ip, network_available = self._resolve_network_identity()
        computer_descriptor = ComputerDescriptor(
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
            descriptor=computer_descriptor,
        )

    @property
    def stable_key(self) -> str:
        return self._descriptor.stable_key

    def get_name(self) -> str:
        return self._descriptor.name

    def get_os(self) -> str:
        return self._descriptor.os

    def get_ip(self) -> str:
        return self._descriptor.ip

    def is_network_available(self) -> bool:
        return self._descriptor.network_available

    def get_port(self) -> int | None:
        return self._descriptor.port

    def get_state(self) -> str | None:
        return self._descriptor.state

    def get_last_communication(self) -> datetime.datetime | None:
        return self._descriptor.last_communication

    def refresh_network_identity(self) -> None:
        ip, network_available = self._resolve_network_identity()
        self._descriptor.ip = ip
        self._descriptor.network_available = network_available

    def _resolve_network_identity(self) -> tuple[str, bool]:
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if is_non_loopback_ipv4(ip):
                return ip, True
        except OSError:
            pass

        try:
            # UDP route probing asks the OS which local address would be used; no packet
            # needs to be exchanged with the target.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            if is_non_loopback_ipv4(ip):
                return ip, True
        except OSError:
            pass
        return "127.0.0.1", False


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
        try:
            super().add(item)
        except ValueError as e:
            logger.error(
                "PhoneRepository: failed to add phone",
                error=str(e),
            )
            return
        if self._working_device is None:
            self._working_device = item

    def remove(self, item: Phone) -> None:
        try:
            super().remove(item)
        except ValueError as e:
            logger.error(
                "PhoneRepository: failed to remove phone",
                error=str(e),
            )
            return
        if self._working_device == item:
            self._working_device = None

    def clear(self) -> None:
        super().clear()
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
        try:
            super().add(item)
        except ValueError as e:
            logger.error(
                "ComputerRepository: failed to add computer",
                error=str(e),
            )
            return
        if self._working_device is None:
            self._working_device = item

    def remove(self, item: Computer) -> None:
        try:
            super().remove(item)
        except ValueError as e:
            logger.error(
                "ComputerRepository: failed to remove computer",
                error=str(e),
            )
            return
        if self._working_device == item:
            self._working_device = None
