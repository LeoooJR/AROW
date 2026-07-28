"""
Application loguru setup: sinks and a format that prints all bound keyword / extra fields.
"""

from __future__ import annotations

import os
import re
import tempfile
import time
from collections.abc import Mapping
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

from core.application_paths import (
    default_application_log_file_path,
    get_or_create_application_dir,
)

AROW_LOG_FILE_ENV = (
    "AROW_LOG_FILE"  # Environment variable for the application log file path
)
AROW_LOG_FALLBACK_DIR_ENV = "AROW_LOG_FALLBACK_DIR"
AROW_LOG_SERIALIZE_ENV = "AROW_LOG_SERIALIZE"

_APPLICATION_LOG_ROTATION = "10 MB"
_APPLICATION_LOG_RETENTION = timedelta(days=14)
_APPLICATION_LOG_COMPRESSION = "gz"
_APPLICATION_LOG_GLOB = "application_*.log*"
_JSON_LOG_SCHEMA_VERSION = 1


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

# Extra keys matching these patterns have values replaced in log output (identifiers, pairing codes, secrets).
_SENSITIVE_EXTRA_KEYS_EXACT = frozenset(
    {
        "stable_key",
        "hardware_serial",
        "install_token",
        "install_identity",
        "association_code",
        "password",
        "secret",
        "api_key",
        "authorization",
        "auth_token",
        "access_token",
        "refresh_token",
    }
)
_SENSITIVE_EXTRA_KEY_SUFFIXES = (
    "_token",
    "_secret",
    "_key",
    "_password",
)

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

_ORIGIN_COL_WIDTH = 9


def redact_stable_identifier(text: str) -> str:
    """
    Replace RFC4122-shaped UUID tokens in unstructured log text.

    Intended for explicit use when interpolating identifiers into ``message``.
    Structured ``logger.info(..., key=…)`` extras are sanitized via ``maybe_redact_extra_value``.
    """
    return _UUID_RE.sub("<redacted:uuid>", text)


def maybe_redact_extra_value(key: str, value: Any) -> str:
    """
    Stringify one bound ``extra`` field for serialization, masking sensitive keys and
    UUID-shaped / host-stable-key patterns in repr output.
    """
    kl = key.lower()
    if kl in _SENSITIVE_EXTRA_KEYS_EXACT:
        return "<redacted>"
    if any(kl.endswith(suf) for suf in _SENSITIVE_EXTRA_KEY_SUFFIXES):
        return "<redacted>"
    try:
        raw = repr(value)
    except Exception:
        return "<??>"
    if _UUID_RE.search(raw):
        raw = redact_stable_identifier(raw)
    if "pc:v1:install:" in raw.lower():
        return "<redacted:host_key>"
    return raw


def _sanitize_json_extra_value(key: str, value: Any) -> Any:
    """Return JSON-friendly structured context with nested sensitive values redacted."""
    kl = key.lower()
    if kl in _SENSITIVE_EXTRA_KEYS_EXACT:
        return "<redacted>"
    if any(kl.endswith(suffix) for suffix in _SENSITIVE_EXTRA_KEY_SUFFIXES):
        return "<redacted>"
    if isinstance(value, str):
        if "pc:v1:install:" in value.lower():
            return "<redacted:host_key>"
        return redact_stable_identifier(value)
    if isinstance(value, Mapping):
        return {
            str(nested_key): _sanitize_json_extra_value(str(nested_key), nested_value)
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_json_extra_value(key, item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [
            _sanitize_json_extra_value(key, item) for item in sorted(value, key=repr)
        ]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return maybe_redact_extra_value(key, value)


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
            parts.append(f"{key}={maybe_redact_extra_value(key, value)}")
        except Exception:
            parts.append(f"{key}=<?>")
    return f" | {' '.join(parts)}"


def _escape_braces_for_loguru_format_fragment(text: str) -> str:
    """
    Loguru applies ``str.format_map`` to the full format string. Literal ``{`` / ``}`` in
    serialized values (e.g. ``repr`` of dicts) must be doubled so they are not treated as fields.
    """
    return text.replace("{", "{{").replace("}", "}}")


def _escape_loguru_markup_literals(text: str) -> str:
    """
    Dynamic fragments are concatenated into the format string; loguru otherwise parses ``<name>``
    as color/markup (e.g. redaction placeholders like ``<redacted>``).
    """
    return text.replace("\\", "\\\\").replace("<", "\\<")


def _loguru_format(record: dict[str, Any]) -> str:
    """
    Format template for loguru: standard fields plus any keyword/extra context appended literally.
    """
    suffix = _escape_braces_for_loguru_format_fragment(_serialize_extras(record))
    origin = _escape_braces_for_loguru_format_fragment(_origin_column(record))
    suffix = _escape_loguru_markup_literals(suffix)
    origin = _escape_loguru_markup_literals(origin)
    return (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        + origin
        + " | {name}:{function}:{line} | {message}"
        + suffix
        + "\n{exception}"
    )


def _json_loguru_format(record: dict[str, Any]) -> str:
    """
    Prepare one Loguru record for agent-friendly JSON serialization.

    Loguru's native ``serialize=True`` sink writes the complete record metadata.
    This formatter enriches its structured extras with a stable schema marker and
    inferred application layer while applying the same redaction boundary used by
    the human-readable sink.
    """
    origin = _resolve_origin(record)
    raw_extra = record.get("extra") or {}
    sanitized_extra = {
        str(key): _sanitize_json_extra_value(str(key), value)
        for key, value in raw_extra.items()
        if key != "origin"
    }
    sanitized_extra["log_schema_version"] = _JSON_LOG_SCHEMA_VERSION
    sanitized_extra["origin"] = origin.value if origin is not None else None
    record["extra"] = sanitized_extra
    record["message"] = redact_stable_identifier(str(record["message"]))
    return "{message}\n{exception}"


def resolve_application_log_file_path() -> Path:
    """
    Return the main low-level application log file for this process tree.

    The main process resolves a concrete path under ``<application_dir>/logs`` and stores
    it in :data:`AROW_LOG_FILE_ENV`. Spawned workers use it as the base for isolated
    per-process log paths.
    """
    env_path = os.environ.get(AROW_LOG_FILE_ENV, "").strip()
    if env_path:
        return Path(env_path)
    application_dir = get_or_create_application_dir()
    log_path = default_application_log_file_path(application_dir)
    os.environ[AROW_LOG_FILE_ENV] = str(log_path)
    return log_path


def _fallback_application_log_file_path(original_path: Path) -> Path:
    """
    Return a writable fallback path when the app data directory is unavailable.

    This keeps logging alive in restricted environments such as sandboxes and test
    runners where ``~/.arow`` cannot be created or opened.
    """
    fallback_root = os.environ.get(AROW_LOG_FALLBACK_DIR_ENV, "").strip()
    base_dir = (
        Path(fallback_root).expanduser()
        if fallback_root
        else Path(tempfile.gettempdir()) / "arow-logs"
    )
    return base_dir / original_path.name


def _prune_expired_application_logs(log_dir: Path) -> None:
    """Best-effort cleanup across timestamped application logs from previous runs."""
    cutoff = time.time() - _APPLICATION_LOG_RETENTION.total_seconds()
    try:
        candidates = list(log_dir.glob(_APPLICATION_LOG_GLOB))
    except OSError:
        return

    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_mtime <= cutoff:
                candidate.unlink()
        except OSError:
            # Retention must not prevent the application from starting or logging.
            continue


def _resolve_log_serialization(serialize: bool | None) -> bool:
    """Resolve and persist the sink mode so spawned workers inherit it."""
    if serialize is None:
        return os.environ.get(AROW_LOG_SERIALIZE_ENV, "0") == "1"
    os.environ[AROW_LOG_SERIALIZE_ENV] = "1" if serialize else "0"
    return serialize


def resolve_worker_application_log_file_path(
    *,
    process_id: int | str | None = None,
) -> Path:
    """Return the PID-specific worker path, or a template when given ``"{pid}"``."""
    shared_path = resolve_application_log_file_path()
    resolved_process_id = os.getpid() if process_id is None else process_id
    return shared_path.with_name(
        f"{shared_path.stem}.worker-{resolved_process_id}{shared_path.suffix}"
    )


def _configure_logger(
    log_path: Path,
    *,
    serialize_logs: bool,
    publish_log_path: bool,
) -> Path:
    """Configure one process-local sink and return its concrete path."""
    candidate_paths = (log_path, _fallback_application_log_file_path(log_path))

    logger.remove()

    last_error: OSError | None = None
    for candidate_path in candidate_paths:
        try:
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            _prune_expired_application_logs(candidate_path.parent)
            logger.add(
                str(candidate_path),
                format=_json_loguru_format if serialize_logs else _loguru_format,
                serialize=serialize_logs,
                colorize=False,
                encoding="utf-8",
                rotation=_APPLICATION_LOG_ROTATION,
                retention=_APPLICATION_LOG_RETENTION,
                compression=_APPLICATION_LOG_COMPRESSION,
                watch=True,
            )
            if publish_log_path:
                os.environ[AROW_LOG_FILE_ENV] = str(candidate_path)
            return candidate_path
        except OSError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return log_path


def setup_logger(*, serialize: bool | None = None) -> Path:
    """
    Configure Loguru sinks and the project format string.

    Call this before importing modules that emit logs at import time. For example,
    ``core.entrypoint`` imports ``CORE_RUNTIME_WORKS``, which constructs
    :class:`~collection.Repository` subclasses that log snapshot lines from ``add`` / ``add_all``.
    If this runs too late, those lines go through Loguru's default handler instead of the file sink.

    Returns:
        Path: The concrete application log file used by this process tree.
    """
    serialize_logs = _resolve_log_serialization(serialize)
    log_path = resolve_application_log_file_path()
    return _configure_logger(
        log_path,
        serialize_logs=serialize_logs,
        publish_log_path=True,
    )


def setup_worker_logger() -> Path:
    """
    Configure a process-pool worker with an isolated rotating file sink.

    Workers inherit the main path and serialization mode through the environment,
    but never open the main process file. This avoids unsupported concurrent
    rotation, compression, and writes across independently configured Loguru sinks.
    """
    worker_path = resolve_worker_application_log_file_path()
    return _configure_logger(
        worker_path,
        serialize_logs=_resolve_log_serialization(None),
        publish_log_path=False,
    )
