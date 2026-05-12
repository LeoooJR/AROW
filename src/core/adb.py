import datetime
import os
import random
import re
import shlex
import subprocess
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, member
from pathlib import Path
from typing import Any, Callable, Final, Optional

from faker import Faker
from faker.providers import DynamicProvider

ParserFn = Callable[[str], Any]

from core.devices import Phone, PhoneRepository
from core.exceptions import AdbClientException, AdbServerException
from core.location import Location
from logger import logger

# `adb pair` success line: Successfully paired to <host>:<port> [guid=<device_id>]
_PAIR_SUCCESS_LINE = re.compile(
    r"Successfully\s+paired\s+to\s+(\S+)\s+\[guid=([^\]]+)\]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AdbBinary:
    """
    Adb binary
    """

    path: Path = field(
        metadata={"description": "The path to the adb binary"},
        default=Path(__file__).parent / "assets" / "linux" / "plateform-tools" / "adb",
    )
    version: str = field(
        metadata={"description": "The version of the adb binary"}, default=""
    )
    build_date: Optional[datetime.datetime] = field(
        metadata={"description": "The build date of the adb binary"}, default=None
    )
    build_number: Optional[int] = field(
        metadata={"description": "The build number of the adb binary"}, default=None
    )
    build_version: Optional[str] = field(
        metadata={"description": "The build version of the adb binary"}, default=None
    )

    def __str__(self) -> str:
        return f"{self.path} - {self.version} - {self.build_date} - {self.build_number} - {self.build_version}"

    def __repr__(self) -> str:
        return f"AdbBinary(path={self.path}, version={self.version}, build_date={self.build_date}, build_number={self.build_number}, build_version={self.build_version})"


class AdbCommandResultStatus(Enum):
    """
    Status of the command execution
    SUCCESS: The command executed successfully
    ERROR: The command failed to execute
    TIMEOUT: The command timed out
    CONNECTION_ERROR: The command failed to connect to the device
    UNKNOWN_ERROR: The command failed for an unknown reason
    """

    SUCCESS = 0
    ERROR = 1
    TIMEOUT = 2
    CONNECTION_ERROR = 3
    UNKNOWN_ERROR = 4


@dataclass(frozen=True)
class AdbCommandResult:
    """
    Result of the command execution
    """

    status: AdbCommandResultStatus = field(
        metadata={"description": "The status of the command execution"},
        default=AdbCommandResultStatus.UNKNOWN_ERROR,
    )
    phone: Phone | None = field(
        metadata={"description": "The phone the command was executed on"}, default=None
    )
    time: datetime.datetime = field(
        metadata={"description": "The time the command was executed"},
        default=datetime.datetime.now(),
    )
    output: str = field(
        metadata={"description": "The output of the command execution"}, default=""
    )
    error: str = field(
        metadata={"description": "The error of the command execution"}, default=""
    )
    return_code: int = field(
        metadata={"description": "The return code of the command execution"}, default=1
    )


def _make_strip_parser() -> ParserFn:
    """Build a distinct callable for Enum members that only need stripped stdout."""

    def _fn(output: str) -> str:
        return output.strip()

    return _fn


def _parse_pair(output: str) -> Phone | None:
    """
    Parse `adb pair` stdout/stderr into a ``Phone``.

    Success shape (one line): ``Successfully paired to host:port [guid=adb-…]``.
    Device id is the value after ``guid=`` (up to ``]``). Host/port use IPv4 ``host:port``
    parsing via a final ``:`` split.
    """
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _PAIR_SUCCESS_LINE.search(line)
        if not m:
            continue
        hostport, device_id = m.group(1), m.group(2).strip()
        if not device_id or ":" not in hostport:
            continue
        host, port_str = hostport.rsplit(":", 1)
        try:
            port_num = int(port_str)
        except ValueError:
            continue
        if not (1 <= port_num <= 65535):
            continue
        # state ``device`` so downstream ``get_ro_serialno`` runs after pair in auth flow.
        return Phone(
            id=device_id,
            name=None,
            ip=host,
            port=port_num,
            state="device",
        )
    return None


def _parse_devices(output: str) -> list[Phone]:
    """Parse `adb devices -l` stdout into `Phone` rows; skip header and malformed lines."""
    phones: list[Phone] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        tokens = line.split()
        if len(tokens) < 6:
            continue
        try:
            values = list(map(lambda x: x.split(":")[1] if ":" in x else x, tokens))
            id, state, product, model, device, transport_id = values
            phones.append(
                Phone(
                    id=id,
                    product=product,
                    model=model,
                    state=state,
                    transport_id=transport_id,
                    device=device,
                )
            )
        except (ValueError, TypeError):
            continue
    return phones


def _parse_optional_int_line(output: str) -> int | None:
    """Parse a lone integer line (`getprop` sdk, `settings get` ints); empty -> None."""
    text = output.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _normalize_kv_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace("/", "_")


def _coerce_dumpsys_scalar(text: str) -> int | bool | str:
    lowered = text.strip()
    if lowered.lower() in ("true", "false"):
        return lowered.lower() == "true"
    try:
        return int(lowered)
    except ValueError:
        return text.strip()


def _parse_battery(output: str) -> dict[str, int | bool | str]:
    """
    Parse `dumpsys battery` key/value lines after `Current Battery Service state:`.
    Keys are normalized snake_case (e.g. `ac_powered`, `level`).
    """
    parsed: dict[str, int | bool | str] = {}
    in_section = False
    for raw_line in output.splitlines():
        if "Current Battery Service state:" in raw_line:
            in_section = True
            continue
        if not in_section:
            continue
        stripped = raw_line.strip()
        if not stripped:
            if parsed:
                break
            continue
        match = re.match(r"^\s+(.+?):\s*(.+)$", raw_line)
        if match:
            k = _normalize_kv_key(match.group(1))
            parsed[k] = _coerce_dumpsys_scalar(match.group(2))
    return parsed


def _parse_window_summary(output: str) -> dict[str, str | bool | None]:
    """
    Pull a small subset from `dumpsys window` (screen/power/focus/size).
    Keys: m_awake, m_screen_on_fully, screen_state, display_size, m_focused_app, m_current_focus.
    """
    summary: dict[str, str | bool | None] = {}
    m = re.search(r"mAwake=(true|false)", output)
    if m:
        summary["m_awake"] = m.group(1) == "true"
    m = re.search(r"mScreenOnFully=(true|false)", output)
    if m:
        summary["m_screen_on_fully"] = m.group(1) == "true"
    m = re.search(r"screenState=(\S+)", output)
    if m:
        summary["screen_state"] = m.group(1)
    m = re.search(r"Display\{#[0-9]+\s+state=\w+\s+size=([0-9]+x[0-9]+)", output)
    if m:
        summary["display_size"] = m.group(1)
    m = re.search(r"mFocusedApp=(.+)$", output, re.MULTILINE)
    if m:
        summary["m_focused_app"] = m.group(1).strip()
    m = re.search(r"mCurrentFocus=(.+)$", output, re.MULTILINE)
    if m:
        summary["m_current_focus"] = m.group(1).strip()
    return summary


def _parse_notification_post(output: str) -> bool:
    """True when `cmd notification post` echoed a posting confirmation."""
    return "posting:" in output.lower()


class ADBCommandParser(Enum):
    """Structured parsing for stdout shapes documented in adb-commands-output."""

    # Callables must be wrapped with enum.member() or Enum treats them as methods.
    PAIR = member(_parse_pair)
    GET_DEVICES = member(_parse_devices)
    GET_ANDROID_VERSION = member(_make_strip_parser())
    GET_MANUFACTURER = member(_make_strip_parser())
    GET_DEVICE_NAME = member(_make_strip_parser())
    GET_PRODUCT_MODEL = member(_make_strip_parser())
    GET_SDK_VERSION = member(_parse_optional_int_line)
    GET_LOCATION_MODE = member(_parse_optional_int_line)
    GET_SERIAL_NO = member(_make_strip_parser())
    GET_BATTERY_INFOS = member(_parse_battery)
    DUMPSYS_WINDOW = member(_parse_window_summary)
    SEND_NOTIFICATION = member(_parse_notification_post)

    def parse(self, output: str) -> Any:
        """Parse raw adb stdout (or stderr if piped) using this command's rules."""
        fn = self.value
        if not callable(fn):
            raise TypeError(f"{self} has no callable parser")
        return fn(output)


@dataclass(unsafe_hash=True, frozen=True)
class AdbCommand:
    """
    Command to execute
    """

    name: str = field(
        metadata={"description": "The name of the command"}, default="", hash=True
    )
    description: str = field(
        metadata={"description": "The description of the command"}, default=""
    )
    command: str = field(metadata={"description": "The command to execute"}, default="")
    args: list[str] = field(
        metadata={"description": "The arguments to pass to the command"},
        default_factory=list,
    )
    sending_rate: int = field(
        metadata={"description": "The sending rate of the command"}, default=0
    )


class AdbCommands(Enum):
    """
    Commands to execute
    """

    START_SERVER = AdbCommand(
        name="Start ADB Server",
        description="Start the ADB server",
        command="start-server",
    )
    KILL_SERVER = AdbCommand(
        name="Kill ADB Server", description="Kill the ADB server", command="kill-server"
    )
    STATUS = AdbCommand(
        name="ADB status", description="Get the ADB server state", command="get-state"
    )
    GET_DEVICES = AdbCommand(
        name="Get devices",
        description="Get the devices",
        command="devices",
        args=["-l"],
    )
    PAIR = AdbCommand(
        name="Pair with a device", description="Pair with a device", command="pair"
    )
    GET_DEVICE_NAME = AdbCommand(
        name="Get device name",
        description="Get the name of the device",
        command="shell",
        args=["getprop", "device_name"],
    )
    GET_ANDROID_VERSION = AdbCommand(
        name="Get Android version",
        description="Get the Android version",
        command="shell",
        args=["getprop", "ro.build.version.release"],
    )
    GET_BATTERY_INFOS = AdbCommand(
        name="Get battery infos",
        description="Get the battery infos",
        command="shell",
        args=["dumpsys", "battery"],
    )
    GET_MANUFACTURER = AdbCommand(
        name="Get manufacturer",
        description="Get the manufacturer",
        command="shell",
        args=["getprop", "ro.product.manufacturer"],
    )
    GET_SERIAL_NO = AdbCommand(
        name="Serial (ro.serialno)",
        description="Hardware serial via ro.serialno (adb shell getprop ro.serialno)",
        command="shell",
        args=["getprop", "ro.serialno"],
    )
    GET_PRODUCT_MODEL = AdbCommand(
        name="Get product model",
        description="Commercial model string (ro.product.model)",
        command="shell",
        args=["getprop", "ro.product.model"],
    )
    GET_SDK_VERSION = AdbCommand(
        name="Get SDK version",
        description="Android API level (ro.build.version.sdk)",
        command="shell",
        args=["getprop", "ro.build.version.sdk"],
    )
    GET_LOCATION_MODE = AdbCommand(
        name="Get location mode",
        description="Secure settings location_mode (0 off, 3 high accuracy, etc.)",
        command="shell",
        args=["settings", "get", "secure", "location_mode"],
    )
    DUMPSYS_WINDOW = AdbCommand(
        name="Dump window manager",
        description="Large window manager dump (parse summary via ADBCommandParser)",
        command="shell",
        args=["dumpsys", "window"],
    )
    SEND_NOTIFICATION = AdbCommand(
        name="Post connection notification",
        description="Show a status notification on the device after connect",
        command="shell",
        args=[
            "cmd",
            "notification",
            "post",
            "-n",
            "ARROW",
        ],
    )
    SEND_LOCATION = AdbCommand()


ADB_COMMAND_PARSERS: dict[AdbCommands, ADBCommandParser] = {
    AdbCommands.GET_DEVICES: ADBCommandParser.GET_DEVICES,
    AdbCommands.GET_ANDROID_VERSION: ADBCommandParser.GET_ANDROID_VERSION,
    AdbCommands.GET_MANUFACTURER: ADBCommandParser.GET_MANUFACTURER,
    AdbCommands.GET_DEVICE_NAME: ADBCommandParser.GET_DEVICE_NAME,
    AdbCommands.GET_PRODUCT_MODEL: ADBCommandParser.GET_PRODUCT_MODEL,
    AdbCommands.GET_SDK_VERSION: ADBCommandParser.GET_SDK_VERSION,
    AdbCommands.GET_LOCATION_MODE: ADBCommandParser.GET_LOCATION_MODE,
    AdbCommands.GET_SERIAL_NO: ADBCommandParser.GET_SERIAL_NO,
    AdbCommands.GET_BATTERY_INFOS: ADBCommandParser.GET_BATTERY_INFOS,
    AdbCommands.DUMPSYS_WINDOW: ADBCommandParser.DUMPSYS_WINDOW,
    AdbCommands.SEND_NOTIFICATION: ADBCommandParser.SEND_NOTIFICATION,
}


class AdbClient:
    """
    Client to execute adb commands
    """

    def __init__(self, binary: AdbBinary):

        self.binary = binary
        self._history: OrderedDict[
            datetime.datetime, tuple[AdbCommand, AdbCommandResult]
        ] = OrderedDict()

    @property
    def history(
        self,
    ) -> OrderedDict[datetime.datetime, tuple[AdbCommand, AdbCommandResult]]:
        """
        Get the history of the adb client
        """
        return self._history

    @history.setter
    def history(
        self,
        history: OrderedDict[datetime.datetime, tuple[AdbCommand, AdbCommandResult]],
    ) -> None:
        """
        Set the history of the adb client
        """
        self._history = history

    @history.deleter
    def history(self) -> None:
        """
        Delete the history of the adb client
        """
        self._history.clear()

    def add_to_history(self, command: AdbCommand, result: AdbCommandResult) -> None:
        """
        Add to the history of the adb client
        """
        self._history[datetime.datetime.now()] = (command, result)

    def remove_from_history(self, command: AdbCommand) -> None:
        """
        Remove from the history of the adb client
        """
        self._history.pop(datetime.datetime.now())

    def pair(self, ip: str, port: int, association_code: str) -> Phone:
        """
        Pair with a device and return a ``Phone`` parsed from adb output (``guid=`` id).
        """
        command = AdbCommands.PAIR.value
        try:
            result = self._execute(command, None, [f"{ip}:{port}", association_code])
        except AdbClientException as e:
            raise
        combined = f"{result.output or ''}\n{result.error or ''}".strip()
        phone = ADBCommandParser.PAIR.parse(combined)
        if phone is None:
            snippet = combined if len(combined) <= 500 else combined[:500] + "…"
            raise AdbClientException(
                "Unparseable adb pair output (expected 'Successfully paired to … [guid=…]'): "
                f"{snippet}"
            )
        return phone

    def devices(self) -> list[Phone]:
        """
        Get the devices
        """
        command = AdbCommands.GET_DEVICES.value
        try:
            result = self._execute(command, None)
        except AdbClientException as e:
            raise
        return ADBCommandParser.GET_DEVICES.parse(result.output or "")

    def send_notification(self, title: str, message: str) -> bool:
        """
        Send a notification to the device

        Args:
            title: The title of the notification
            message: The message of the notification

        Returns:
            bool: True if the notification was sent successfully, False otherwise
        """
        command = AdbCommands.SEND_NOTIFICATION.value
        try:
            result = self._execute(
                command, None, ["-t", shlex.quote(title), "-m", shlex.quote(message)]
            )
        except AdbClientException as e:
            raise
        return ADBCommandParser.SEND_NOTIFICATION.parse(result.output or "")

    def enable_location_services(self) -> None:
        pass

    def disable_location_services(self) -> None:
        pass

    def set_mock_location(self, location: Location) -> None:
        """
        Define a fake GPS location
        """
        pass

    def get_ro_serialno(self, phone: Phone) -> str:
        """
        Read ``ro.serialno`` on the device: ``adb -s <id> shell getprop ro.serialno``.

        Returns stripped stdout or empty string on failure.
        """
        command = AdbCommands.GET_SERIAL_NO.value
        try:
            result = self._execute(command, phone)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.serialno",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_SERIAL_NO.parse(result.output or "")
        if not parsed:
            return ""
        out = parsed.strip()
        if not out:
            return ""
        logger.debug(
            "AdbClient: ro.serialno read",
            device_id=phone.descriptor.id,
            serial_len=len(out),
        )
        return out

    def get_device_name_prop(self, phone: Phone) -> str:
        """
        ``adb -s <id> shell getprop device_name``. Returns stripped value or ``""`` on failure.
        """
        command = AdbCommands.GET_DEVICE_NAME.value
        try:
            result = self._execute(command, phone)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read device_name",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_DEVICE_NAME.parse(result.output or "")
        return (parsed or "").strip()

    def get_android_release(self, phone: Phone) -> str:
        """
        ``ro.build.version.release`` — Android version string (e.g. ``"15"``).
        """
        command = AdbCommands.GET_ANDROID_VERSION.value
        try:
            result = self._execute(command, phone)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.build.version.release",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_ANDROID_VERSION.parse(result.output or "")
        return (parsed or "").strip()

    def get_product_manufacturer(self, phone: Phone) -> str:
        """``ro.product.manufacturer``."""
        command = AdbCommands.GET_MANUFACTURER.value
        try:
            result = self._execute(command, phone)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.product.manufacturer",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_MANUFACTURER.parse(result.output or "")
        return (parsed or "").strip()

    def get_product_model(self, phone: Phone) -> str:
        """``ro.product.model`` (commercial model string)."""
        command = AdbCommands.GET_PRODUCT_MODEL.value
        try:
            result = self._execute(command, phone)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.product.model",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return ""
        parsed = ADBCommandParser.GET_PRODUCT_MODEL.parse(result.output or "")
        return (parsed or "").strip()

    def get_android_sdk_api_level(self, phone: Phone) -> int | None:
        """``ro.build.version.sdk`` as integer API level, or ``None`` if unreadable."""
        command = AdbCommands.GET_SDK_VERSION.value
        try:
            result = self._execute(command, phone)
        except AdbClientException as exc:
            logger.warning(
                "AdbClient: failed to read ro.build.version.sdk",
                device_id=phone.descriptor.id,
                error=str(exc),
            )
            return None
        return ADBCommandParser.GET_SDK_VERSION.parse(result.output or "")

    def _execute(
        self,
        command: AdbCommand,
        phone: Phone | None = None,
        positional_arguments: list[str] | None = None,
    ) -> AdbCommandResult:
        """
        Execute a command
        """
        positional_arguments = positional_arguments or []
        argv: list[str] = [str(self.binary.path)]
        if phone is not None:
            argv.extend(["-s", phone.descriptor.id])
        argv.extend([command.command, *command.args, *positional_arguments])
        try:
            logger.debug(
                "AdbClient: executing command",
                adb_path=str(self.binary.path),
                command=command.command,
                phone_id=phone.descriptor.id if phone else None,
                argv=argv,
                command_line=" ".join(shlex.quote(arg) for arg in argv),
            )
            result = subprocess.run(argv, capture_output=True, text=True)
            logger.debug(
                "AdbClient: command completed",
                adb_path=str(self.binary.path),
                command=command.command,
                return_code=result.returncode,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
            )
            if result.returncode != 0:
                raise AdbClientException(
                    f"Failed to execute command: {command.command} {command.args}: {result.stderr or result.stdout}"
                )
        except subprocess.CalledProcessError as e:
            raise AdbClientException(
                f"Failed to execute command: {command.command} {command.args}"
            ) from e
        except OSError as e:
            raise AdbClientException(
                f"Failed to run ADB binary {self.binary.path}"
            ) from e
        cmd_result = AdbCommandResult(
            status=AdbCommandResultStatus.SUCCESS,
            phone=phone,
            time=datetime.datetime.now(),
            output=result.stdout or "",
            error=result.stderr or "",
            return_code=result.returncode,
        )
        self.add_to_history(command, cmd_result)
        return cmd_result


class AdbServer:
    """
    ADB Server
    """

    def __init__(self, binary: AdbBinary):

        self.binary = binary
        self._history: OrderedDict[
            datetime.datetime, tuple[AdbCommand, AdbCommandResult]
        ] = OrderedDict()
        self._paired_devices: PhoneRepository = PhoneRepository()
        self.restart()

    @property
    def history(
        self,
    ) -> OrderedDict[datetime.datetime, tuple[AdbCommand, AdbCommandResult]]:
        """
        Get the history of the adb server
        """
        return self._history

    @history.setter
    def history(
        self,
        history: OrderedDict[datetime.datetime, tuple[AdbCommand, AdbCommandResult]],
    ) -> None:
        """
        Set the history of the adb server
        """
        self._history = history

    @history.deleter
    def history(self) -> None:
        """
        Delete the history of the adb server
        """
        self._history.clear()

    def add_to_history(self, command: AdbCommand, result: AdbCommandResult) -> None:
        """
        Add to the history of the adb server
        """
        self._history[datetime.datetime.now()] = (command, result)

    def remove_from_history(self, command: AdbCommand) -> None:
        """
        Remove from the history of the adb server
        """
        self._history.pop(datetime.datetime.now())

    def get_last_command_time(self) -> datetime.datetime:
        """
        Get the time of the last command
        """
        return next(reversed(self.history))

    def get_last_from_history(self) -> tuple[AdbCommand, AdbCommandResult]:
        """
        Get the last command and result
        """
        return self.history[self.get_last_command_time()]

    def get_last_command(self) -> AdbCommand:
        """
        Get the last command
        """
        return self.get_last_from_history()[0]

    def get_last_command_result(self) -> AdbCommandResult:
        """
        Get the last command result
        """
        return self.get_last_from_history()[1]

    @property
    def paired_devices(self) -> PhoneRepository:
        """
        Get the paired devices
        """
        return self._paired_devices

    @paired_devices.setter
    def paired_devices(self, paired_devices: PhoneRepository) -> None:
        """
        Set the paired devices
        """
        self._paired_devices = paired_devices

    @paired_devices.deleter
    def paired_devices(self) -> None:
        """
        Delete the paired devices
        """
        self._paired_devices.clear()

    def start(self) -> None:
        """
        Start the adb server
        """
        command = AdbCommands.START_SERVER.value
        result = self._execute(command)
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to start adb server: {result}")
        # Get known devices
        for device in self.get_known_devices():
            self._paired_devices.add(device)

    def stop(self) -> None:
        """
        Stop the adb server
        """
        command = AdbCommands.KILL_SERVER.value
        result = self._execute(command)
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to stop adb server: {result}")

    def restart(self) -> None:
        """
        Restart the adb server
        """
        try:
            self.stop()
            self.start()
        except AdbServerException as e:
            raise

    def status(self) -> None:
        """
        Get the status of the adb server
        """
        command = AdbCommands.STATUS.value
        result = self._execute(command)
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to get status of adb server: {result}")

    def get_known_devices(self) -> list[Phone]:
        """
        Get the known devices.
        """
        command = AdbCommands.GET_DEVICES.value
        try:
            result = self._execute(command)
        except AdbServerException as e:
            raise AdbClientException(f"Failed to get known devices: {e}") from e
        return ADBCommandParser.GET_DEVICES.parse(result.output or "")

    def _execute(self, command: AdbCommand) -> AdbCommandResult:
        """
        Execute a command
        """
        argv: list[str] = [str(self.binary.path), command.command, *command.args]
        try:
            logger.debug(
                "AdbServer: executing command",
                adb_path=str(self.binary.path),
                command=command.command,
                argv=argv,
                command_line=" ".join(shlex.quote(arg) for arg in argv),
            )
            result = subprocess.run(argv, capture_output=True, text=True)
            logger.debug(
                "AdbServer: command completed",
                adb_path=str(self.binary.path),
                command=command.command,
                return_code=result.returncode,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
            )
            if result.returncode != 0:
                raise AdbServerException(
                    f"Failed to execute command: {command.command} {command.args}: {result.stderr or result.stdout}"
                )
        except subprocess.CalledProcessError as e:
            raise AdbServerException(
                f"Failed to execute command: {command.command} {command.args}"
            ) from e
        except OSError as e:
            raise AdbServerException(
                f"Failed to run ADB binary {self.binary.path}"
            ) from e
        cmd_result = AdbCommandResult(
            status=AdbCommandResultStatus.SUCCESS,
            phone=None,
            time=datetime.datetime.now(),
            output=result.stdout or "",
            error=result.stderr or "",
            return_code=result.returncode,
        )
        self.add_to_history(command, cmd_result)
        return cmd_result


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
    awake = random.choice(("true", "false"))
    screen_on = random.choice(("true", "false"))
    width = random.choice((1080, 1200))
    height = random.choice((2400, 2640))
    return (
        f"      screenState=SCREEN_STATE_{'OFF' if screen_on != 'true' else 'FULL'}\n"
        "WINDOW MANAGER ANIMATOR STATE (dumpsys window animator)\n"
        f"    Display{{#0 state=OFF size={width}x{height} ROTATION_0}}:\n"
        "  DisplayPolicy\n"
        f"    mAwake={awake} mScreenOnEarly={screen_on} mScreenOnFully={screen_on}\n"
        f"mCurrentFocus=Window{{bdf3658 u0 {profile.model}\\MockHome}}\n"
        "mFocusedApp=ActivityRecord{3e3682b u0 com.example/com.example.Activity t999}\n"
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
        if tup == ("getprop", "device_name"):
            return f"{profile.device_name}\n" if profile.device_name else ""
        if tup == ("getprop", "ro.build.version.release"):
            return f"{profile.android_release}\n"
        if tup == ("getprop", "ro.product.manufacturer"):
            return f"{profile.manufacturer}\n"
        if tup == ("getprop", "ro.product.model"):
            return f"{profile.model.replace('_', ' ')}\n"
        if tup == ("getprop", "ro.build.version.sdk"):
            return f"{profile.sdk}\n"
        if tup == ("settings", "get", "secure", "location_mode"):
            return str(fake.random_int(min=0, max=3)) + "\n"
        if tup == ("dumpsys", "battery"):
            return _mock_battery_blob(fake)
        if tup == ("dumpsys", "window"):
            return _mock_window_blob(profile)
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
            phone_id=phone.descriptor.id if phone else None,
            argv=argv,
            command_line=" ".join(shlex.quote(arg) for arg in argv),
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
        else:
            out = ""

        logger.debug(
            "MockAdbClient: command completed (mock)",
            command=command.command,
            stdout_preview=out[:200],
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
            argv=argv,
            command_line=" ".join(shlex.quote(arg) for arg in argv),
        )
        out = ""
        if command.command == "devices" and command.args == ["-l"]:
            out = self._mock_state.devices_l_blob()
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
