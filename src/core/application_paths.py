"""
User-writable paths for configuration and application-local data (`~/.arow`, `%APPDATA%`, etc.).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from faker import Faker

_application_log_faker = Faker("en_US", use_weighting=False)


def get_or_create_application_dir() -> Path:
    """
    User-writable application data directory, created if missing.

    - Windows: %LOCALAPPDATA%\\arow (fallback: ~/AppData/Local/arow)
    - Linux, macOS, and other Unix-like: ~/.arow
    """
    if sys.platform == "win32":
        local = (os.environ.get("LOCALAPPDATA") or "").strip()
        path = (
            Path(local) / "arow"
            if local
            else Path.home() / "AppData" / "Local" / "arow"
        )
    else:
        path = Path.home() / ".arow"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolved_config_base() -> Path:
    """Directory that contains per-app config folders (e.g. .../arow), before the app name segment."""
    if sys.platform == "win32":
        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            base = Path(appdata)
        else:
            base = Path.home() / "AppData" / "Roaming"
    else:
        xdg = (os.environ.get("XDG_CONFIG_HOME") or "").strip()
        if xdg:
            base = Path(xdg).expanduser()
        else:
            base = Path.home() / ".config"
    if not base.is_absolute():
        base = Path.home() / base
    return base.resolve(strict=False)


def get_or_create_config_dir() -> Path:
    """
    User configuration directory, created if missing.

    - Windows: %APPDATA%\\arow (fallback: ~/AppData/Roaming/arow)
    - Linux, macOS, and other Unix-like: $XDG_CONFIG_HOME/arow or ~/.config/arow
    """
    config = _resolved_config_base() / "arow"
    config.mkdir(parents=True, exist_ok=True)
    return config


def get_or_create_activity_logs_dir(application_dir: Path) -> Path:
    """Return the app-wide activity logs directory under ``application_dir``, creating it if needed."""
    logs_dir = application_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def default_activity_log_file_path(
    application_dir: Path,
    *,
    now: datetime | None = None,
) -> Path:
    """
    Return the default timestamped app-wide activity log file path.

    One file per calendar day under ``<application_dir>/logs/activity_YYYYMMDD.log``.
    """
    day_stamp = (now or datetime.now()).strftime("%Y%m%d")
    return (
        get_or_create_activity_logs_dir(application_dir) / f"activity_{day_stamp}.log"
    )


def default_application_log_file_path(
    application_dir: Path,
) -> Path:
    """
    Return a UUID4-named low-level application log file path for one process run.

    Distinct from :func:`default_activity_log_file_path` (user-facing GUI activity).
    One file per application start under
    ``<application_dir>/logs/<run_identifier>.log``.
    """
    run_identifier = _application_log_faker.uuid4()
    return get_or_create_activity_logs_dir(application_dir) / f"{run_identifier}.log"
