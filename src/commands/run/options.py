"""Shared options for application run interfaces."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RunOptions:
    """Options shared by the TUI and GUI launch paths."""

    mock_adb: bool = False
