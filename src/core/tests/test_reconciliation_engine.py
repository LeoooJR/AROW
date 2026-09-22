"""Tests for physical-phone/ADB-connection reconciliation."""

from __future__ import annotations

import datetime

from core.devices.phone import AdbConnection, Phone, PhoneRepository
from core.devices.reconciliation import (
    PhoneAdded,
    PhoneIdentityChanged,
    PhoneRemoved,
    PhoneUpdated,
    ReconciliationEngine,
)


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
    assert result.has_changes is True
    assert result.changes == (PhoneAdded("hw:v1:SERIAL-1"),)
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

    assert result.changes == (PhoneUpdated(paired.id),)
    assert repository.get("hw:v1:SERIAL-1") is paired
    assert [connection.id for connection in paired.connections] == ["usb-1"]


def test_absent_phone_is_removed_by_physical_identity() -> None:
    paired = _phone("usb-1", serial="SERIAL-1")
    repository = _repository(paired)

    result = ReconciliationEngine().reconcile(repository, [])

    assert result.changes == (PhoneRemoved("hw:v1:SERIAL-1"),)
    assert result.removals == (PhoneRemoved("hw:v1:SERIAL-1"),)
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

    assert active_result.changes == (PhoneUpdated(paired.id),)
    assert inactive_result.changes == (PhoneUpdated(paired.id),)
    assert paired.connections[0].last_connection == later


def test_provisional_identity_promotes_and_reports_rebinding() -> None:
    paired = _phone("usb-1")
    old_identity = paired.identity.value
    repository = _repository(paired)

    result = ReconciliationEngine().reconcile(
        repository, [_phone("usb-1", serial="SERIAL-1")]
    )

    assert result.identity_changes == (
        PhoneIdentityChanged(old_identity, "hw:v1:SERIAL-1"),
    )
    assert repository.get("hw:v1:SERIAL-1") is paired


def test_identity_promotion_merges_usb_and_wifi_into_canonical_phone() -> None:
    paired = _phone("usb-1")
    old_identity = paired.identity.value
    repository = _repository(paired)
    usb = _phone("usb-1", serial="SERIAL-1")
    wifi = _phone("wifi-1", serial="SERIAL-1", kind="wifi")

    result = ReconciliationEngine().reconcile(repository, [wifi, usb])

    assert result.changes == (PhoneIdentityChanged(old_identity, "hw:v1:SERIAL-1"),)
    assert repository.get("hw:v1:SERIAL-1") is paired
    assert [connection.id for connection in paired.connections] == [
        "usb-1",
        "wifi-1",
    ]
    assert paired.target_connection is not None
    assert paired.target_connection.id == "usb-1"


def test_tier_two_lookalikes_remain_separate() -> None:
    first = _phone("usb-1")
    second = _phone("wifi-1", kind="wifi")
    for phone in (first, second):
        phone.manufacturer = "Google"
        assert phone.stable_key.startswith("fp:v1:")
    repository = _repository()

    ReconciliationEngine().reconcile(repository, [first, second])

    assert len(repository) == 2


def test_empty_reconciliation_returns_an_empty_report() -> None:
    result = ReconciliationEngine().reconcile(_repository(), [])

    assert result.has_changes is False
    assert result.changes == ()
    assert result.identity_changes == ()
    assert result.removals == ()


def test_duplicate_connection_keeps_the_last_observation() -> None:
    repository = _repository()
    active = _phone("usb-1", state="device")
    offline = _phone("usb-1", state="offline")

    result = ReconciliationEngine().reconcile(repository, [active, offline])

    stored = repository.get(offline.id)
    assert result.changes == (PhoneAdded(offline.id),)
    assert stored is offline
    assert stored.connections[0].state == "offline"


def test_events_follow_discovery_then_repository_removal_order() -> None:
    first_stale = _phone("stale-1", serial="STALE-1")
    second_stale = _phone("stale-2", serial="STALE-2")
    first_new = _phone("new-1", serial="NEW-1")
    second_new = _phone("new-2", serial="NEW-2")
    repository = _repository(first_stale, second_stale)

    result = ReconciliationEngine().reconcile(repository, [first_new, second_new])

    assert result.changes == (
        PhoneAdded(first_new.id),
        PhoneAdded(second_new.id),
        PhoneRemoved(first_stale.id),
        PhoneRemoved(second_stale.id),
    )
