from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final

from faker import Faker
from faker.providers import DynamicProvider

from application_paths import APPLICATION_PATHS
from core.adb.binary import AdbBinary
from core.adb.client import AdbClient
from core.adb.command import (
    AdbCommandInvocation,
    AdbCommandResultStatus,
    AdbCommands,
    AdbCommandSpec,
)
from core.adb.exceptions import AdbServerException
from core.adb.execution import (
    AdbCommandExecutor,
    AdbTransportFailure,
    AdbTransportResult,
    AdbTransportScope,
)
from core.adb.server import AdbServer
from core.devices.phone import Phone

AROW_MOCK_ADB_SEED_ENV_VAR: Final[str] = "AROW_MOCK_ADB_SEED"

MOCK_ANDROID_DEVICE_MODEL_ELEMENTS: Final[tuple[str, ...]] = (
    "Pixel 7",
    "Pixel 8 Pro",
    "Galaxy S24 Ultra",
    "Nothing Phone (2)",
    "OnePlus 12",
)

MOCK_ANDROID_DEVICE_MANUFACTURER_ELEMENTS: Final[tuple[str, ...]] = (
    "Google",
    "Samsung",
    "Honor",
    "Nothing",
    "OnePlus",
)

ANDROID_RELEASE_SDK_CHOICES: Final[tuple[tuple[str, int], ...]] = (
    ("13", 33),
    ("14", 34),
    ("15", 35),
)


@dataclass
class MockAdbDeviceProfile:
    """Synthetic device facts shared between mock ``devices -l`` and ``adb shell`` output."""

    manufacturer: str
    model: str
    product: str
    device_codename: str
    ro_serialno: str
    device_name: str
    android_release: str
    sdk: int
    transport_id: int


class MockAdbState:
    """
    Shared faker-backed catalogue of mock-connected devices.

    Keeps ``adb devices -l`` rows aligned with fake ``adb shell`` getprop/settings/dumpsys
    output for each connection id (``adb -s <id>``).
    """

    def __init__(
        self, *, seed: int | None = None, initial_devices: int | None = None
    ) -> None:
        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)
        fake = Faker("en_US", use_weighting=False)
        fake.add_provider(
            DynamicProvider(
                provider_name="mock_android_model",
                elements=list(MOCK_ANDROID_DEVICE_MODEL_ELEMENTS),
            )
        )
        fake.add_provider(
            DynamicProvider(
                provider_name="mock_android_manufacturer",
                elements=list(MOCK_ANDROID_DEVICE_MANUFACTURER_ELEMENTS),
            )
        )

        count = (
            initial_devices
            if initial_devices is not None
            else fake.random_int(min=1, max=2)
        )
        self._faker = fake
        self._ordered_ids: list[str] = []
        self._profiles: dict[str, MockAdbDeviceProfile] = {}
        self._next_transport_id: int = 1
        self._bootstrap_devices(count)

    def _alloc_transport_id(self) -> int:
        tid = self._next_transport_id
        self._next_transport_id += 1
        return tid

    def _bootstrap_devices(self, count: int) -> None:
        for _ in range(max(0, count)):
            tls_id = self._new_tls_connection_id(unique=True)
            tid = self._alloc_transport_id()
            self._profiles[tls_id] = self._build_profile(tid)
            self._ordered_ids.append(tls_id)

    def _new_tls_connection_id(self, *, unique: bool) -> str:
        fake = self._faker
        for _ in range(64):
            left = fake.bothify(
                text="???????????",
                letters="ABCDEFGHJKLMNPQRSTUVWXYZ23456789",
            )
            right = fake.bothify(
                text="??????",
                letters="abcdefghijklmnopqrstuvwxyz0123456789",
            )
            cid = f"adb-{left}-{right}._adb-tls-connect._tcp"
            if not unique or cid not in self._profiles:
                return cid
        raise RuntimeError("MockAdbState: exhausted unique connection ids")

    def _slug_token(self, text: str, max_len: int) -> str:
        base = "".join(ch if ch.isalnum() else "_" for ch in text).strip("_")
        if len(base) > max_len:
            base = base[:max_len]
        return base or "device"

    def _build_profile(self, transport_id: int) -> MockAdbDeviceProfile:
        fake = self._faker
        manufacturer = fake.mock_android_manufacturer()
        model_display = fake.mock_android_model()
        model_slug = self._slug_token(model_display.replace(" ", "_"), 48)
        product = self._slug_token(fake.slug() or fake.word(), 32)
        device_codename = self._slug_token(
            (fake.lexify("??") + "_" + fake.word())[:16], 16
        )
        ro_serialno = fake.bothify(
            text=f"{manufacturer[:3].upper()}-############",
            letters="ABCDEFGHJKLMNPQRSTUVWXYZ",
        ).replace("_", "")[:48]
        if fake.boolean(chance_of_getting_true=40):
            device_name = ""
        else:
            device_name = fake.first_name().replace("\n", " ")[:32]
        pair_release_sdk = ANDROID_RELEASE_SDK_CHOICES[
            fake.random_int(min=0, max=len(ANDROID_RELEASE_SDK_CHOICES) - 1)
        ]
        android_release, sdk = pair_release_sdk
        return MockAdbDeviceProfile(
            manufacturer=manufacturer,
            model=model_slug,
            product=product,
            device_codename=device_codename,
            ro_serialno=ro_serialno,
            device_name=device_name,
            android_release=android_release,
            sdk=sdk,
            transport_id=transport_id,
        )

    def devices_l_blob(self) -> str:
        """Return parser-compatible ``adb devices -l`` output."""
        lines = ["List of devices attached"]
        for did in self._ordered_ids:
            p = self._profiles[did]
            lines.append(
                f"{did} device product:{p.product} model:{p.model} device:{p.device_codename} transport_id:{p.transport_id}"
            )
        return "\n".join(lines) + "\n"

    def ensure_profile_for_id(self, device_id: str) -> MockAdbDeviceProfile:
        if device_id not in self._profiles:
            tid = self._alloc_transport_id()
            self._profiles[device_id] = self._build_profile(tid)
            self._ordered_ids.append(device_id)
        return self._profiles[device_id]

    def register_new_paired_device(self) -> str:
        """Append a freshly generated device profile; return connection id embedded in ``[guid=…]``."""
        new_id = self._new_tls_connection_id(unique=True)
        tid = self._alloc_transport_id()
        self._profiles[new_id] = self._build_profile(tid)
        self._ordered_ids.append(new_id)
        return new_id


def mock_adb_seed_from_env() -> int | None:
    """Parse ``AROW_MOCK_ADB_SEED`` for deterministic mocks; invalid values yield ``None``."""
    raw = (os.environ.get(AROW_MOCK_ADB_SEED_ENV_VAR) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _mock_battery_blob(fake: Faker) -> str:
    level = fake.random_int(min=12, max=98)
    return (
        "Current Battery Service state:\n"
        "  AC powered: false\n"
        "  USB powered: false\n"
        "  Wireless powered: false\n"
        "  Dock powered: false\n"
        "  Max charging current: 0\n"
        "  Max charging voltage: 0\n"
        "  Charge counter: 2848000\n"
        "  status: 3\n"
        "  health: 2\n"
        "  present: true\n"
        f"  level: {level}\n"
        "  scale: 100\n"
        "  voltage: 3906\n"
        "  temperature: 220\n"
        "  technology: Li-ion\n"
        "  Charging state: 0\n"
        "  Charging policy: 0\n"
    )


def _mock_window_blob(profile: MockAdbDeviceProfile) -> str:
    # Mock display state only; no security or cryptographic use.
    awake = random.choice(("true", "false"))  # nosec B311
    screen_on = random.choice(("true", "false"))  # nosec B311
    width = random.choice((1080, 1200))  # nosec B311
    height = random.choice((2400, 2640))  # nosec B311
    return (
        f"      screenState=SCREEN_STATE_{'OFF' if screen_on != 'true' else 'FULL'}\n"
        "WINDOW MANAGER ANIMATOR STATE (dumpsys window animator)\n"
        f"    Display{{#0 state=OFF size={width}x{height} ROTATION_0}}:\n"
        "  DisplayPolicy\n"
        f"    mAwake={awake} mScreenOnEarly={screen_on} mScreenOnFully={screen_on}\n"
        f"mCurrentFocus=Window{{bdf3658 u0 {profile.model}\\MockHome}}\n"
        "mFocusedApp=ActivityRecord{3e3682b u0 com.example/com.example.Activity t999}\n"
    )


def _mock_shell_enrichment_blob(profile: MockAdbDeviceProfile) -> str:
    return (
        f"manufacturer={profile.manufacturer}\n"
        f"model={profile.model.replace('_', ' ')}\n"
        f"device_name={profile.device_name}\n"
        f"android_release={profile.android_release}\n"
        f"sdk={profile.sdk}\n"
        f"ro_serialno={profile.ro_serialno}\n"
    )


class MockAdbTransport:
    """Faker-backed transport that never invokes the local ADB binary."""

    log_label = "Mock ADB"

    def __init__(self, state: MockAdbState) -> None:
        self._state = state

    @property
    def state(self) -> MockAdbState:
        """Return the synthetic device state owned by this transport."""
        return self._state

    def run(
        self,
        invocation: AdbCommandInvocation[object],
        *,
        binary_path: Path,
        scope: AdbTransportScope,
        phone: Phone | None,
        timeout_seconds: float,
    ) -> AdbTransportResult:
        del timeout_seconds
        command = invocation.spec
        handlers = (
            self._client_handlers()
            if scope == "client"
            else self._server_handlers(binary_path)
        )
        handler = handlers.get(command)
        if handler is None:
            raise AdbTransportFailure(
                f"Unsupported mock ADB {scope} command specification: {command.name}"
            )
        out = handler(invocation, phone)
        return AdbTransportResult(output=out)

    def _client_handlers(
        self,
    ) -> dict[
        AdbCommandSpec[object],
        Callable[[AdbCommandInvocation[object], Phone | None], str],
    ]:
        return {
            AdbCommands.PAIR: self._handle_pair,
            AdbCommands.GET_DEVICES: self._handle_get_devices,
            AdbCommands.STATUS: self._handle_status,
            AdbCommands.GET_SERIAL_NO: self._handle_get_serial_no,
            AdbCommands.GET_DEVICE_NAME: self._handle_get_device_name,
            AdbCommands.GET_ANDROID_VERSION: self._handle_get_android_version,
            AdbCommands.GET_MANUFACTURER: self._handle_get_manufacturer,
            AdbCommands.GET_PRODUCT_MODEL: self._handle_get_product_model,
            AdbCommands.GET_SDK_VERSION: self._handle_get_sdk_version,
            AdbCommands.GET_LOCATION_MODE: self._handle_get_location_mode,
            AdbCommands.GET_BATTERY_INFOS: self._handle_get_battery_infos,
            AdbCommands.DUMPSYS_WINDOW: self._handle_dumpsys_window,
            AdbCommands.GET_SHELL_ENRICHMENT_PROPERTIES: self._handle_enrichment,
            AdbCommands.SEND_NOTIFICATION: self._handle_send_notification,
        }

    def _server_handlers(self, binary_path: Path) -> dict[
        AdbCommandSpec[object],
        Callable[[AdbCommandInvocation[object], Phone | None], str],
    ]:
        def _empty(
            invocation: AdbCommandInvocation[object], phone: Phone | None
        ) -> str:
            del invocation, phone
            return ""

        def _mdns(invocation: AdbCommandInvocation[object], phone: Phone | None) -> str:
            del invocation, phone
            return "mdns daemon version [Openscreen discovery 0.0.0]\n"

        def _version(
            invocation: AdbCommandInvocation[object], phone: Phone | None
        ) -> str:
            del invocation, phone
            return (
                "Android Debug Bridge version 1.0.41\n"
                "Version 36.0.0-13206524\n"
                f"Installed as {binary_path}\n"
                "Running on MockOS 0.0.0 (mock)\n"
            )

        return {
            AdbCommands.START_SERVER: _empty,
            AdbCommands.KILL_SERVER: _empty,
            AdbCommands.GET_DEVICES: self._handle_get_devices,
            AdbCommands.MDNS_CHECK: _mdns,
            AdbCommands.GET_BINARY_VERSION: _version,
        }

    def _profile_for_phone(self, phone: Phone | None) -> MockAdbDeviceProfile:
        if phone is None:
            raise AdbTransportFailure("Mock ADB shell command requires a target device")
        return self._state.ensure_profile_for_id(phone.descriptor.id)

    def _handle_pair(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del phone
        if not invocation.dynamic_args:
            raise AdbTransportFailure("Mock ADB pair command requires an endpoint")
        hostport = invocation.dynamic_args[0]
        if ":" not in hostport:
            raise AdbTransportFailure(f"Malformed pair endpoint: {hostport!r}")
        new_id = self._state.register_new_paired_device()
        return f"Successfully paired to {hostport} [guid={new_id}]\n"

    def _handle_get_devices(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation, phone
        return self._state.devices_l_blob()

    def _handle_status(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        if phone is None:
            raise AdbTransportFailure(
                "Mock ADB status command requires a target device"
            )
        return f"{(phone.descriptor.state or 'device').strip()}\n"

    def _handle_get_serial_no(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        return f"{self._profile_for_phone(phone).ro_serialno}\n"

    def _handle_get_device_name(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        device_name = self._profile_for_phone(phone).device_name
        return f"{device_name}\n" if device_name else ""

    def _handle_get_android_version(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        return f"{self._profile_for_phone(phone).android_release}\n"

    def _handle_get_manufacturer(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        return f"{self._profile_for_phone(phone).manufacturer}\n"

    def _handle_get_product_model(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        return f"{self._profile_for_phone(phone).model.replace('_', ' ')}\n"

    def _handle_get_sdk_version(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        return f"{self._profile_for_phone(phone).sdk}\n"

    def _handle_get_location_mode(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        self._profile_for_phone(phone)
        return f"{self._state._faker.random_int(min=0, max=3)}\n"

    def _handle_get_battery_infos(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        self._profile_for_phone(phone)
        return _mock_battery_blob(self._state._faker)

    def _handle_dumpsys_window(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        return _mock_window_blob(self._profile_for_phone(phone))

    def _handle_enrichment(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        del invocation
        return _mock_shell_enrichment_blob(self._profile_for_phone(phone))

    def _handle_send_notification(
        self, invocation: AdbCommandInvocation[object], phone: Phone | None
    ) -> str:
        self._profile_for_phone(phone)
        if len(invocation.dynamic_args) != 4:
            raise AdbTransportFailure(
                "Mock ADB notification command requires tag, title, id, and message"
            )
        return "posting:\n"


class MockAdbClient(AdbClient):
    """ADB client backed by a deterministic in-memory transport."""

    def __init__(
        self,
        *,
        state: MockAdbState,
        binary: AdbBinary | None = None,
    ) -> None:
        self._state = state
        command_binary = binary or AdbBinary(path=APPLICATION_PATHS.mock_adb_binary)
        super().__init__(command_binary)

    def _create_executor(self, binary: AdbBinary) -> AdbCommandExecutor:
        """Create a client executor backed by this facade's mock state."""
        return AdbCommandExecutor(
            binary,
            transport=MockAdbTransport(self._state),
        )


class MockAdbServer(AdbServer):
    """ADB server façade that satisfies lifecycle calls without spawning adb."""

    def __init__(
        self,
        *,
        state: MockAdbState,
        binary: AdbBinary | None = None,
    ) -> None:
        self._state = state
        command_binary = binary or AdbBinary(path=APPLICATION_PATHS.mock_adb_binary)
        super().__init__(command_binary)

    def _create_executor(self, binary: AdbBinary) -> AdbCommandExecutor:
        """Create a server executor backed by this facade's mock state."""
        return AdbCommandExecutor(
            binary,
            transport=MockAdbTransport(self._state),
        )

    def start(self) -> None:
        command = AdbCommands.START_SERVER
        result = self._execute(command.invoke())
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to start adb server: {result}")
        self._paired_devices.clear()
        for device in self.get_known_devices():
            self._paired_devices.add(device)

    def refresh_network_availability(self) -> bool:
        """Keep mock workflows independent from host-specific network state."""
        self._network_available = True
        return self._network_available
