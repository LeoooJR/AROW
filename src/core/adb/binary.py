from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core import ADB_BINARY_BUILD_NUMBER, ADB_BINARY_BUILD_VERSION, ADB_BINARY_VERSION

# Default path to the bundled Linux ADB binary under src/assets (overridden at startup).
_DEFAULT_ADB_BINARY_PATH: Path = (
    Path(__file__).resolve().parents[2] / "assets" / "linux" / "platform-tools" / "adb"
)


@dataclass(frozen=True, match_args=True)
class AdbBinary:
    """ADB binary metadata and path."""

    path: Path = field(
        metadata={"description": "The path to the adb binary"},
        default=_DEFAULT_ADB_BINARY_PATH,
        compare=False,
    )
    version: str = field(
        metadata={"description": "The version of the adb binary"},
        default=ADB_BINARY_VERSION,
    )
    build_date: Optional[datetime.datetime] = field(
        metadata={"description": "The build date of the adb binary"},
        default=None,
        compare=False,
    )
    build_number: Optional[int] = field(
        metadata={"description": "The build number of the adb binary"},
        default=ADB_BINARY_BUILD_NUMBER,
    )
    build_version: Optional[str] = field(
        metadata={"description": "The build version of the adb binary"},
        default=ADB_BINARY_BUILD_VERSION,
    )

    def __str__(self) -> str:
        return (
            f"{self.path} - {self.version} - {self.build_date} - "
            f"{self.build_number} - {self.build_version}"
        )

    def __repr__(self) -> str:
        return (
            f"AdbBinary(path={self.path}, version={self.version}, "
            f"build_date={self.build_date}, build_number={self.build_number}, "
            f"build_version={self.build_version})"
        )
