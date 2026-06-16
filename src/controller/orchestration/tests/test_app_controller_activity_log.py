"""Tests for AppController app-wide activity log file handling."""

from __future__ import annotations

import builtins
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


class _AppControllerHostInfoProbe:
    def __init__(self) -> None:
        self.model_entrypoint = MagicMock(spec=ModelEntrypoint)
        self.model_entrypoint.host.get_name.return_value = "MacBook Pro"
        self.model_entrypoint.host.get_os.return_value = "macOS"
        self.model_entrypoint.host.get_ip.return_value = "192.168.1.42"
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
    probe = _AppControllerActivityLogProbe(Path("/tmp/arow"))
    custom_path = "/tmp/custom/activity_20260531.log"
    _patch_controller_type_checks(monkeypatch, probe)

    AppController._on_activity_log_file_update_requested(probe, custom_path)

    assert probe._activity_log_file == Path(custom_path)
    probe.view.forward_activity_log_file_updated.assert_called_once_with(custom_path)


def test_send_host_device_information_forwards_host_metadata(monkeypatch) -> None:
    probe = _AppControllerHostInfoProbe()
    _patch_controller_type_checks(monkeypatch, probe)

    AppController._send_host_device_information(cast(AppController, probe))

    probe.view.forward_host_device_information_updated.assert_called_once_with(
        "MacBook Pro",
        "macOS",
        "192.168.1.42",
    )


def test_send_host_device_information_returns_when_model_entrypoint_is_invalid(
    monkeypatch,
) -> None:
    probe = _AppControllerHostInfoProbe()
    probe.model_entrypoint = object()
    real_isinstance = builtins.isinstance

    def _isinstance(obj, cls) -> bool:
        if getattr(cls, "__name__", "") == "MainWindow" and obj is probe.view:
            return True
        return real_isinstance(obj, cls)

    monkeypatch.setattr(builtins, "isinstance", _isinstance)

    AppController._send_host_device_information(cast(AppController, probe))

    probe.view.forward_host_device_information_updated.assert_not_called()
