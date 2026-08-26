"""Tests for AppController host device information forwarding."""

from __future__ import annotations

from typing import cast
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


def test_send_host_device_information_forwards_host_metadata() -> None:
    probe = _AppControllerHostInfoProbe()

    AppController._send_host_device_information(cast(AppController, probe))

    probe.view.forward_host_device_information_updated.assert_called_once_with(
        "MacBook Pro",
        "macOS",
        "192.168.1.42",
    )
