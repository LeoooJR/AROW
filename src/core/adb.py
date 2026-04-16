import datetime
import shlex
import subprocess
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger

from core.devices import Phone, PhoneRepository
from core.exceptions import AdbClientException, AdbServerException
from core.location import Location


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


class AdbCommandParser(Enum):
    """
    Parser for the adb commands
    """

    START_SERVER = None
    KILL_SERVER = None
    GET_DEVICES = None
    PAIR = None


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
        command="shell getprop device_name",
    )
    GET_ANDROID_VERSION = AdbCommand(
        name="Get Android version",
        description="Get the Android version",
        command="shell getprop ro.build.version.release",
    )
    GET_BATTERY_INFOS = AdbCommand(
        name="Get battery infos",
        description="Get the battery infos",
        command="shell dumpsys battery",
    )
    GET_MANUFACTURER = AdbCommand(
        name="Get manufacturer",
        description="Get the manufacturer",
        command="shell getprop ro.product.manufacturer",
    )
    SEND_LOCATION = AdbCommand()


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
        return (
            [
                Phone.from_string(line)
                for line in result.output.splitlines()
                if line.strip()
            ]
            if result.output
            else []
        )

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
                "Executing ADB client command | "
                f"adb_path={self.binary.path} "
                f"command={command.command} "
                f"phone_id={phone.descriptor.id if phone else None} "
                f"argv={argv} "
                f"command_line={' '.join(shlex.quote(arg) for arg in argv)}"
            )
            result = subprocess.run(argv, capture_output=True, text=True)
            logger.debug(
                "ADB client command completed | "
                f"adb_path={self.binary.path} "
                f"command={command.command} "
                f"return_code={result.returncode} "
                f"stdout={result.stdout.strip()!r} "
                f"stderr={result.stderr.strip()!r}"
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
        if not result.output:
            return []
        phones: list[Phone] = []
        for line in result.output.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 6:
                continue
            try:
                phones.append(Phone.from_string(line))
            except (ValueError, TypeError):
                continue
        return phones

    def execute(self, command: AdbCommand) -> AdbCommandResult:
        """
        Execute a command
        """
        argv: list[str] = [str(self.binary.path), command.command, *command.args]
        try:
            logger.debug(
                "Executing ADB server command | "
                f"adb_path={self.binary.path} "
                f"command={command.command} "
                f"argv={argv} "
                f"command_line={' '.join(shlex.quote(arg) for arg in argv)}"
            )
            result = subprocess.run(argv, capture_output=True, text=True)
            logger.debug(
                "ADB server command completed | "
                f"adb_path={self.binary.path} "
                f"command={command.command} "
                f"return_code={result.returncode} "
                f"stdout={result.stdout.strip()!r} "
                f"stderr={result.stderr.strip()!r}"
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
