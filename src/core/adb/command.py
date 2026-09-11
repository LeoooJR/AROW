"""Immutable ADB command specifications, invocations, results, and log redaction."""

from __future__ import annotations

import datetime
import shlex
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Final, Generic, TypeVar

from core.adb.binary import AdbBinary
from core.adb.parser import (
    ShellEnrichmentProperties,
    parse_battery,
    parse_binary_version,
    parse_devices,
    parse_mdns_check,
    parse_notification_post,
    parse_optional_int_line,
    parse_pair,
    parse_shell_enrichment_properties,
    parse_stripped_output,
    parse_window_summary,
)
from core.devices.phone import Phone

_REDACTED_LOG_VALUE: Final[str] = "<redacted>"
_LOG_PREVIEW_LIMIT: Final[int] = 200

ParsedT_co = TypeVar("ParsedT_co", covariant=True)


class AdbCommandResultStatus(Enum):
    """Status of an ADB command execution."""

    SUCCESS = 0
    ERROR = 1
    TIMEOUT = 2
    TRANSIENT_ERROR = 3
    UNKNOWN_ERROR = 4


class AdbRetryPolicy(Enum):
    """Retry profile identity selected explicitly by each command specification."""

    PAIR = auto()
    KILL_SERVER = auto()
    DAEMON = auto()
    CLIENT = auto()
    DEFAULT = auto()


@dataclass(frozen=True, slots=True)
class AdbLogPolicy:
    """Declarative rules for rendering an invocation safely in logs."""

    output_sensitive: bool = False
    sensitive_dynamic_arg_indexes: frozenset[int] = frozenset()


@dataclass(frozen=True, slots=True)
class AdbCommandSpec(Generic[ParsedT_co]):
    """Static, typed definition of one logical ADB command."""

    name: str
    description: str
    argv: tuple[str, ...]
    parser: Callable[[str], ParsedT_co]
    retry_policy: AdbRetryPolicy
    log_policy: AdbLogPolicy = AdbLogPolicy()

    def parse(self, output: str) -> ParsedT_co:
        """Parse raw ADB output using this command's declared parser."""
        return self.parser(output)

    def invoke(self, *dynamic_args: str) -> AdbCommandInvocation[ParsedT_co]:
        """Bind runtime arguments to this specification."""
        return AdbCommandInvocation(spec=self, dynamic_args=tuple(dynamic_args))


@dataclass(frozen=True, slots=True)
class AdbCommandInvocation(Generic[ParsedT_co]):
    """One immutable invocation of an ADB command specification."""

    spec: AdbCommandSpec[ParsedT_co]
    dynamic_args: tuple[str, ...] = ()

    def argv(self, binary_path: Path, *, device_id: str | None = None) -> list[str]:
        """Build the complete argument-safe subprocess argv."""
        values = [str(binary_path)]
        if device_id is not None:
            values.extend(("-s", device_id))
        values.extend(self.spec.argv)
        values.extend(self.dynamic_args)
        return values


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


class AdbCommands:
    """Canonical namespace of typed ADB command specifications."""

    START_SERVER: Final[AdbCommandSpec[str]] = AdbCommandSpec(
        name="Start ADB Server",
        description="Start the ADB server",
        argv=("start-server",),
        parser=parse_stripped_output,
        retry_policy=AdbRetryPolicy.DAEMON,
    )
    KILL_SERVER: Final[AdbCommandSpec[str]] = AdbCommandSpec(
        name="Kill ADB Server",
        description="Kill the ADB server",
        argv=("kill-server",),
        parser=parse_stripped_output,
        retry_policy=AdbRetryPolicy.KILL_SERVER,
    )
    STATUS: Final[AdbCommandSpec[str]] = AdbCommandSpec(
        name="Get device state",
        description="Get the ADB connection state of a specific device (adb get-state)",
        argv=("get-state",),
        parser=parse_stripped_output,
        retry_policy=AdbRetryPolicy.DAEMON,
    )
    GET_DEVICES: Final[AdbCommandSpec[list[Phone]]] = AdbCommandSpec(
        name="Get devices",
        description="Get the devices",
        argv=("devices", "-l"),
        parser=parse_devices,
        retry_policy=AdbRetryPolicy.DAEMON,
        log_policy=AdbLogPolicy(output_sensitive=True),
    )
    PAIR: Final[AdbCommandSpec[Phone | None]] = AdbCommandSpec(
        name="Pair with a device",
        description="Pair with a device",
        argv=("pair",),
        parser=parse_pair,
        retry_policy=AdbRetryPolicy.PAIR,
        log_policy=AdbLogPolicy(
            output_sensitive=True,
            sensitive_dynamic_arg_indexes=frozenset((1,)),
        ),
    )
    MDNS_CHECK: Final[AdbCommandSpec[bool]] = AdbCommandSpec(
        name="Check mDNS availability",
        description="Check whether ADB mDNS discovery is available",
        argv=("mdns", "check"),
        parser=parse_mdns_check,
        retry_policy=AdbRetryPolicy.DEFAULT,
    )
    GET_BINARY_VERSION: Final[AdbCommandSpec[AdbBinary]] = AdbCommandSpec(
        name="Get ADB binary version",
        description="Read bundled ADB binary version metadata",
        argv=("--version",),
        parser=parse_binary_version,
        retry_policy=AdbRetryPolicy.DEFAULT,
    )
    GET_DEVICE_NAME: Final[AdbCommandSpec[str]] = AdbCommandSpec(
        name="Get device name",
        description="Get the name of the device",
        argv=("shell", "getprop", "device_name"),
        parser=parse_stripped_output,
        retry_policy=AdbRetryPolicy.CLIENT,
    )
    GET_ANDROID_VERSION: Final[AdbCommandSpec[str]] = AdbCommandSpec(
        name="Get Android version",
        description="Get the Android version",
        argv=("shell", "getprop", "ro.build.version.release"),
        parser=parse_stripped_output,
        retry_policy=AdbRetryPolicy.CLIENT,
    )
    GET_BATTERY_INFOS: Final[AdbCommandSpec[dict[str, int | bool | str]]] = (
        AdbCommandSpec(
            name="Get battery infos",
            description="Get the battery infos",
            argv=("shell", "dumpsys", "battery"),
            parser=parse_battery,
            retry_policy=AdbRetryPolicy.CLIENT,
        )
    )
    GET_MANUFACTURER: Final[AdbCommandSpec[str]] = AdbCommandSpec(
        name="Get manufacturer",
        description="Get the manufacturer",
        argv=("shell", "getprop", "ro.product.manufacturer"),
        parser=parse_stripped_output,
        retry_policy=AdbRetryPolicy.CLIENT,
    )
    GET_SERIAL_NO: Final[AdbCommandSpec[str]] = AdbCommandSpec(
        name="Serial (ro.serialno)",
        description="Hardware serial via ro.serialno (adb shell getprop ro.serialno)",
        argv=("shell", "getprop", "ro.serialno"),
        parser=parse_stripped_output,
        retry_policy=AdbRetryPolicy.CLIENT,
        log_policy=AdbLogPolicy(output_sensitive=True),
    )
    GET_PRODUCT_MODEL: Final[AdbCommandSpec[str]] = AdbCommandSpec(
        name="Get product model",
        description="Commercial model string (ro.product.model)",
        argv=("shell", "getprop", "ro.product.model"),
        parser=parse_stripped_output,
        retry_policy=AdbRetryPolicy.CLIENT,
    )
    GET_SDK_VERSION: Final[AdbCommandSpec[int | None]] = AdbCommandSpec(
        name="Get SDK version",
        description="Android API level (ro.build.version.sdk)",
        argv=("shell", "getprop", "ro.build.version.sdk"),
        parser=parse_optional_int_line,
        retry_policy=AdbRetryPolicy.CLIENT,
    )
    GET_SHELL_ENRICHMENT_PROPERTIES: Final[
        AdbCommandSpec[ShellEnrichmentProperties]
    ] = AdbCommandSpec(
        name="Get shell enrichment properties",
        description="Batch getprops used to enrich device metadata",
        argv=(
            "shell",
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
        ),
        parser=parse_shell_enrichment_properties,
        retry_policy=AdbRetryPolicy.CLIENT,
        log_policy=AdbLogPolicy(output_sensitive=True),
    )
    GET_LOCATION_MODE: Final[AdbCommandSpec[int | None]] = AdbCommandSpec(
        name="Get location mode",
        description="Secure settings location_mode (0 off, 3 high accuracy, etc.)",
        argv=("shell", "settings", "get", "secure", "location_mode"),
        parser=parse_optional_int_line,
        retry_policy=AdbRetryPolicy.CLIENT,
    )
    DUMPSYS_WINDOW: Final[AdbCommandSpec[dict[str, str | bool | None]]] = (
        AdbCommandSpec(
            name="Dump window manager",
            description="Large window manager dump parsed into a focused summary",
            argv=("shell", "dumpsys", "window"),
            parser=parse_window_summary,
            retry_policy=AdbRetryPolicy.CLIENT,
        )
    )
    SEND_NOTIFICATION: Final[AdbCommandSpec[bool]] = AdbCommandSpec(
        name="Post connection notification",
        description="Show a status notification on the device after connect",
        argv=("shell", "cmd", "notification", "post", "-n", "ARROW"),
        parser=parse_notification_post,
        retry_policy=AdbRetryPolicy.CLIENT,
        log_policy=AdbLogPolicy(
            sensitive_dynamic_arg_indexes=frozenset((1, 3)),
        ),
    )


def _redacted_log_value(value: str | None) -> str | None:
    """Return a fixed redaction token for sensitive log-only fields."""
    if value is None:
        return None
    return _REDACTED_LOG_VALUE


def _log_safe_argv(
    invocation: AdbCommandInvocation[object],
    binary_path: Path,
    *,
    device_id: str | None = None,
) -> list[str]:
    """Build the complete log-only argv from declarative sensitivity metadata."""
    safe = [str(binary_path)]
    if device_id is not None:
        safe.extend(("-s", _REDACTED_LOG_VALUE))
    safe.extend(invocation.spec.argv)
    sensitive_indexes = invocation.spec.log_policy.sensitive_dynamic_arg_indexes
    safe.extend(
        _REDACTED_LOG_VALUE if index in sensitive_indexes else value
        for index, value in enumerate(invocation.dynamic_args)
    )
    return safe


def _log_safe_command_line(
    invocation: AdbCommandInvocation[object],
    binary_path: Path,
    *,
    device_id: str | None = None,
) -> str:
    """Return a shell-like preview of the invocation's redacted argv."""
    return " ".join(
        shlex.quote(arg)
        for arg in _log_safe_argv(invocation, binary_path, device_id=device_id)
    )


def _log_safe_output_preview(
    output: str, command: AdbCommandSpec[object] | None = None
) -> str:
    """Keep output logs redacted and bounded without changing stored results."""
    if command is not None and output and command.log_policy.output_sensitive:
        return _REDACTED_LOG_VALUE
    if len(output) <= _LOG_PREVIEW_LIMIT:
        return output
    return output[:_LOG_PREVIEW_LIMIT] + "..."
