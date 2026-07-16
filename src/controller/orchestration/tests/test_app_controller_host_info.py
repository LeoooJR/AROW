"""Tests for AppController host device information forwarding."""

from __future__ import annotations

import builtins
from typing import Any, cast
from unittest.mock import MagicMock

from controller.orchestration.app_controller import AppController
from core.entrypoint import ModelEntrypoint


class _AppControllerHostInfoProbe:
    def __init__(self) -> None:
        self.model_entrypoint = MagicMock(spec=ModelEntrypoint)
        self.model_entrypoint.host.name = "MacBook Pro"
        self.model_entrypoint.host.os = "macOS"
        self.model_entrypoint.host.ip = "192.168.1.42"
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
    probe.model_entrypoint = cast(Any, object())
    real_isinstance = builtins.isinstance

    def _isinstance(obj, cls) -> bool:
        if getattr(cls, "__name__", "") == "MainWindow" and obj is probe.view:
            return True
        return real_isinstance(obj, cls)

    monkeypatch.setattr(builtins, "isinstance", _isinstance)

    AppController._send_host_device_information(cast(AppController, probe))

    probe.view.forward_host_device_information_updated.assert_not_called()
