"""
User-writable paths for configuration and application-local data (`~/.arow`, `%APPDATA%`, etc.).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


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
