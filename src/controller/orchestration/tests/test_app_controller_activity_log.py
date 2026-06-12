"""Tests for AppController app-wide activity log file handling."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

from controller.orchestration.app_controller import AppController
from core.entrypoint import ModelEntrypoint


class _AppControllerActivityLogProbe:
    def __init__(self, application_dir: Path) -> None:
        self._activity_log_file: Path | None = None
        self.model_entrypoint = MagicMock(spec=ModelEntrypoint)
        self.model_entrypoint.application_dir = application_dir
        self.view = MagicMock()

    def _resolve_activity_log_file(self) -> Path:
        return AppController._resolve_activity_log_file(cast(AppController, self))


def test_resolve_activity_log_file_uses_timestamped_default(tmp_path: Path) -> None:
    probe = _AppControllerActivityLogProbe(tmp_path)

    resolved = probe._resolve_activity_log_file()

    assert resolved.parent == tmp_path / "logs"
    assert resolved.name.startswith("activity_")
    assert resolved.suffix == ".log"
    assert probe._activity_log_file == resolved


def test_on_activity_log_file_update_requested_stores_path_and_forwards_to_view(
    monkeypatch,
) -> None:
    import builtins

    probe = _AppControllerActivityLogProbe(Path("/tmp/arow"))
    custom_path = "/tmp/custom/activity_20260531.log"
    real_isinstance = builtins.isinstance

    def _isinstance(obj, cls) -> bool:
        if getattr(cls, "__name__", "") == "MainWindow" and obj is probe.view:
            return True
        return real_isinstance(obj, cls)

    monkeypatch.setattr(builtins, "isinstance", _isinstance)

    AppController._on_activity_log_file_update_requested(probe, custom_path)

    assert probe._activity_log_file == Path(custom_path)
    probe.view.forward_activity_log_file_updated.assert_called_once_with(custom_path)
