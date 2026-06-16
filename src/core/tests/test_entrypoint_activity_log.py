"""Tests for ModelEntrypoint app-wide activity log file ownership and signals."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.entrypoint import ModelEntrypoint
from core.signals import (
    ActivityLogFileUpdatedPayload,
    CoreSignal,
    InMemoryCoreSignalBus,
)


@pytest.fixture
def application_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ModelEntrypoint application data at an isolated temporary directory."""
    monkeypatch.setattr(
        "core.entrypoint.get_or_create_application_dir",
        lambda: tmp_path,
    )
    return tmp_path


def test_model_entrypoint_resolves_timestamped_default_activity_log_file(
    application_dir: Path,
) -> None:
    model_entrypoint = ModelEntrypoint()

    resolved = model_entrypoint.activity_log_file

    assert resolved is not None
    assert resolved.parent == application_dir / "logs"
    assert resolved.name.startswith("activity_")
    assert resolved.suffix == ".log"


def test_model_entrypoint_init_emits_activity_log_file_updated(
    application_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[tuple[CoreSignal, object]] = []
    original_emit = InMemoryCoreSignalBus.emit

    def capture_emit(
        self: InMemoryCoreSignalBus,
        signal: CoreSignal,
        payload: object,
    ) -> None:
        emitted.append((signal, payload))
        original_emit(self, signal, payload)

    monkeypatch.setattr(InMemoryCoreSignalBus, "emit", capture_emit)

    model_entrypoint = ModelEntrypoint()

    assert len(emitted) == 1
    signal, payload = emitted[0]
    assert signal == CoreSignal.ACTIVITY_LOG_FILE_UPDATED
    assert isinstance(payload, ActivityLogFileUpdatedPayload)
    assert payload.path == model_entrypoint.activity_log_file


def test_model_entrypoint_activity_log_file_setter_stores_path_and_emits(
    application_dir: Path,
) -> None:
    model_entrypoint = ModelEntrypoint()
    received: list[ActivityLogFileUpdatedPayload] = []

    def capture(payload: ActivityLogFileUpdatedPayload) -> None:
        received.append(payload)

    model_entrypoint.subscribe(CoreSignal.ACTIVITY_LOG_FILE_UPDATED, capture)

    custom_path = Path("/tmp/custom/activity_20260531.log")
    model_entrypoint.activity_log_file = custom_path

    assert model_entrypoint.activity_log_file == custom_path
    assert len(received) == 1
    assert received[0].path == custom_path
