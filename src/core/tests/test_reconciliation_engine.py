"""Tests for physical-phone/ADB-connection reconciliation."""

from __future__ import annotations

import datetime

from core.devices.phone import AdbConnection, Phone, PhoneRepository
from core.devices.reconciliation import ReconciliationEngine


def _phone(
    connection_id: str,
    *,
    serial: str = "",
    state: str = "device",
    kind: str = "usb",
    at: datetime.datetime | None = None,
) -> Phone:
    return Phone(
        AdbConnection.observed(
            connection_id,
            state=state,
            connectivity_type=kind,  # type: ignore[arg-type]
            observed_at=at,
        ),
        hardware_serial=serial,
        model="Pixel",
    )


def _repository(*phones: Phone) -> PhoneRepository:
    repository = PhoneRepository()
    repository.add_all(list(phones))
    return repository


def test_simultaneous_usb_and_wifi_group_into_one_physical_phone() -> None:
    usb = _phone("usb-1", serial="SERIAL-1")
    wifi = _phone("192.168.1.2:5555", serial="SERIAL-1", kind="wifi")
    repository = _repository()

    result = ReconciliationEngine().reconcile(repository, [wifi, usb])

    phone = repository.get("hw:v1:SERIAL-1")
    assert result.changed is True
    assert phone is not None
    assert [connection.id for connection in phone.connections] == [
        "192.168.1.2:5555",
        "usb-1",
    ]
    assert phone.target_connection is not None
    assert phone.target_connection.id == "usb-1"


def test_same_snapshot_is_independent_of_repository_history() -> None:
    paired = _phone("usb-1", serial="SERIAL-1")
    repository = _repository(paired)
    usb = _phone("usb-1", serial="SERIAL-1")
    wifi = _phone("wifi-1", serial="SERIAL-1", kind="wifi")

    ReconciliationEngine().reconcile(repository, [usb, wifi])

    assert len(repository) == 1
    assert repository.get("hw:v1:SERIAL-1") is paired
    assert {item.id for item in paired.connections} == {"usb-1", "wifi-1"}


def test_missing_connection_is_pruned_but_phone_instance_survives() -> None:
    paired = _phone("usb-1", serial="SERIAL-1")
    paired.add_connection(
        AdbConnection.observed("wifi-1", state="device", connectivity_type="wifi")
    )
    repository = _repository(paired)

    result = ReconciliationEngine().reconcile(
        repository, [_phone("usb-1", serial="SERIAL-1")]
    )

    assert result.changed is True
    assert repository.get("hw:v1:SERIAL-1") is paired
    assert [connection.id for connection in paired.connections] == ["usb-1"]


def test_absent_phone_is_removed_by_physical_identity() -> None:
    paired = _phone("usb-1", serial="SERIAL-1")
    repository = _repository(paired)

    result = ReconciliationEngine().reconcile(repository, [])

    assert result.removed_phone_ids == ("hw:v1:SERIAL-1",)
    assert len(repository) == 0


def test_active_timestamp_advances_and_inactive_preserves() -> None:
    earlier = datetime.datetime(2025, 6, 15, 10, 30)
    later = datetime.datetime(2025, 6, 15, 10, 31)
    paired = _phone("usb-1", serial="SERIAL-1", at=earlier)
    repository = _repository(paired)

    active_result = ReconciliationEngine().reconcile(
        repository, [_phone("usb-1", serial="SERIAL-1", at=later)]
    )
    inactive_result = ReconciliationEngine().reconcile(
        repository,
        [_phone("usb-1", serial="SERIAL-1", state="offline")],
    )

    assert active_result.changed is True
    assert inactive_result.changed is True
    assert paired.connections[0].last_connection == later


def test_provisional_identity_promotes_and_reports_rebinding() -> None:
    paired = _phone("usb-1")
    old_identity = paired.identity.value
    repository = _repository(paired)

    result = ReconciliationEngine().reconcile(
        repository, [_phone("usb-1", serial="SERIAL-1")]
    )

    assert result.phone_id_rebindings == {old_identity: "hw:v1:SERIAL-1"}
    assert repository.get("hw:v1:SERIAL-1") is paired


def test_tier_two_lookalikes_remain_separate() -> None:
    first = _phone("usb-1")
    second = _phone("wifi-1", kind="wifi")
    for phone in (first, second):
        phone.manufacturer = "Google"
        assert phone.stable_key.startswith("fp:v1:")
    repository = _repository()

    ReconciliationEngine().reconcile(repository, [first, second])

    assert len(repository) == 2
