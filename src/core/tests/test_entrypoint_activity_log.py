"""Tests for ModelEntrypoint app-wide activity log file ownership and signals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from application_paths import ApplicationPaths
from core.entrypoint import ModelEntrypoint
from core.signal_bus import InMemoryCoreSignalBus
from core.signals import (
    ActivityLogFileUpdatedPayload,
    CoreSignal,
    CoreSignals,
)


@pytest.fixture
def application_paths(tmp_path: Path) -> ApplicationPaths:
    """Provide isolated application paths."""
    return ApplicationPaths(
        application_dir=tmp_path,
        config_dir=tmp_path / "config",
        source_dir=tmp_path / "src",
        platform="linux",
    )


def test_model_entrypoint_resolves_timestamped_default_activity_log_file(
    application_paths: ApplicationPaths,
) -> None:
    model_entrypoint = ModelEntrypoint(paths=application_paths)

    resolved = model_entrypoint.activity_log_file

    assert model_entrypoint.paths is application_paths
    assert resolved is not None
    assert resolved.parent == application_paths.logs_dir
    assert resolved.name.startswith("activity_")
    assert resolved.suffix == ".log"


def test_model_entrypoint_init_emits_activity_log_file_updated(
    application_paths: ApplicationPaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[tuple[CoreSignal[Any], object]] = []
    original_emit = InMemoryCoreSignalBus.emit

    def capture_emit(
        self: InMemoryCoreSignalBus,
        signal: CoreSignal[Any],
        payload: object,
    ) -> None:
        emitted.append((signal, payload))
        original_emit(self, signal, payload)

    monkeypatch.setattr(InMemoryCoreSignalBus, "emit", capture_emit)

    model_entrypoint = ModelEntrypoint(paths=application_paths)

    assert len(emitted) == 1
    signal, payload = emitted[0]
    assert signal == CoreSignals.ACTIVITY_LOG_FILE_UPDATED
    assert isinstance(payload, ActivityLogFileUpdatedPayload)
    assert payload.path == model_entrypoint.activity_log_file


def test_model_entrypoint_activity_log_file_setter_stores_path_and_emits(
    application_paths: ApplicationPaths,
) -> None:
    model_entrypoint = ModelEntrypoint(paths=application_paths)
    received: list[ActivityLogFileUpdatedPayload] = []

    def capture(payload: ActivityLogFileUpdatedPayload) -> None:
        received.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.ACTIVITY_LOG_FILE_UPDATED, capture
    )

    custom_path = Path("/tmp/custom/activity_20260531.log")
    model_entrypoint.activity_log_file = custom_path

    assert model_entrypoint.activity_log_file == custom_path
    assert len(received) == 1
    assert received[0].path == custom_path
