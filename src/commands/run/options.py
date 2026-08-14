"""Shared options for application run interfaces."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunOptions:
    """Options shared by the TUI and GUI launch paths."""

    mock_adb: bool = False
    serialize_logs: bool = False
    log_dir: Path | None = None
