"""Tests for AppController activity log file view wiring."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

from controller.orchestration.app_controller import AppController
from core.entrypoint import ModelEntrypoint
from core.signals import ActivityLogFileUpdatedPayload


class _AppControllerActivityLogProbe:
    def __init__(self) -> None:
        self.model_entrypoint = MagicMock(spec=ModelEntrypoint)
        self.view = MagicMock()


def _patch_controller_type_checks(monkeypatch, probe: object) -> None:
    real_isinstance = builtins.isinstance

    def _isinstance(obj, cls) -> bool:
        cls_name = getattr(cls, "__name__", "")
        if cls_name == "MainWindow" and obj is getattr(probe, "view", object()):
            return True
        if cls_name == "ModelEntrypoint" and obj is getattr(
            probe, "model_entrypoint", object()
        ):
            return True
        return real_isinstance(obj, cls)

    monkeypatch.setattr(builtins, "isinstance", _isinstance)


def test_on_activity_log_file_update_requested_delegates_to_model_entrypoint(
    monkeypatch,
) -> None:
    probe = _AppControllerActivityLogProbe()
    custom_path = "/tmp/custom/activity_20260531.log"
    _patch_controller_type_checks(monkeypatch, probe)

    AppController._on_activity_log_file_update_requested(probe, custom_path)

    assert probe.model_entrypoint.activity_log_file == Path(custom_path)


def test_on_activity_log_file_updated_forwards_path_to_view(monkeypatch) -> None:
    probe = _AppControllerActivityLogProbe()
    custom_path = Path("/tmp/custom/activity_20260531.log")
    _patch_controller_type_checks(monkeypatch, probe)

    AppController._on_activity_log_file_updated(
        cast(AppController, probe),
        ActivityLogFileUpdatedPayload(path=custom_path),
    )

    probe.view.forward_activity_log_file_updated.assert_called_once_with(
        str(custom_path)
    )
