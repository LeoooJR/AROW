"""Tests for persisted host install UUID worker outcome (filesystem; paths monkeypatched)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

import core.host_install_identity_work as host_install_identity_work
from core.host_install_identity_work import HostInstallIdentityWork

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
