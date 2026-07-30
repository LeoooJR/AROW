"""
ADB command catalog: descriptors, stdout parsers, retry profiles, and log redaction.

When adding a new command:
1. Add an ``AdbCommands`` enum member with its ``AdbCommand`` descriptor.
2. When stdout must be parsed, add a ``_parse_*`` helper and an ``ADBCommandParser`` member,
   then register the pair in ``ADB_COMMAND_PARSERS`` (and update
   ``test_adb_command_parsers_registry`` in ``src/core/adb/tests/test_adb_parser.py``).
3. Expose the command from ``AdbClient`` or ``AdbServer`` when model code should call it.
4. Tune ``retry_profile_for`` when the default stop/wait/timeout profile is wrong for the
   subcommand shape.
5. Update ``_command_output_is_sensitive`` and ``_log_safe_argv`` (and related helpers) when
   argv or output may contain secrets, device ids, or location payloads.
6. Extend ``_RETRYABLE_ADB_MESSAGE_FRAGMENTS`` or ``_PERMANENT_ADB_MESSAGE_FRAGMENTS`` when
   new ADB failure messages should change retry behavior.
7. Capture sample output in ``adb-commands-output`` and add parser coverage in
   ``src/core/adb/tests/test_adb_parser.py``.
"""

from __future__ import annotations

import datetime
import ipaddress
import re
import shlex
from dataclasses import dataclass, field
from enum import Enum, member
from pathlib import Path
from typing import Any, Callable, Final, Literal

from tenacity import (
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
    wait_fixed,
)

from core.adb.binary import AdbBinary
from core.adb.exceptions import AdbClientException, AdbServerException
from core.devices.phone import Phone
from logger import logger

ParserFn = Callable[[str], Any]

# Parser regex for `adb pair` success lines. Update if platform-tools changes output.
_PAIR_SUCCESS_LINE = re.compile(
    r"Successfully\s+paired\s+to\s+(\S+)\s+\[guid=([^\]]+)\]",
    re.IGNORECASE,
)

# Retryable ADB message fragments. Update when new transient transport failures are observed.
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

# Permanent ADB message fragments. Keep user/action failures here so retries stop quickly.
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

# Log redaction token. Keep stable so tests and log filters can match it.
_REDACTED_LOG_VALUE: Final[str] = "<redacted>"

# Maximum stdout/stderr preview length for non-sensitive command logs.
_LOG_PREVIEW_LIMIT: Final[int] = 200

# Maximum per-client/server command history entries retained for debugging.
ADB_HISTORY_MAX_ENTRIES: Final[int] = 100

# Batch shell enrichment keys. Update together with GET_SHELL_ENRICHMENT_PROPERTIES.
_SHELL_ENRICHMENT_KEY_MANUFACTURER: Final[str] = "manufacturer"
_SHELL_ENRICHMENT_KEY_MODEL: Final[str] = "model"
_SHELL_ENRICHMENT_KEY_DEVICE_NAME: Final[str] = "device_name"
_SHELL_ENRICHMENT_KEY_ANDROID_RELEASE: Final[str] = "android_release"
_SHELL_ENRICHMENT_KEY_SDK: Final[str] = "sdk"
_SHELL_ENRICHMENT_KEY_RO_SERIALNO: Final[str] = "ro_serialno"

# Parsed shape returned by the batch shell enrichment parser.
ShellEnrichmentProperties = dict[str, str | int | None]


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
    """Result of the command execution."""

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


def adb_status_from_process(
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


def adb_status_from_timeout() -> AdbCommandResultStatus:
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


def return_last_adb_retry_outcome(retry_state: Any) -> AdbCommandResult:
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


def raise_client_for_result(command: AdbCommand, result: AdbCommandResult) -> None:
    if result.status != AdbCommandResultStatus.SUCCESS:
        raise AdbClientException(_adb_failure_message(command, result))


def raise_server_for_result(command: AdbCommand, result: AdbCommandResult) -> None:
    if result.status != AdbCommandResultStatus.SUCCESS:
        raise AdbServerException(_adb_failure_message(command, result))


def _redacted_log_value(value: str | None) -> str | None:
    """Return a fixed redaction token for sensitive log-only fields."""
    if value is None:
        return None
    return _REDACTED_LOG_VALUE


def _command_is_notification_post(command: AdbCommand) -> bool:
    args = tuple(command.args)
    return command.command == "shell" and args[:3] == ("cmd", "notification", "post")


def _command_has_location_payload(command: AdbCommand) -> bool:
    """
    True for future commands that are expected to carry coordinates or location payloads.

    Current read-only location commands, such as ``settings get secure location_mode``,
    are intentionally excluded.
    """
    name = command.name.casefold()
    return "send location" in name or "set mock location" in name


def _command_output_is_sensitive(command: AdbCommand) -> bool:
    """True when stdout/stderr may contain pairing codes, device ids, or payloads."""
    if command.command in ("pair", "devices"):
        return True
    if tuple(command.args) == ("getprop", "ro.serialno"):
        return True
    if command.name == "Get shell enrichment properties":
        return True
    return _command_has_location_payload(command)


def _log_safe_argv(command: AdbCommand, argv: list[str]) -> list[str]:
    """Build a log-only argv copy with credentials, device ids, and payloads redacted."""
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
    """Keep stdout/stderr logs bounded without changing stored command results."""
    if command is not None and output and _command_output_is_sensitive(command):
        return _REDACTED_LOG_VALUE
    if len(output) <= _LOG_PREVIEW_LIMIT:
        return output
    return output[:_LOG_PREVIEW_LIMIT] + "..."


def make_adb_retry_before(
    *,
    scope: _AdbRetryScope,
    command_name: str,
    phone_id: str | None,
) -> Callable[[Any], None]:
    """Build a Tenacity ``before`` callback that logs attempt start and elapsed time."""

    def _before(retry_state: Any) -> None:
        elapsed = retry_state.seconds_since_start
        logger.debug(
            "ADB retry attempt started",
            scope=scope,
            command=command_name,
            phone_id=_redacted_log_value(phone_id),
            attempt=retry_state.attempt_number,
            elapsed_s=round(elapsed, 3) if elapsed is not None else 0.0,
        )

    return _before


def make_adb_retry_after(
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
            "ADB retry attempt completed",
            scope=scope,
            command=command_name,
            phone_id=_redacted_log_value(phone_id),
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


def _parse_mdns_check(output: str) -> bool:
    """Return True when `adb mdns check` reports a running mDNS daemon."""
    return "mdns daemon version" in output.casefold()


def _parse_binary_version(output: str) -> AdbBinary:
    """Parse `adb --version` output into bundled binary metadata."""
    version = ""
    build_version: str | None = None
    build_number: int | None = None
    installed_path: Path | None = None
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        if not version:
            version = line
            continue
        if line.startswith("Version "):
            build_version = line.removeprefix("Version ").strip() or None
            if build_version is not None:
                suffix = build_version.rsplit("-", 1)[-1]
                try:
                    build_number = int(suffix)
                except ValueError:
                    build_number = None
            continue
        if line.startswith("Installed as "):
            installed_path = Path(line.removeprefix("Installed as ").strip())
    return AdbBinary(
        path=installed_path or AdbBinary().path,
        version=version,
        build_number=build_number,
        build_version=build_version,
    )


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
            connection_id, state = tokens[:2]
            metadata = dict(token.split(":", 1) for token in tokens[2:] if ":" in token)
            product = metadata["product"]
            model = metadata["model"]
            device = metadata["device"]
            transport_id = metadata["transport_id"]
            ip = ""
            port: int | None = None
            if ":" in connection_id:
                host, port_value = connection_id.rsplit(":", 1)
                ipaddress.IPv4Address(host)
                parsed_port = int(port_value)
                if 1 <= parsed_port <= 65535:
                    ip, port = host, parsed_port
            phones.append(
                Phone(
                    id=connection_id,
                    ip=ip,
                    port=port,
                    product=product,
                    model=model,
                    state=state,
                    transport_id=transport_id,
                    device=device,
                )
            )
        except (KeyError, ValueError, TypeError):
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


def _parse_shell_enrichment_properties(output: str) -> ShellEnrichmentProperties:
    """
    Parse batch enrichment output as one ``key=value`` per line.

    Unknown keys are ignored so device-side command changes remain backward-compatible.
    """
    parsed: ShellEnrichmentProperties = {
        _SHELL_ENRICHMENT_KEY_MANUFACTURER: "",
        _SHELL_ENRICHMENT_KEY_MODEL: "",
        _SHELL_ENRICHMENT_KEY_DEVICE_NAME: "",
        _SHELL_ENRICHMENT_KEY_ANDROID_RELEASE: "",
        _SHELL_ENRICHMENT_KEY_SDK: None,
        _SHELL_ENRICHMENT_KEY_RO_SERIALNO: "",
    }
    valid_keys = set(parsed)
    for raw in output.splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in valid_keys:
            continue
        if key == _SHELL_ENRICHMENT_KEY_SDK:
            parsed[key] = _parse_optional_int_line(value)
            continue
        parsed[key] = value.strip()
    return parsed


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
    MDNS_CHECK = member(_parse_mdns_check)
    GET_BINARY_VERSION = member(_parse_binary_version)
    GET_DEVICES = member(_parse_devices)
    GET_ANDROID_VERSION = member(_make_strip_parser())
    GET_MANUFACTURER = member(_make_strip_parser())
    GET_DEVICE_NAME = member(_make_strip_parser())
    GET_PRODUCT_MODEL = member(_make_strip_parser())
    GET_SDK_VERSION = member(_parse_optional_int_line)
    GET_LOCATION_MODE = member(_parse_optional_int_line)
    GET_SERIAL_NO = member(_make_strip_parser())
    GET_SHELL_ENRICHMENT_PROPERTIES = member(_parse_shell_enrichment_properties)
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
    """Command to execute."""

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


def retry_profile_for(
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
    """Commands to execute."""

    START_SERVER = AdbCommand(
        name="Start ADB Server",
        description="Start the ADB server",
        command="start-server",
    )
    KILL_SERVER = AdbCommand(
        name="Kill ADB Server", description="Kill the ADB server", command="kill-server"
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
        name="Pair with a device", description="Pair with a device", command="pair"
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
    )  # A all in one command to get all the properties at once, reducing the number of adb trips
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
    AdbCommands.MDNS_CHECK: ADBCommandParser.MDNS_CHECK,
    AdbCommands.GET_BINARY_VERSION: ADBCommandParser.GET_BINARY_VERSION,
    AdbCommands.GET_DEVICES: ADBCommandParser.GET_DEVICES,
    AdbCommands.GET_ANDROID_VERSION: ADBCommandParser.GET_ANDROID_VERSION,
    AdbCommands.GET_MANUFACTURER: ADBCommandParser.GET_MANUFACTURER,
    AdbCommands.GET_DEVICE_NAME: ADBCommandParser.GET_DEVICE_NAME,
    AdbCommands.GET_PRODUCT_MODEL: ADBCommandParser.GET_PRODUCT_MODEL,
    AdbCommands.GET_SDK_VERSION: ADBCommandParser.GET_SDK_VERSION,
    AdbCommands.GET_LOCATION_MODE: ADBCommandParser.GET_LOCATION_MODE,
    AdbCommands.GET_SERIAL_NO: ADBCommandParser.GET_SERIAL_NO,
    AdbCommands.GET_SHELL_ENRICHMENT_PROPERTIES: (
        ADBCommandParser.GET_SHELL_ENRICHMENT_PROPERTIES
    ),
    AdbCommands.GET_BATTERY_INFOS: ADBCommandParser.GET_BATTERY_INFOS,
    AdbCommands.DUMPSYS_WINDOW: ADBCommandParser.DUMPSYS_WINDOW,
    AdbCommands.SEND_NOTIFICATION: ADBCommandParser.SEND_NOTIFICATION,
}
