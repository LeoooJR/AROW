"""Tests for shared low-level application log file setup."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from core.application_paths import default_application_log_file_path
from logger import AROW_LOG_FILE_ENV, resolve_application_log_file_path, setup_logger


def test_default_application_log_file_path_uses_run_timestamp(tmp_path: Path) -> None:
    fixed_now = datetime(2026, 6, 21, 12, 30, 45)
    path = default_application_log_file_path(tmp_path, now=fixed_now)

    assert path == tmp_path / "logs" / "application_20260621_123045.log"
    assert path.parent.is_dir()


def test_setup_logger_sets_concrete_application_log_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(AROW_LOG_FILE_ENV, raising=False)
    monkeypatch.setattr("logger.get_or_create_application_dir", lambda: tmp_path)

    log_path = setup_logger()

    assert "{time}" not in str(log_path)
    assert log_path.parent == tmp_path / "logs"
    assert log_path.name.startswith("application_")
    assert log_path.suffix == ".log"
    assert os.environ[AROW_LOG_FILE_ENV] == str(log_path)


def test_setup_logger_reuses_env_log_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shared = tmp_path / "logs" / "application_20260101_120000.log"
    shared.parent.mkdir(parents=True)
    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(shared))

    log_path = setup_logger()

    assert log_path == shared


def test_resolve_application_log_file_path_reuses_env_without_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shared = tmp_path / "logs" / "application_shared.log"
    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(shared))

    assert resolve_application_log_file_path() == shared


def test_setup_logger_falls_back_when_primary_log_path_is_unwritable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    primary = tmp_path / "primary" / "application_20260621_123045.log"
    fallback_dir = tmp_path / "fallback"
    calls: list[Path] = []

    def fake_add(sink: str, **_kwargs: object) -> int:
        path = Path(sink)
        calls.append(path)
        if path == primary:
            raise PermissionError("primary path is not writable")
        return 1

    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(primary))
    monkeypatch.setenv("AROW_LOG_FALLBACK_DIR", str(fallback_dir))
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    log_path = setup_logger()

    expected_fallback = fallback_dir / primary.name
    assert calls == [primary, expected_fallback]
    assert log_path == expected_fallback
    assert os.environ[AROW_LOG_FILE_ENV] == str(expected_fallback)
