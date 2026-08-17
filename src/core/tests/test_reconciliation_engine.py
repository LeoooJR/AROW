"""Unit tests for paired-phone reconciliation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from core.devices.phone import Phone, PhoneRepository
from core.devices.reconciliation import ReconciliationEngine

pytestmark = [pytest.mark.devices]


def _repository(*phones: Phone) -> PhoneRepository:
    repository = PhoneRepository()
    for phone in phones:
        repository.add(phone)
    return repository


def test_reconcile_adds_newly_discovered_phone() -> None:
    repository = _repository()
    discovered = Phone(id="fresh-device", state="device", model="Pixel")

    result = ReconciliationEngine().reconcile(repository, [discovered])

    assert result.changed is True
    assert result.device_id_rebindings == {}
    assert result.removed_device_ids == ()
    assert repository.get("fresh-device") is discovered


def test_reconcile_result_is_immutable() -> None:
    result = ReconciliationEngine().reconcile(_repository(), [])

    with pytest.raises(FrozenInstanceError):
        result.changed = True  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.device_id_rebindings["old"] = "new"  # type: ignore[index]


def test_reconcile_identical_phone_is_a_noop() -> None:
    paired = Phone(id="device-1", state="device", model="Pixel")
    discovered = Phone(id="device-1", state="device", model="Pixel")
    discovered.descriptor.last_communication = paired.descriptor.last_communication
    repository = _repository(paired)

    result = ReconciliationEngine().reconcile(repository, [discovered])

    assert result.changed is False
    assert result.device_id_rebindings == {}
    assert result.removed_device_ids == ()
    assert repository.get("device-1") is paired


def test_reconcile_updates_existing_phone_in_place() -> None:
    paired = Phone(id="device-1", state="device", model="Old model")
    discovered = Phone(id="device-1", state="offline", model="New model")
    repository = _repository(paired)

    result = ReconciliationEngine().reconcile(repository, [discovered])

    assert result.changed is True
    assert repository.get("device-1") is paired
    assert paired.model == "New model"
    assert paired.state == "offline"


def test_reconcile_rebinds_collision_resistant_stable_identity() -> None:
    paired = Phone(
        id="192.168.0.10:5555",
        hardware_serial="SER-RECONNECT",
        state="device",
    )
    discovered = Phone(
        id="192.168.0.10:37849",
        hardware_serial="SER-RECONNECT",
        state="device",
    )
    repository = _repository(paired)

    result = ReconciliationEngine().reconcile(repository, [discovered])

    assert result.device_id_rebindings == {"192.168.0.10:5555": "192.168.0.10:37849"}
    assert repository.get("192.168.0.10:5555") is None
    assert repository.get("192.168.0.10:37849") is paired


def test_reconcile_reports_removed_phone_ids_in_repository_order() -> None:
    repository = _repository(
        Phone(id="stale-a", state="device"),
        Phone(id="stale-b", state="offline"),
    )

    result = ReconciliationEngine().reconcile(repository, [])

    assert result.changed is True
    assert result.removed_device_ids == ("stale-a", "stale-b")
    assert list(repository) == []


def test_reconcile_uses_last_discovery_for_duplicate_connection_id() -> None:
    repository = _repository()
    first = Phone(id="device-1", state="offline", model="Old model")
    last = Phone(id="device-1", state="device", model="Current model")

    result = ReconciliationEngine().reconcile(repository, [first, last])

    assert result.changed is True
    assert repository.get("device-1") is last


def test_reconcile_skips_discovered_phone_with_blank_id() -> None:
    repository = _repository()

    result = ReconciliationEngine().reconcile(
        repository,
        [Phone(id="   ", state="device")],
    )

    assert result.changed is False
    assert result.removed_device_ids == ()
    assert list(repository) == []


def test_reconcile_does_not_rebind_collision_prone_stable_identity() -> None:
    paired = Phone(id="10.0.0.1:5555", state="device", model="Pixel 8")
    discovered = Phone(id="10.0.0.1:44444", state="device", model="Pixel 8")
    for phone in (paired, discovered):
        phone.manufacturer = "Google"
        phone.hardware_serial = ""
        assert phone.stable_key.startswith("fp:v1:")
    repository = _repository(paired)

    result = ReconciliationEngine().reconcile(repository, [discovered])

    assert result.device_id_rebindings == {}
    assert result.removed_device_ids == ("10.0.0.1:5555",)
    assert repository.get("10.0.0.1:44444") is discovered
