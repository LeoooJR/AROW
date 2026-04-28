"""
Application loguru setup: sinks and a format that prints all bound keyword / extra fields.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


class LogOrigin(str, Enum):
    """Logical layer for log lines (MVC-style split)."""

    GUI = "GUI"
    CONTROLLER = "CONTROLLER"
    CORE = "CORE"


# Icon + short tag for a stable-width column (works in UTF-8 log files and most terminals).
_ORIGIN_DISPLAY: dict[LogOrigin, str] = {
    LogOrigin.GUI: "◆ GUI",
    LogOrigin.CONTROLLER: "▣ CTL",
    LogOrigin.CORE: "● CORE",
}

# First directory under ``src/`` → origin (``geo`` is core-side map/data work).
_SRC_CHILD_TO_ORIGIN: dict[str, LogOrigin] = {
    "gui": LogOrigin.GUI,
    "controller": LogOrigin.CONTROLLER,
    "core": LogOrigin.CORE,
    "geo": LogOrigin.CORE,
}

_RESERVED_EXTRA_KEYS = frozenset({"origin"})

_ORIGIN_COL_WIDTH = 9


def logger_for(origin: LogOrigin) -> Any:
    """Logger with ``origin`` bound; use for explicit tags or code outside the usual ``src/*/`` paths."""
    return logger.bind(origin=origin.value)


def _parse_origin_extra(raw: Any) -> LogOrigin | None:
    if raw is None:
        return None
    if isinstance(raw, LogOrigin):
        return raw
    if isinstance(raw, str):
        for member in LogOrigin:
            if member.value == raw:
                return member
    return None


def _infer_origin_from_path(file_path: str) -> LogOrigin | None:
    parts = [p.lower() for p in Path(file_path).parts]
    try:
        i = parts.index("src")
    except ValueError:
        return None
    if i + 1 >= len(parts):
        return None
    return _SRC_CHILD_TO_ORIGIN.get(parts[i + 1])


def _resolve_origin(record: dict[str, Any]) -> LogOrigin | None:
    extra = record.get("extra") or {}
    explicit = _parse_origin_extra(extra.get("origin"))
    if explicit is not None:
        return explicit
    file_info = record.get("file")
    if file_info is None:
        return None
    path_str = getattr(file_info, "path", None)
    if not path_str:
        return None
    return _infer_origin_from_path(str(path_str))


def _origin_column(record: dict[str, Any]) -> str:
    origin = _resolve_origin(record)
    if origin is None:
        return f"{'?':<{_ORIGIN_COL_WIDTH}}"
    return f"{_ORIGIN_DISPLAY[origin]:<{_ORIGIN_COL_WIDTH}}"


def _serialize_extras(record: dict[str, Any]) -> str:
    """
    Build a single-line suffix from ``record["extra"]`` (kwargs from ``logger.info(..., k=v)``,
    ``logger.bind()``, etc.). Keys are sorted for stable, diff-friendly output.
    """
    extra = record.get("extra")
    if not extra:
        return ""
    parts: list[str] = []
    for key in sorted(extra.keys()):
        if key in _RESERVED_EXTRA_KEYS:
            continue
        value = extra[key]
        try:
            parts.append(f"{key}={value!r}")
        except Exception:
            parts.append(f"{key}=<?>")
    return f" | {' '.join(parts)}"


def _escape_braces_for_loguru_format_fragment(text: str) -> str:
    """
    Loguru applies ``str.format_map`` to the full format string. Literal ``{`` / ``}`` in
    serialized values (e.g. ``repr`` of dicts) must be doubled so they are not treated as fields.
    """
    return text.replace("{", "{{").replace("}", "}}")


def _loguru_format(record: dict[str, Any]) -> str:
    """
    Format template for loguru: standard fields plus any keyword/extra context appended literally.
    """
    suffix = _escape_braces_for_loguru_format_fragment(_serialize_extras(record))
    origin = _escape_braces_for_loguru_format_fragment(_origin_column(record))
    return (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        + origin
        + " | {name}:{function}:{line} | {message}"
        + suffix
        + "\n{exception}"
    )


def setup_logger() -> None:
    logger.remove()

    logger.add(
        "arow_{time}.log",
        format=_loguru_format,
        colorize=False,
        encoding="utf-8",
    )
