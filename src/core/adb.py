import datetime
import re
import shlex
import subprocess
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, member
from pathlib import Path
from typing import Any, Callable, Optional

ParserFn = Callable[[str], Any]

from core.devices import Phone, PhoneRepository
from core.exceptions import AdbClientException, AdbServerException
from core.location import Location
from logger import logger


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


def _parse_devices(output: str) -> list[Phone]:
    """Parse `adb devices -l` stdout into `Phone` rows; skip header and malformed lines."""
    phones: list[Phone] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            phones.append(Phone.from_string(line))
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
            continue
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
    GET_DEVICES = member(_parse_devices)
    GET_ANDROID_VERSION = member(_make_strip_parser())
    GET_MANUFACTURER = member(_make_strip_parser())
    GET_DEVICE_NAME = member(_make_strip_parser())
    GET_PRODUCT_MODEL = member(_make_strip_parser())
    GET_SDK_VERSION = member(_parse_optional_int_line)
    GET_LOCATION_MODE = member(_parse_optional_int_line)
    GET_SERIAL_NO = member(_make_strip_parser())
    SHELL_GET_SERIAL_NO = member(_make_strip_parser())
    GET_BATTERY_INFOS = member(_parse_battery)
    DUMPSYS_WINDOW = member(_parse_window_summary)
    POST_CONNECTION_NOTIFICATION = member(_parse_notification_post)

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
        name="Get serial number (host)",
        description="Serial from adb client for the selected device",
        command="get-serialno",
    )
    SHELL_GET_SERIAL_NO = AdbCommand(
        name="Get serial number (shell)",
        description="Serial from device shell get-serialno",
        command="shell",
        args=["get-serialno"],
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
    POST_CONNECTION_NOTIFICATION = AdbCommand(
        name="Post connection notification",
        description="Show a status notification on the device after connect",
        command="shell",
        args=[
            "cmd",
            "notification",
            "post",
            "-t",
            "Connected with ARROW",
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
    AdbCommands.SHELL_GET_SERIAL_NO: ADBCommandParser.SHELL_GET_SERIAL_NO,
    AdbCommands.GET_BATTERY_INFOS: ADBCommandParser.GET_BATTERY_INFOS,
    AdbCommands.DUMPSYS_WINDOW: ADBCommandParser.DUMPSYS_WINDOW,
    AdbCommands.POST_CONNECTION_NOTIFICATION: ADBCommandParser.POST_CONNECTION_NOTIFICATION,
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

    def pair(self, ip: str, port: int, association_code: str) -> Phone | None:
        """
        Pair with a device
        """
        command = AdbCommands.PAIR.value
        try:
            result = self.execute(command, None, [f"{ip}:{port}", association_code])
        except AdbClientException as e:
            raise AdbClientException(f"Failed to pair with {ip}:{port}") from e
        return Phone.from_string(result.output) if result.output else None

    def devices(self) -> list[Phone]:
        """
        Get the devices
        """
        command = AdbCommands.GET_DEVICES.value
        try:
            result = self.execute(command, None)
        except AdbClientException as e:
            raise AdbClientException(f"Failed to get devices") from e
        return ADBCommandParser.GET_DEVICES.parse(result.output or "")

    def enable_location_services(self) -> None:
        pass

    def disable_location_services(self) -> None:
        pass

    def set_mock_location(self, location: Location) -> None:
        """
        Define a fake GPS location
        """
        pass

    def execute(
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
        self.paired_devices: PhoneRepository = PhoneRepository()
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

    def start(self) -> None:
        """
        Start the adb server
        """
        command = AdbCommands.START_SERVER.value
        result = self.execute(command)
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to start adb server: {result}")
        # Get known devices
        for device in self.get_known_devices():
            self.paired_devices.add_phone(device)

    def stop(self) -> None:
        """
        Stop the adb server
        """
        command = AdbCommands.KILL_SERVER.value
        result = self.execute(command)
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
            raise AdbServerException(f"Failed to restart adb server") from e

    def status(self) -> None:
        """
        Get the status of the adb server
        """
        command = AdbCommands.STATUS.value
        result = self.execute(command)
        if result.status != AdbCommandResultStatus.SUCCESS:
            raise AdbServerException(f"Failed to get status of adb server: {result}")

    def get_known_devices(self) -> list[Phone]:
        """
        Get the known devices.
        """
        command = AdbCommands.GET_DEVICES.value
        try:
            result = self.execute(command)
        except AdbServerException as e:
            raise AdbClientException(f"Failed to get known devices: {e}") from e
        return ADBCommandParser.GET_DEVICES.parse(result.output or "")

    def execute(self, command: AdbCommand) -> AdbCommandResult:
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
