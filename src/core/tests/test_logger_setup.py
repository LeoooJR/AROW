"""Tests for shared low-level application log file setup."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.application_paths import default_application_log_file_path
from logger import (
    AROW_LOG_FILE_ENV,
    AROW_LOG_SERIALIZE_ENV,
    _json_loguru_format,
    resolve_application_log_file_path,
    setup_logger,
    setup_worker_logger,
)


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


def test_setup_logger_configures_bounded_file_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shared = tmp_path / "logs" / "application_20260101_120000.log"
    sink_options: dict[str, object] = {}

    def fake_add(_sink: str, **kwargs: object) -> int:
        sink_options.update(kwargs)
        return 1

    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(shared))
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    setup_logger()

    assert sink_options["rotation"] == "10 MB"
    assert sink_options["retention"] == timedelta(days=14)
    assert sink_options["compression"] == "gz"
    assert sink_options["watch"] is True


def test_setup_logger_configures_json_serialization_for_process_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shared = tmp_path / "logs" / "application_20260101_120000.log"
    sink_options: list[dict[str, object]] = []

    def fake_add(_sink: str, **kwargs: object) -> int:
        sink_options.append(kwargs)
        return 1

    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(shared))
    monkeypatch.delenv(AROW_LOG_SERIALIZE_ENV, raising=False)
    monkeypatch.setattr("logger.os.getpid", lambda: 4242)
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    setup_logger(serialize=True)
    setup_worker_logger()

    assert os.environ[AROW_LOG_SERIALIZE_ENV] == "1"
    assert sink_options[0]["serialize"] is True
    assert sink_options[1]["serialize"] is True
    assert sink_options[0]["format"] is _json_loguru_format
    assert sink_options[1]["format"] is _json_loguru_format


def test_setup_worker_logger_uses_process_isolated_sink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shared = tmp_path / "logs" / "application_20260101_120000.log"
    sink_paths: list[Path] = []

    def fake_add(sink: str, **_kwargs: object) -> int:
        sink_paths.append(Path(sink))
        return 1

    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(shared))
    monkeypatch.setenv(AROW_LOG_SERIALIZE_ENV, "1")
    monkeypatch.setattr("logger.os.getpid", lambda: 4242)
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    worker_path = setup_worker_logger()

    expected = shared.with_name("application_20260101_120000.worker-4242.log")
    assert worker_path == expected
    assert sink_paths == [expected]
    assert os.environ[AROW_LOG_FILE_ENV] == str(shared)


def test_setup_logger_prunes_expired_logs_from_previous_runs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    shared = log_dir / "application_20260727_120000.log"
    expired = log_dir / "application_20260701_120000.log"
    expired_compressed = log_dir / "application_20260701_120000.log.gz"
    recent = log_dir / "application_20260726_120000.log"
    unrelated = log_dir / "activity_20260701.log"

    for path in (expired, expired_compressed, recent, unrelated):
        path.touch()

    now = 1_800_000_000.0
    expired_timestamp = now - timedelta(days=15).total_seconds()
    recent_timestamp = now - timedelta(days=1).total_seconds()
    os.utime(expired, (expired_timestamp, expired_timestamp))
    os.utime(expired_compressed, (expired_timestamp, expired_timestamp))
    os.utime(recent, (recent_timestamp, recent_timestamp))
    os.utime(unrelated, (expired_timestamp, expired_timestamp))

    monkeypatch.setattr("logger.time.time", lambda: now)
    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(shared))
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", lambda *_args, **_kwargs: 1)

    setup_logger()

    assert not expired.exists()
    assert not expired_compressed.exists()
    assert recent.exists()
    assert unrelated.exists()


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


def test_setup_logger_uses_default_temp_fallback_dir_when_override_is_unset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    primary = tmp_path / "primary" / "application_20260621_123045.log"
    temp_root = tmp_path / "tmp-root"
    calls: list[Path] = []

    def fake_add(sink: str, **_kwargs: object) -> int:
        path = Path(sink)
        calls.append(path)
        if path == primary:
            raise PermissionError("primary path is not writable")
        return 1

    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(primary))
    monkeypatch.delenv("AROW_LOG_FALLBACK_DIR", raising=False)
    monkeypatch.setattr("logger.tempfile.gettempdir", lambda: str(temp_root))
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    log_path = setup_logger()

    expected_fallback = temp_root / "arow-logs" / primary.name
    assert calls == [primary, expected_fallback]
    assert log_path == expected_fallback
    assert os.environ[AROW_LOG_FILE_ENV] == str(expected_fallback)


def test_setup_logger_raises_last_error_when_primary_and_fallback_both_fail(
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
        raise PermissionError("fallback path is not writable")

    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(primary))
    monkeypatch.setenv("AROW_LOG_FALLBACK_DIR", str(fallback_dir))
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    with pytest.raises(PermissionError, match="fallback path is not writable"):
        setup_logger()

    assert calls == [primary, fallback_dir / primary.name]
