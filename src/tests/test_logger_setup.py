"""Tests for source-root low-level application log file setup."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pytest

from logger import (
    AROW_LOG_FILE_ENV,
    AROW_LOG_SERIALIZE_ENV,
    _json_loguru_format,
    resolve_application_log_file_path,
    setup_logger,
    setup_worker_logger,
)

RUN_IDENTIFIER = "01fdb29d-2e6b-49d1-8956-9d1caa576d2c"
SECOND_RUN_IDENTIFIER = "82f51368-a37b-466b-8047-21d86640d93e"


def test_setup_logger_publishes_fresh_application_log_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generated_path = tmp_path / "logs" / f"{RUN_IDENTIFIER}.log"
    inherited_path = tmp_path / "logs" / "inherited.log"
    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(inherited_path))

    log_path = setup_logger(generated_path)

    assert log_path == generated_path
    assert os.environ[AROW_LOG_FILE_ENV] == str(log_path)


def test_successive_root_logger_setups_publish_distinct_run_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_generated = tmp_path / "logs" / f"{RUN_IDENTIFIER}.log"
    second_generated = tmp_path / "logs" / f"{SECOND_RUN_IDENTIFIER}.log"

    first_path = setup_logger(first_generated)
    second_path = setup_logger(second_generated)

    assert first_path != second_path
    assert os.environ[AROW_LOG_FILE_ENV] == str(second_path)


def test_setup_logger_configures_bounded_file_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sink_options: dict[str, object] = {}

    def fake_add(_sink: str, **kwargs: object) -> int:
        sink_options.update(kwargs)
        return 1

    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    setup_logger(tmp_path / "logs" / f"{RUN_IDENTIFIER}.log")

    assert sink_options["rotation"] == "10 MB"
    assert sink_options["retention"] == timedelta(days=14)
    assert sink_options["compression"] == "gz"
    assert sink_options["watch"] is True


def test_setup_logger_configures_json_serialization_for_process_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sink_options: list[dict[str, object]] = []

    def fake_add(_sink: str, **kwargs: object) -> int:
        sink_options.append(kwargs)
        return 1

    monkeypatch.delenv(AROW_LOG_SERIALIZE_ENV, raising=False)
    monkeypatch.setattr("logger.os.getpid", lambda: 4242)
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    setup_logger(
        tmp_path / "logs" / f"{RUN_IDENTIFIER}.log",
        serialize=True,
    )
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
    shared = tmp_path / "logs" / f"{RUN_IDENTIFIER}.log"
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

    expected = shared.with_name(f"{RUN_IDENTIFIER}.worker-4242.log")
    assert worker_path == expected
    assert sink_paths == [expected]
    assert os.environ[AROW_LOG_FILE_ENV] == str(shared)


def test_setup_logger_prunes_expired_logs_from_previous_runs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    expired = log_dir / f"{SECOND_RUN_IDENTIFIER}.log"
    expired_worker = log_dir / f"{SECOND_RUN_IDENTIFIER}.worker-4242.log"
    expired_rotated_compressed = (
        log_dir / f"{SECOND_RUN_IDENTIFIER}.2026-07-01_12-00-00_000000.log.gz"
    )
    recent = log_dir / f"{RUN_IDENTIFIER}.worker-4343.log"
    activity_log = log_dir / "activity_20260701.log"
    legacy_log = log_dir / "application_20260701_120000.log"
    unrelated = log_dir / "notes.log"

    for path in (
        expired,
        expired_worker,
        expired_rotated_compressed,
        recent,
        activity_log,
        legacy_log,
        unrelated,
    ):
        path.touch()

    now = 1_800_000_000.0
    expired_timestamp = now - timedelta(days=15).total_seconds()
    recent_timestamp = now - timedelta(days=1).total_seconds()
    os.utime(expired, (expired_timestamp, expired_timestamp))
    os.utime(expired_worker, (expired_timestamp, expired_timestamp))
    os.utime(
        expired_rotated_compressed,
        (expired_timestamp, expired_timestamp),
    )
    os.utime(recent, (recent_timestamp, recent_timestamp))
    os.utime(activity_log, (expired_timestamp, expired_timestamp))
    os.utime(legacy_log, (expired_timestamp, expired_timestamp))
    os.utime(unrelated, (expired_timestamp, expired_timestamp))

    monkeypatch.setattr("logger.time.time", lambda: now)
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", lambda *_args, **_kwargs: 1)

    setup_logger(log_dir / f"{RUN_IDENTIFIER}.log")

    assert not expired.exists()
    assert not expired_worker.exists()
    assert not expired_rotated_compressed.exists()
    assert recent.exists()
    assert activity_log.exists()
    assert legacy_log.exists()
    assert unrelated.exists()


def test_resolve_application_log_file_path_reuses_env_without_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shared = tmp_path / "logs" / f"{RUN_IDENTIFIER}.log"
    monkeypatch.setenv(AROW_LOG_FILE_ENV, str(shared))

    assert resolve_application_log_file_path() == shared


def test_resolve_application_log_file_path_requires_root_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(AROW_LOG_FILE_ENV, raising=False)

    with pytest.raises(RuntimeError, match="configure root logging"):
        resolve_application_log_file_path()


def test_setup_logger_falls_back_when_primary_log_path_is_unwritable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    primary = tmp_path / "primary" / "logs" / f"{RUN_IDENTIFIER}.log"
    fallback_dir = tmp_path / "fallback"
    calls: list[Path] = []

    def fake_add(sink: str, **_kwargs: object) -> int:
        path = Path(sink)
        calls.append(path)
        if path == primary:
            raise PermissionError("primary path is not writable")
        return 1

    monkeypatch.setenv("AROW_LOG_FALLBACK_DIR", str(fallback_dir))
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    log_path = setup_logger(primary)

    expected_fallback = fallback_dir / primary.name
    assert calls == [primary, expected_fallback]
    assert log_path == expected_fallback
    assert os.environ[AROW_LOG_FILE_ENV] == str(expected_fallback)


def test_setup_logger_can_disable_fallback_for_explicit_log_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    primary = tmp_path / "primary" / "logs" / f"{RUN_IDENTIFIER}.log"
    fallback_dir = tmp_path / "fallback"
    calls: list[Path] = []

    def fake_add(sink: str, **_kwargs: object) -> int:
        calls.append(Path(sink))
        raise PermissionError("explicit path is not writable")

    monkeypatch.setenv("AROW_LOG_FALLBACK_DIR", str(fallback_dir))
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    with pytest.raises(PermissionError, match="explicit path is not writable"):
        setup_logger(primary, allow_fallback=False)

    assert calls == [primary]
    assert os.environ.get(AROW_LOG_FILE_ENV) != str(primary)


def test_setup_logger_uses_default_temp_fallback_dir_when_override_is_unset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    primary = tmp_path / "primary" / "logs" / f"{RUN_IDENTIFIER}.log"
    temp_root = tmp_path / "tmp-root"
    calls: list[Path] = []

    def fake_add(sink: str, **_kwargs: object) -> int:
        path = Path(sink)
        calls.append(path)
        if path == primary:
            raise PermissionError("primary path is not writable")
        return 1

    monkeypatch.delenv("AROW_LOG_FALLBACK_DIR", raising=False)
    monkeypatch.setattr("logger.tempfile.gettempdir", lambda: str(temp_root))
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    log_path = setup_logger(primary)

    expected_fallback = temp_root / "arow-logs" / primary.name
    assert calls == [primary, expected_fallback]
    assert log_path == expected_fallback
    assert os.environ[AROW_LOG_FILE_ENV] == str(expected_fallback)


def test_setup_logger_raises_last_error_when_primary_and_fallback_both_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    primary = tmp_path / "primary" / "logs" / f"{RUN_IDENTIFIER}.log"
    fallback_dir = tmp_path / "fallback"
    calls: list[Path] = []

    def fake_add(sink: str, **_kwargs: object) -> int:
        path = Path(sink)
        calls.append(path)
        if path == primary:
            raise PermissionError("primary path is not writable")
        raise PermissionError("fallback path is not writable")

    monkeypatch.setenv("AROW_LOG_FALLBACK_DIR", str(fallback_dir))
    monkeypatch.setattr("logger.logger.remove", lambda: None)
    monkeypatch.setattr("logger.logger.add", fake_add)

    with pytest.raises(PermissionError, match="fallback path is not writable"):
        setup_logger(primary)

    assert calls == [primary, fallback_dir / primary.name]
