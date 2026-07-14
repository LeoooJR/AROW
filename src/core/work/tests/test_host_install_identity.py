"""Tests for persisted host install UUID worker outcome (filesystem; paths monkeypatched)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

import core.work.host_install_identity_work as host_install_identity_work
from core.devices.computer import compute_computer_stable_key
from core.entrypoint import ModelEntrypoint
from core.signals import CoreSignals, HostComputerIdentityPayload
from core.work.host_install_identity_work import (
    HostInstallIdentityOutcome,
    HostInstallIdentityWork,
)

pytestmark = [pytest.mark.devices]


def test_host_install_identity_work_idempotent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        host_install_identity_work, "get_or_create_application_dir", lambda: tmp_path
    )
    outcome = HostInstallIdentityWork().run()
    assert Path(tmp_path / "install_identity").is_file()
    uuid.UUID(outcome.install_token)
    second = HostInstallIdentityWork().run()
    assert outcome.install_token == second.install_token


def test_apply_main_thread_sets_host_identity_and_emits_signal() -> None:
    model_entrypoint = ModelEntrypoint()
    token = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    captured: list[HostComputerIdentityPayload] = []

    def capture(payload: HostComputerIdentityPayload) -> None:
        captured.append(payload)

    model_entrypoint.signal_bus.subscribe(
        CoreSignals.HOST_COMPUTER_IDENTITY_UPDATED,
        capture,
    )
    HostInstallIdentityWork.apply_main_thread(
        model_entrypoint,
        HostInstallIdentityOutcome(install_token=token),
    )

    expected_key = compute_computer_stable_key(token)
    assert model_entrypoint.host.descriptor.stable_key == expected_key
    assert captured == [HostComputerIdentityPayload(stable_key=expected_key)]
