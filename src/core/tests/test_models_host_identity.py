"""Tests for ModelEntrypoint host install identity via apply_result + core bus emission."""

from __future__ import annotations

import pytest

from core.devices import compute_computer_stable_key
from core.entrypoint import ModelEntrypoint
from core.signals import CoreSignal, HostComputerIdentityPayload
from core.work.host_install_identity_work import HostInstallIdentityOutcome

pytestmark = [pytest.mark.devices]


def test_apply_host_install_identity_outcome_sets_stable_key() -> None:
    model_entrypoint = ModelEntrypoint()
    token = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    model_entrypoint.apply_result(HostInstallIdentityOutcome(install_token=token))
    expected = compute_computer_stable_key(token)
    assert model_entrypoint.host.stable_key == expected
    assert model_entrypoint.host.descriptor.stable_key == expected


def test_apply_host_install_identity_outcome_skips_blank_token() -> None:
    model_entrypoint = ModelEntrypoint()
    model_entrypoint.apply_result(HostInstallIdentityOutcome(install_token="   "))
    assert model_entrypoint.host.descriptor.stable_key == ""


def test_apply_host_install_identity_outcome_emits_core_signal() -> None:
    model_entrypoint = ModelEntrypoint()
    received: list[HostComputerIdentityPayload] = []

    def capture(payload: object) -> None:
        assert isinstance(payload, HostComputerIdentityPayload)
        received.append(payload)

    model_entrypoint.subscribe(CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED, capture)
    token = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    model_entrypoint.apply_result(HostInstallIdentityOutcome(install_token=token))

    expected = compute_computer_stable_key(token)
    assert len(received) == 1
    assert received[0].stable_key == expected
