from __future__ import annotations

import datetime
import re
import shlex
import subprocess
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, member
from pathlib import Path
from typing import Any, Callable, Final, Literal, Optional

from tenacity import (
    Retrying,
    retry_if_exception,
    retry_if_result,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
    wait_fixed,
)

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
    Status of the command execution.

    SUCCESS: The command executed successfully.
    ERROR: Non-retryable command failure (auth, permissions, invalid input, etc.).
    TIMEOUT: The subprocess timed out.
    TRANSIENT_ERROR: Retryable transport/device/server failure after retries are exhausted.
    UNKNOWN_ERROR: Unclassified failure (reserved for future use).
    """

    SUCCESS = 0
    ERROR = 1
    TIMEOUT = 2
    TRANSIENT_ERROR = 3
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


# Substrings that indicate a transient ADB failure worth retrying (case-insensitive).
_RETRYABLE_ADB_MESSAGE_FRAGMENTS: Final[tuple[str, ...]] = (
    "protocol fault",
    "connection reset",
    "error: closed",
    "broken pipe",
    "connection refused",
    "cannot connect",
    "no connection could be made",
    "failed to connect",
    "device offline",
    "device not found",
    "daemon not running",
    "server version mismatch",
    "timed out",
    "timeout",
)

# Substrings that indicate a permanent failure; never retry even if mixed with noise.
_PERMANENT_ADB_MESSAGE_FRAGMENTS: Final[tuple[str, ...]] = (
    "wrong pairing code",
    "wrong",
    "invalid",
    "failed to authenticate",
    "incorrect",
    "pairing code",
    "unauthorized",
    "permission denied",
    "insufficient permissions",
    "failed to run adb binary",
)


@dataclass(frozen=True)
class _AdbRetryProfile:
    """Per-command Tenacity stop/wait boundaries and subprocess timeout."""

    stop: Any
    wait: Any
    timeout_seconds: float


_AdbRetryScope = Literal["client", "server"]


def _message_is_retryable_adb_failure(message: str) -> bool:
    """True when ADB stderr/stdout points to a transient transport or daemon issue."""
    message = message.casefold()
    for fragment in _PERMANENT_ADB_MESSAGE_FRAGMENTS:
        if fragment in message:
            return False
    for fragment in _RETRYABLE_ADB_MESSAGE_FRAGMENTS:
        if fragment in message:
            return True
    return False


def _is_retryable_adb_exception(exc: BaseException) -> bool:
    """
    Return True when an ADB subprocess failure is likely transient.

    Missing binaries (``OSError``) and user-action failures (auth, permissions) are excluded.
    """
    if isinstance(exc, OSError):
        return False
    if not isinstance(exc, (AdbClientException, AdbServerException)):
        return False
    return _message_is_retryable_adb_failure(str(exc))


def _adb_status_from_process(
    *, return_code: int, output: str = "", error: str = ""
) -> AdbCommandResultStatus:
    """
    Map a completed adb process to the project status enum.

    ADB often writes daemon and diagnostic notes to stderr on success, so stderr alone is
    not a failure signal. Non-zero return codes are classified by the message content.
    """
    if return_code == 0:
        return AdbCommandResultStatus.SUCCESS
    combined = f"{output}\n{error}".strip()
    if _message_is_retryable_adb_failure(combined):
        return AdbCommandResultStatus.TRANSIENT_ERROR
    return AdbCommandResultStatus.ERROR


def _adb_status_from_timeout() -> AdbCommandResultStatus:
    """Name timeout status through a helper so timeout construction stays explicit."""
    return AdbCommandResultStatus.TIMEOUT


def _is_retryable_adb_result(result: AdbCommandResult) -> bool:
    """Retry finalizable ADB results only for transient status values/messages."""
    if result.status == AdbCommandResultStatus.TIMEOUT:
        return True
    if result.status == AdbCommandResultStatus.TRANSIENT_ERROR:
        return True
    if result.status != AdbCommandResultStatus.SUCCESS:
        return _message_is_retryable_adb_failure(f"{result.output}\n{result.error}")
    return False


def _return_last_adb_retry_outcome(retry_state: Any) -> AdbCommandResult:
    """
    Return the final result when result-based retries are exhausted.

    Tenacity otherwise raises ``RetryError`` for exhausted result predicates. Exceptions
    still re-raise here so ``reraise=True`` preserves the original exception contract.
    """
    outcome = retry_state.outcome
    if outcome is None:
        raise RuntimeError("ADB retry finished without an outcome")
    if outcome.failed:
        raise outcome.exception()
    return outcome.result()


def _adb_failure_message(command: AdbCommand, result: AdbCommandResult) -> str:
    """Build one consistent exception message from a non-success command result."""
    detail = (result.error or result.output or result.status.name).strip()
    return f"Failed to execute command: {command.command} {command.args}: {detail}"


def _raise_client_for_result(command: AdbCommand, result: AdbCommandResult) -> None:
    if result.status != AdbCommandResultStatus.SUCCESS:
        raise AdbClientException(_adb_failure_message(command, result))


def _raise_server_for_result(command: AdbCommand, result: AdbCommandResult) -> None:
    if result.status != AdbCommandResultStatus.SUCCESS:
        raise AdbServerException(_adb_failure_message(command, result))


def _make_adb_retry_before(
    *,
    scope: _AdbRetryScope,
    command_name: str,
    phone_id: str | None,
) -> Callable[[Any], None]:
    """Build a Tenacity ``before`` callback that logs attempt start and elapsed time."""

    def _before(retry_state: Any) -> None:
        elapsed = retry_state.seconds_since_start
        logger.debug(
            "ADB retry: attempt starting",
            scope=scope,
            command=command_name,
            phone_id=phone_id,
            attempt=retry_state.attempt_number,
            elapsed_s=round(elapsed, 3) if elapsed is not None else 0.0,
        )

    return _before


def _make_adb_retry_after(
    *,
    scope: _AdbRetryScope,
    command_name: str,
    phone_id: str | None,
) -> Callable[[Any], None]:
    """Build a Tenacity ``after`` callback that logs attempt outcome and elapsed time."""

    def _after(retry_state: Any) -> None:
        outcome = retry_state.outcome
        failed = outcome is not None and outcome.failed
        error = str(outcome.exception()) if failed else None
        result = None if outcome is None or failed else outcome.result()
        result_status = getattr(getattr(result, "status", None), "name", None)
        elapsed = retry_state.seconds_since_start
        logger.debug(
            "ADB retry: attempt finished",
            scope=scope,
            command=command_name,
            phone_id=phone_id,
            attempt=retry_state.attempt_number,
            elapsed_s=round(elapsed, 3) if elapsed is not None else 0.0,
            failed=failed,
            result_status=result_status,
            error=error,
        )

    return _after


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


def _retry_profile_for(
    command: AdbCommand, *, scope: _AdbRetryScope
) -> _AdbRetryProfile:
    """
    Select optimized retry boundaries by ADB subcommand shape.

    ``pair`` gets a wider window; shell getters stay short; kill-server is minimal.
    """
    cmd = command.command
    if cmd == "pair":
        return _AdbRetryProfile(
            stop=stop_after_attempt(3) | stop_after_delay(8),
            wait=wait_exponential_jitter(initial=0.3, max=2.0, jitter=0.2),
            timeout_seconds=15.0,
        )
    if cmd == "kill-server":
        return _AdbRetryProfile(
            stop=stop_after_attempt(2) | stop_after_delay(3),
            wait=wait_fixed(0.5),
            timeout_seconds=5.0,
        )
    if cmd in ("start-server", "get-state", "devices"):
        return _AdbRetryProfile(
            stop=stop_after_attempt(3) | stop_after_delay(5),
            wait=wait_exponential_jitter(initial=0.2, max=1.5, jitter=0.1),
            timeout_seconds=10.0,
        )
    if cmd == "shell" or scope == "client":
        return _AdbRetryProfile(
            stop=stop_after_attempt(2) | stop_after_delay(3),
            wait=wait_exponential_jitter(initial=0.15, max=1.0, jitter=0.1),
            timeout_seconds=8.0,
        )
    return _AdbRetryProfile(
        stop=stop_after_attempt(3) | stop_after_delay(5),
        wait=wait_exponential_jitter(initial=0.2, max=1.5, jitter=0.1),
        timeout_seconds=10.0,
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
        _raise_client_for_result(command, result)
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
        _raise_client_for_result(command, result)
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
        _raise_client_for_result(command, result)
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
            _raise_client_for_result(command, result)
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
            _raise_client_for_result(command, result)
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
            _raise_client_for_result(command, result)
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
            _raise_client_for_result(command, result)
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
            _raise_client_for_result(command, result)
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
            _raise_client_for_result(command, result)
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
        Execute a command with Tenacity-backed retries on transient subprocess failures.
        """
        positional_arguments = positional_arguments or []
        argv: list[str] = [str(self.binary.path)]
        if phone is not None:
            argv.extend(["-s", phone.descriptor.id])
        argv.extend([command.command, *command.args, *positional_arguments])
        phone_id = phone.descriptor.id if phone else None
        profile = _retry_profile_for(command, scope="client")

        def _attempt() -> AdbCommandResult:
            logger.debug(
                "AdbClient: executing command",
                adb_path=str(self.binary.path),
                command=command.command,
                phone_id=phone_id,
                argv=argv,
                command_line=" ".join(shlex.quote(arg) for arg in argv),
                timeout_s=profile.timeout_seconds,
            )
            try:
                completed = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=profile.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                error = f"timed out after {profile.timeout_seconds}s"
                logger.debug(
                    "AdbClient: command timed out",
                    adb_path=str(self.binary.path),
                    command=command.command,
                    phone_id=phone_id,
                    error=error,
                )
                return AdbCommandResult(
                    status=_adb_status_from_timeout(),
                    phone=phone,
                    time=datetime.datetime.now(),
                    output=exc.output or "",
                    error=error,
                    return_code=1,
                )
            except subprocess.CalledProcessError as exc:
                raise AdbClientException(
                    f"Failed to execute command: {command.command} {command.args}"
                ) from exc
            except OSError as exc:
                raise AdbClientException(
                    f"Failed to run ADB binary {self.binary.path}"
                ) from exc
            logger.debug(
                "AdbClient: command completed",
                adb_path=str(self.binary.path),
                command=command.command,
                return_code=completed.returncode,
                stdout=completed.stdout.strip(),
                stderr=completed.stderr.strip(),
            )
            return AdbCommandResult(
                status=_adb_status_from_process(
                    return_code=completed.returncode,
                    output=completed.stdout or "",
                    error=completed.stderr or "",
                ),
                phone=phone,
                time=datetime.datetime.now(),
                output=completed.stdout or "",
                error=completed.stderr or "",
                return_code=completed.returncode,
            )

        retryer = Retrying(
            stop=profile.stop,
            wait=profile.wait,
            retry=retry_if_exception(_is_retryable_adb_exception)
            | retry_if_result(_is_retryable_adb_result),
            reraise=True,
            before=_make_adb_retry_before(
                scope="client", command_name=command.command, phone_id=phone_id
            ),
            after=_make_adb_retry_after(
                scope="client", command_name=command.command, phone_id=phone_id
            ),
            retry_error_callback=_return_last_adb_retry_outcome,
        )
        result = retryer(_attempt)
        self.add_to_history(command, result)
        return result


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
            _raise_server_for_result(command, result)
        except AdbServerException as e:
            raise AdbClientException(f"Failed to get known devices: {e}") from e
        return ADBCommandParser.GET_DEVICES.parse(result.output or "")

    def _execute(self, command: AdbCommand) -> AdbCommandResult:
        """
        Execute a command with Tenacity-backed retries on transient subprocess failures.
        """
        argv: list[str] = [str(self.binary.path), command.command, *command.args]
        profile = _retry_profile_for(command, scope="server")

        def _attempt() -> AdbCommandResult:
            logger.debug(
                "AdbServer: executing command",
                adb_path=str(self.binary.path),
                command=command.command,
                argv=argv,
                command_line=" ".join(shlex.quote(arg) for arg in argv),
                timeout_s=profile.timeout_seconds,
            )
            try:
                completed = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=profile.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                error = f"timed out after {profile.timeout_seconds}s"
                logger.debug(
                    "AdbServer: command timed out",
                    adb_path=str(self.binary.path),
                    command=command.command,
                    error=error,
                )
                return AdbCommandResult(
                    status=_adb_status_from_timeout(),
                    phone=None,
                    time=datetime.datetime.now(),
                    output=exc.output or "",
                    error=error,
                    return_code=1,
                )
            except subprocess.CalledProcessError as exc:
                raise AdbServerException(
                    f"Failed to execute command: {command.command} {command.args}"
                ) from exc
            except OSError as exc:
                raise AdbServerException(
                    f"Failed to run ADB binary {self.binary.path}"
                ) from exc
            logger.debug(
                "AdbServer: command completed",
                adb_path=str(self.binary.path),
                command=command.command,
                return_code=completed.returncode,
                stdout=completed.stdout.strip(),
                stderr=completed.stderr.strip(),
            )
            return AdbCommandResult(
                status=_adb_status_from_process(
                    return_code=completed.returncode,
                    output=completed.stdout or "",
                    error=completed.stderr or "",
                ),
                phone=None,
                time=datetime.datetime.now(),
                output=completed.stdout or "",
                error=completed.stderr or "",
                return_code=completed.returncode,
            )

        retryer = Retrying(
            stop=profile.stop,
            wait=profile.wait,
            retry=retry_if_exception(_is_retryable_adb_exception)
            | retry_if_result(_is_retryable_adb_result),
            reraise=True,
            before=_make_adb_retry_before(
                scope="server", command_name=command.command, phone_id=None
            ),
            after=_make_adb_retry_after(
                scope="server", command_name=command.command, phone_id=None
            ),
            retry_error_callback=_return_last_adb_retry_outcome,
        )
        result = retryer(_attempt)
        self.add_to_history(command, result)
        return result
