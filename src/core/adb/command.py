"""
ADB command descriptors, result models, history limits, and log redaction.

When adding a command:
1. Add an ``AdbCommands`` member with its ``AdbCommand`` descriptor.
2. Register output parsing in ``core.adb.parser`` when the command has structured output.
3. Tune retry behavior in ``core.adb.retry`` when the default profile is unsuitable.
4. Update the redaction helpers below when argv or output may contain sensitive values.
5. Expose the command from ``AdbClient`` or ``AdbServer`` when model code needs it.
"""

from __future__ import annotations

import datetime
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from core.devices.phone import Phone

_REDACTED_LOG_VALUE: Final[str] = "<redacted>"
_LOG_PREVIEW_LIMIT: Final[int] = 200
ADB_HISTORY_MAX_ENTRIES: Final[int] = 100


class AdbCommandResultStatus(Enum):
    """
    Status of the command execution.

    SUCCESS: The command executed successfully.
    ERROR: Non-retryable command failure (auth, permissions, invalid input, etc.).
    TIMEOUT: The subprocess timed out.
    TRANSIENT_ERROR: Retryable failure after retries are exhausted.
    UNKNOWN_ERROR: Unclassified failure (reserved for future use).
    """

    SUCCESS = 0
    ERROR = 1
    TIMEOUT = 2
    TRANSIENT_ERROR = 3
    UNKNOWN_ERROR = 4


@dataclass(frozen=True)
class AdbCommandResult:
    """Result of an ADB command execution."""

    status: AdbCommandResultStatus = field(
        metadata={"description": "The status of the command execution"},
        default=AdbCommandResultStatus.UNKNOWN_ERROR,
    )
    phone: Phone | None = field(
        metadata={"description": "The phone the command was executed on"}, default=None
    )
    time: datetime.datetime = field(
        metadata={"description": "The time the command was executed"},
        default_factory=datetime.datetime.now,
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


@dataclass(unsafe_hash=True, frozen=True)
class AdbCommand:
    """ADB command descriptor."""

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
    """ADB command catalog."""

    START_SERVER = AdbCommand(
        name="Start ADB Server",
        description="Start the ADB server",
        command="start-server",
    )
    KILL_SERVER = AdbCommand(
        name="Kill ADB Server",
        description="Kill the ADB server",
        command="kill-server",
    )
    STATUS = AdbCommand(
        name="Get device state",
        description="Get the ADB connection state of a specific device (adb get-state)",
        command="get-state",
    )
    GET_DEVICES = AdbCommand(
        name="Get devices",
        description="Get the devices",
        command="devices",
        args=["-l"],
    )
    PAIR = AdbCommand(
        name="Pair with a device",
        description="Pair with a device",
        command="pair",
    )
    MDNS_CHECK = AdbCommand(
        name="Check mDNS availability",
        description="Check whether ADB mDNS discovery is available",
        command="mdns",
        args=["check"],
    )
    GET_BINARY_VERSION = AdbCommand(
        name="Get ADB binary version",
        description="Read bundled ADB binary version metadata",
        command="--version",
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
    GET_SHELL_ENRICHMENT_PROPERTIES = AdbCommand(
        name="Get shell enrichment properties",
        description="Batch getprops used to enrich device metadata",
        command="shell",
        args=[
            "sh",
            "-c",
            (
                "printf 'manufacturer=%s\\n' \"$(getprop ro.product.manufacturer)\"; "
                "printf 'model=%s\\n' \"$(getprop ro.product.model)\"; "
                "printf 'device_name=%s\\n' \"$(getprop device_name)\"; "
                "printf 'android_release=%s\\n' \"$(getprop ro.build.version.release)\"; "
                "printf 'sdk=%s\\n' \"$(getprop ro.build.version.sdk)\"; "
                "printf 'ro_serialno=%s\\n' \"$(getprop ro.serialno)\""
            ),
        ],
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


def _redacted_log_value(value: str | None) -> str | None:
    """Return a fixed redaction token for sensitive log-only fields."""
    if value is None:
        return None
    return _REDACTED_LOG_VALUE


def _command_is_notification_post(command: AdbCommand) -> bool:
    args = tuple(command.args)
    return command.command == "shell" and args[:3] == ("cmd", "notification", "post")


def _command_has_location_payload(command: AdbCommand) -> bool:
    """Return whether a command is expected to carry a location payload."""
    name = command.name.casefold()
    return "send location" in name or "set mock location" in name


def _command_output_is_sensitive(command: AdbCommand) -> bool:
    """Return whether output may contain pairing, device, or payload secrets."""
    if command.command in ("pair", "devices"):
        return True
    if tuple(command.args) == ("getprop", "ro.serialno"):
        return True
    if command.name == "Get shell enrichment properties":
        return True
    return _command_has_location_payload(command)


def _log_safe_argv(command: AdbCommand, argv: list[str]) -> list[str]:
    """Build a log-only argv copy with sensitive values redacted."""
    safe: list[str] = []
    pair_value_index = -1
    if command.command == "pair":
        try:
            pair_value_index = argv.index("pair") + 2
        except ValueError:
            pair_value_index = -1
    command_index = -1
    if _command_has_location_payload(command) and command.command:
        try:
            command_index = argv.index(command.command)
        except ValueError:
            command_index = -1

    redact_next_option_value = False
    for index, value in enumerate(argv):
        if redact_next_option_value:
            safe.append(_REDACTED_LOG_VALUE)
            redact_next_option_value = False
            continue
        if value == "-s":
            safe.append(value)
            redact_next_option_value = True
            continue
        if _command_is_notification_post(command) and value in ("-t", "-m"):
            safe.append(value)
            redact_next_option_value = True
            continue
        if pair_value_index == index:
            safe.append(_REDACTED_LOG_VALUE)
            continue
        if command_index >= 0 and index > command_index:
            safe.append(_REDACTED_LOG_VALUE)
            continue
        safe.append(value)
    return safe


def _log_safe_command_line(command: AdbCommand, argv: list[str]) -> str:
    """Return a shell-like command preview from the redacted argv copy."""
    return " ".join(shlex.quote(arg) for arg in _log_safe_argv(command, argv))


def _log_safe_output_preview(output: str, command: AdbCommand | None = None) -> str:
    """Keep output logs redacted and bounded without changing stored results."""
    if command is not None and output and _command_output_is_sensitive(command):
        return _REDACTED_LOG_VALUE
    if len(output) <= _LOG_PREVIEW_LIMIT:
        return output
    return output[:_LOG_PREVIEW_LIMIT] + "..."
