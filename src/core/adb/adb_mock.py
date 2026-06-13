from __future__ import annotations

import datetime
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from faker import Faker
from faker.providers import DynamicProvider

from core.adb.binary import AdbBinary
from core.adb.client import AdbClient
from core.adb.command import (
    AdbCommand,
    AdbCommandResult,
    AdbCommandResultStatus,
    AdbCommands,
    _log_safe_argv,
    _log_safe_command_line,
    _log_safe_output_preview,
    _redacted_log_value,
)
from core.adb.exceptions import AdbClientException, AdbServerException
from core.adb.server import AdbServer
from core.devices import Phone
from logger import logger

DEFAULT_MOCK_ADB_BINARY_PATH: Final[Path] = Path("/mock/adb")

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
        """Stderr/stdout-shaped ``adb devices -l`` list for :class:`ADBCommandParser.GET_DEVICES`."""
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
    raw = (os.environ.get("AROW_MOCK_ADB_SEED") or "").strip()
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


class MockAdbClient(AdbClient):
    """
    ADB client that never spawns adb: emits faker-shaped stdout/stderr compatible with parsers.
    """

    def __init__(
        self,
        *,
        state: MockAdbState,
        binary: AdbBinary | None = None,
    ) -> None:
        super().__init__(binary or AdbBinary(path=DEFAULT_MOCK_ADB_BINARY_PATH))
        self._state = state

    def _fake_shell_stdout(
        self,
        *,
        phone: Phone | None,
        args: list[str],
    ) -> str:
        if phone is None:
            if (
                len(args) >= 3
                and args[0] == "cmd"
                and args[1] == "notification"
                and args[2] == "post"
            ):
                return "posting:\n"
            return ""
        fake = self._faker
        profile = self._state.ensure_profile_for_id(phone.descriptor.id)
        tup = tuple(args)
        if tup == ("getprop", "ro.serialno"):
            return f"{profile.ro_serialno}\n"
        elif tup == ("getprop", "device_name"):
            return f"{profile.device_name}\n" if profile.device_name else ""
        elif tup == ("getprop", "ro.build.version.release"):
            return f"{profile.android_release}\n"
        elif tup == ("getprop", "ro.product.manufacturer"):
            return f"{profile.manufacturer}\n"
        elif tup == ("getprop", "ro.product.model"):
            return f"{profile.model.replace('_', ' ')}\n"
        elif tup == ("getprop", "ro.build.version.sdk"):
            return f"{profile.sdk}\n"
        elif tup == ("settings", "get", "secure", "location_mode"):
            return str(fake.random_int(min=0, max=3)) + "\n"
        elif tup == ("dumpsys", "battery"):
            return _mock_battery_blob(fake)
        elif tup == ("dumpsys", "window"):
            return _mock_window_blob(profile)
        elif len(args) >= 3 and args[0] == "sh" and args[1] == "-c":
            script = args[2]
            if "manufacturer=" in script and "ro_serialno=" in script:
                return _mock_shell_enrichment_blob(profile)
            return ""
        else:
            return ""

    @property
    def _faker(self) -> Faker:
        return self._state._faker

    def _execute(
        self,
        command: AdbCommand,
        phone: Phone | None = None,
        positional_arguments: list[str] | None = None,
    ) -> AdbCommandResult:
        positional_arguments = positional_arguments or []
        argv: list[str] = [str(self.binary.path)]
        if phone is not None:
            argv.extend(["-s", phone.descriptor.id])
        argv.extend([command.command, *command.args, *positional_arguments])
        logger.debug(
            "MockAdbClient: executing command (no subprocess)",
            adb_path=str(self.binary.path),
            command=command.command,
            phone_id=_redacted_log_value(phone.descriptor.id if phone else None),
            argv=_log_safe_argv(command, argv),
            command_line=_log_safe_command_line(command, argv),
        )
        out = ""
        if command.command == "pair":
            hostport = (
                positional_arguments[0] if positional_arguments else "127.0.0.1:5555"
            )
            if ":" not in hostport:
                raise AdbClientException(f"Malformed pair endpoint: {hostport!r}")
            new_id = self._state.register_new_paired_device()
            out = f"Successfully paired to {hostport} [guid={new_id}]\n"
        elif command.command == "devices" and command.args == ["-l"]:
            out = self._state.devices_l_blob()
        elif command.command == "shell":
            out = self._fake_shell_stdout(phone=phone, args=list(command.args))
        elif command.command == "get-state" and phone is not None:
            device_state = (phone.descriptor.state or "device").strip()
            out = f"{device_state}\n"
        else:
            out = ""

        logger.debug(
            "MockAdbClient: command completed (mock)",
            command=command.command,
            stdout_preview=_log_safe_output_preview(out.strip(), command),
        )
        cmd_result = AdbCommandResult(
            status=AdbCommandResultStatus.SUCCESS,
            phone=phone,
            time=datetime.datetime.now(),
            output=out,
            error="",
            return_code=0,
        )
        self.add_to_history(command, cmd_result)
        return cmd_result


class MockAdbServer(AdbServer):
    """ADB server façade that satisfies lifecycle calls without spawning adb."""

    def __init__(
        self,
        *,
        state: MockAdbState,
        binary: AdbBinary | None = None,
    ) -> None:
        self._mock_state = state
        super().__init__(binary or AdbBinary(path=DEFAULT_MOCK_ADB_BINARY_PATH))

    def start(self) -> None:
        command = AdbCommands.START_SERVER.value
        result = self._execute(command)
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to start adb server: {result}")
        self._paired_devices.clear()
        for device in self.get_known_devices():
            self._paired_devices.add(device)

    def _execute(self, command: AdbCommand) -> AdbCommandResult:
        argv: list[str] = [str(self.binary.path), command.command, *command.args]
        logger.debug(
            "MockAdbServer: executing command (no subprocess)",
            adb_path=str(self.binary.path),
            command=command.command,
            argv=_log_safe_argv(command, argv),
            command_line=_log_safe_command_line(command, argv),
        )
        out = ""
        if command.command == "devices" and command.args == ["-l"]:
            out = self._mock_state.devices_l_blob()
        elif command.command == "mdns" and command.args == ["check"]:
            out = "mdns daemon version [Openscreen discovery 0.0.0]\n"
        elif command.command == "--version":
            out = (
                "Android Debug Bridge version 1.0.41\n"
                "Version 36.0.0-13206524\n"
                "Installed as /mock/adb\n"
                "Running on MockOS 0.0.0 (mock)\n"
            )
        cmd_result = AdbCommandResult(
            status=AdbCommandResultStatus.SUCCESS,
            phone=None,
            time=datetime.datetime.now(),
            output=out,
            error="",
            return_code=0,
        )
        self.add_to_history(command, cmd_result)
        return cmd_result
