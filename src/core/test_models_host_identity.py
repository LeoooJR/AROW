"""Tests for CoreRuntimeModel host install identity via apply_result + core bus emission."""

from __future__ import annotations

import pytest

from core.devices import compute_computer_stable_key
from core.host_install_identity_work import HostInstallIdentityOutcome
from core.models import CoreRuntimeModel
from core.signals import CoreSignal, HostComputerIdentityPayload

pytestmark = [pytest.mark.devices]


def test_apply_host_install_identity_outcome_sets_stable_key() -> None:
    model = CoreRuntimeModel()
    token = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    model.apply_result(HostInstallIdentityOutcome(install_token=token))
    expected = compute_computer_stable_key(token)
    assert model.host.stable_key == expected
    assert model.host.descriptor.stable_key == expected


def test_apply_host_install_identity_outcome_skips_blank_token() -> None:
    model = CoreRuntimeModel()
    model.apply_result(HostInstallIdentityOutcome(install_token="   "))
    assert model.host.descriptor.stable_key == ""


def test_apply_host_install_identity_outcome_emits_core_signal() -> None:
    model = CoreRuntimeModel()
    received: list[HostComputerIdentityPayload] = []

    def capture(payload: object) -> None:
        assert isinstance(payload, HostComputerIdentityPayload)
        received.append(payload)

    model.subscribe(CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED, capture)
    token = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    model.apply_result(HostInstallIdentityOutcome(install_token=token))

    expected = compute_computer_stable_key(token)
    assert len(received) == 1
    assert received[0].stable_key == expected
