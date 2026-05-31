"""Tests for user-writable application path helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.application_paths import (
    default_activity_log_file_path,
    get_or_create_activity_logs_dir,
)


def test_default_activity_log_file_path_uses_timestamped_name(tmp_path: Path) -> None:
    fixed_now = datetime(2026, 5, 31, 14, 30, 0)
    path = default_activity_log_file_path(tmp_path, now=fixed_now)

    assert path == tmp_path / "logs" / "activity_20260531.log"
    assert path.parent.is_dir()


def test_get_or_create_activity_logs_dir_is_idempotent(tmp_path: Path) -> None:
    first = get_or_create_activity_logs_dir(tmp_path)
    second = get_or_create_activity_logs_dir(tmp_path)

    assert first == tmp_path / "logs"
    assert second == first
    assert first.is_dir()
