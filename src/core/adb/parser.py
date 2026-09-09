"""
Typed ADB stdout/stderr parsers.

When adding a parser:
1. Add a focused ``parse_*`` function.
2. Attach it to the command specification in ``core.adb.command``.
3. Capture representative output and add parser tests.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Final

from core.adb.binary import AdbBinary
from core.devices.phone import Phone

_PAIR_SUCCESS_LINE = re.compile(
    r"Successfully\s+paired\s+to\s+(\S+)\s+\[guid=([^\]]+)\]",
    re.IGNORECASE,
)

_SHELL_ENRICHMENT_KEY_MANUFACTURER: Final[str] = "manufacturer"
_SHELL_ENRICHMENT_KEY_MODEL: Final[str] = "model"
_SHELL_ENRICHMENT_KEY_DEVICE_NAME: Final[str] = "device_name"
_SHELL_ENRICHMENT_KEY_ANDROID_RELEASE: Final[str] = "android_release"
_SHELL_ENRICHMENT_KEY_SDK: Final[str] = "sdk"
_SHELL_ENRICHMENT_KEY_RO_SERIALNO: Final[str] = "ro_serialno"

ShellEnrichmentProperties = dict[str, str | int | None]


def parse_stripped_output(output: str) -> str:
    """Return stripped ADB output for simple scalar commands."""
    return output.strip()


def parse_pair(output: str) -> Phone | None:
    """
    Parse `adb pair` stdout/stderr into a ``Phone``.

    Success shape (one line): ``Successfully paired to host:port [guid=adb-…]``.
    Device id is the value after ``guid=`` (up to ``]``). Host/port use IPv4
    ``host:port`` parsing via a final ``:`` split.
    """
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _PAIR_SUCCESS_LINE.search(line)
        if not match:
            continue
        hostport, device_id = match.group(1), match.group(2).strip()
        if not device_id or ":" not in hostport:
            continue
        host, port_str = hostport.rsplit(":", 1)
        try:
            port_num = int(port_str)
        except ValueError:
            continue
        if not (1 <= port_num <= 65535):
            continue
        return Phone(
            id=device_id,
            name=None,
            ip=host,
            port=port_num,
            state="device",
        )
    return None


def parse_mdns_check(output: str) -> bool:
    """Return True when `adb mdns check` reports a running mDNS daemon."""
    return "mdns daemon version" in output.casefold()


def parse_binary_version(output: str) -> AdbBinary:
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


def parse_devices(output: str) -> list[Phone]:
    """Parse `adb devices -l` stdout into `Phone` rows; skip malformed lines."""
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


def parse_device_state_from_listing(output: str, device_id: str) -> str | None:
    """Return the state from an exact ``adb devices -l`` row match."""
    for raw_line in output.splitlines():
        tokens = raw_line.strip().split()
        if len(tokens) >= 2 and tokens[0] == device_id:
            return tokens[1]
    return None


def parse_optional_int_line(output: str) -> int | None:
    """Parse a lone integer line; return ``None`` for empty or invalid output."""
    text = output.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_shell_enrichment_properties(output: str) -> ShellEnrichmentProperties:
    """Parse batch shell enrichment output as one ``key=value`` per line."""
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
            parsed[key] = parse_optional_int_line(value)
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


def parse_battery(output: str) -> dict[str, int | bool | str]:
    """Parse the key/value body from ``adb shell dumpsys battery``."""
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
            key = _normalize_kv_key(match.group(1))
            parsed[key] = _coerce_dumpsys_scalar(match.group(2))
    return parsed


def parse_window_summary(output: str) -> dict[str, str | bool | None]:
    """Extract the small window-manager summary consumed by the application."""
    summary: dict[str, str | bool | None] = {}
    match = re.search(r"mAwake=(true|false)", output)
    if match:
        summary["m_awake"] = match.group(1) == "true"
    match = re.search(r"mScreenOnFully=(true|false)", output)
    if match:
        summary["m_screen_on_fully"] = match.group(1) == "true"
    match = re.search(r"screenState=(\S+)", output)
    if match:
        summary["screen_state"] = match.group(1)
    match = re.search(r"Display\{#[0-9]+\s+state=\w+\s+size=([0-9]+x[0-9]+)", output)
    if match:
        summary["display_size"] = match.group(1)
    match = re.search(r"mFocusedApp=(.+)$", output, re.MULTILINE)
    if match:
        summary["m_focused_app"] = match.group(1).strip()
    match = re.search(r"mCurrentFocus=(.+)$", output, re.MULTILINE)
    if match:
        summary["m_current_focus"] = match.group(1).strip()
    return summary


def parse_notification_post(output: str) -> bool:
    """True when `cmd notification post` echoed a posting confirmation."""
    return "posting:" in output.lower()
