"""Tests for physical phones, ADB connections, identities, and repositories."""

from __future__ import annotations

import datetime
from dataclasses import FrozenInstanceError

import pytest

from core.devices.phone import (
    AdbConnection,
    Phone,
    PhoneDescriptor,
    PhoneIdentity,
    PhoneRepository,
)

pytestmark = [pytest.mark.devices]


def _connection(
    id: str,
    *,
    state: str = "device",
    kind: str = "usb",
    at: datetime.datetime | None = None,
) -> AdbConnection:
    return AdbConnection.observed(
        id,
        state=state,
        connectivity_type=kind,  # type: ignore[arg-type]
        observed_at=at,
    )


class TestAdbConnection:
    def test_active_observation_records_timestamp(self) -> None:
        at = datetime.datetime(2025, 6, 15, 10, 30)
        active = _connection("usb-1", at=at)
        offline = _connection("wifi-1", state="offline", at=at)

        assert active.is_active is True
        assert active.last_connection == at
        assert offline.is_active is False
        assert offline.last_connection is None

    def test_connection_is_immutable_structural_and_unhashable(self) -> None:
        first = _connection("usb-1")
        second = AdbConnection.deserialize(first.serialize())

        assert first == second
        with pytest.raises(FrozenInstanceError):
            first.state = "offline"  # type: ignore[misc]
        with pytest.raises(TypeError):
            hash(first)

    def test_connection_json_timestamp_round_trip(self) -> None:
        at = datetime.datetime(2025, 6, 15, 10, 30)
        payload = _connection("usb-1", at=at).serialize(json_compatible=True)

        assert payload["last_connection"] == "2025-06-15T10:30:00"
        assert AdbConnection.deserialize(payload).last_connection == at


class TestPhoneIdentity:
    def test_tier_one_identity_is_hashable(self) -> None:
        first = PhoneIdentity.from_stable_key("hw:v1:SERIAL-1")
        second = PhoneIdentity.from_stable_key("hw:v1:SERIAL-1")

        assert first is not None and first == second
        assert hash(first) == hash(second)

    def test_tier_two_identity_is_rejected(self) -> None:
        assert PhoneIdentity.from_stable_key("fp:v1:" + "a" * 64) is None
        assert PhoneIdentity.provisional().is_provisional is True


class TestPhone:
    def test_phone_owns_connections_without_endpoint_forwarding(self) -> None:
        phone = Phone(_connection("usb-1"), model="Pixel")

        assert phone.connections[0].id == "usb-1"
        assert phone.target_connection is phone.connections[0]
        assert not hasattr(phone, "state")
        assert not hasattr(phone, "ip")
        assert not hasattr(phone, "last_connection")

    def test_phone_prefers_sticky_connection_then_usb_fallback(self) -> None:
        phone = Phone(_connection("usb-1"))
        phone.add_connection(_connection("wifi-1", kind="wifi"))
        phone.select_connection("wifi-1")

        assert phone.target_connection is not None
        assert phone.target_connection.id == "wifi-1"

        discovered = Phone(_connection("usb-1"), identity=phone.identity)
        discovered.add_connection(_connection("wifi-1", state="offline", kind="wifi"))
        phone.apply_discovery(discovered)

        assert phone.target_connection is not None
        assert phone.target_connection.id == "usb-1"

    def test_phone_has_no_target_when_every_connection_is_inactive(self) -> None:
        phone = Phone(_connection("usb-1", state="offline"))

        assert phone.target_connection is None
        with pytest.raises(ValueError, match="not active"):
            phone.select_connection("usb-1")

    def test_tier_one_enrichment_promotes_provisional_identity(self) -> None:
        phone = Phone(_connection("usb-1"))
        assert phone.identity.is_provisional

        phone.apply_shell_enrichment(
            manufacturer="Google",
            model="Pixel",
            shell_device_name="Field phone",
            os="15",
            android_api_level=35,
            hardware_serial="SERIAL-1",
        )

        assert phone.identity == PhoneIdentity("hw:v1:SERIAL-1")
        assert phone.stable_key == "hw:v1:SERIAL-1"
        assert phone.name == "Field phone"

    def test_apply_discovery_preserves_inactive_connection_recency(self) -> None:
        at = datetime.datetime(2025, 6, 15, 10, 30)
        phone = Phone(_connection("usb-1", at=at))
        discovered = Phone(
            _connection("usb-1", state="offline"), identity=phone.identity
        )

        changed = phone.apply_discovery(discovered)

        assert changed is True
        assert phone.connections[0].state == "offline"
        assert phone.connections[0].last_connection == at

    def test_apply_discovery_reports_effective_noop(self) -> None:
        at = datetime.datetime(2025, 6, 15, 10, 30)
        phone = Phone(_connection("usb-1", at=at), model="Pixel")
        discovered = Phone(
            _connection("usb-1", at=at),
            identity=phone.identity,
            model="Pixel",
        )

        changed = phone.apply_discovery(discovered)

        assert changed is False

    def test_nested_serialization_round_trip(self) -> None:
        phone = Phone(
            _connection("usb-1"),
            hardware_serial="SERIAL-1",
            model="Pixel",
        )
        phone.add_connection(_connection("wifi-1", kind="wifi"))

        payload = phone.serialize(json_compatible=True)
        restored = Phone.deserialize(payload)

        assert payload["id"] == "hw:v1:SERIAL-1"
        assert len(payload["connections"]) == 2  # type: ignore[arg-type]
        assert restored.identity == phone.identity
        assert restored.connections == phone.connections

    def test_legacy_flat_payload_becomes_one_connection(self) -> None:
        restored = Phone.deserialize(
            {
                "id": "legacy-endpoint",
                "name": "Pixel",
                "state": "offline",
                "connectivity_type": "usb",
                "last_connection": "2025-06-15T10:30:00",
            }
        )

        assert restored.identity.is_provisional
        assert restored.connections[0].id == "legacy-endpoint"
        assert restored.connections[0].last_connection == datetime.datetime(
            2025, 6, 15, 10, 30
        )

    def test_phone_and_descriptor_are_unhashable(self) -> None:
        phone = Phone(_connection("usb-1"))
        descriptor = PhoneDescriptor(name="Pixel")

        assert phone == phone
        assert phone != Phone(_connection("usb-1"))
        with pytest.raises(TypeError):
            hash(phone)
        with pytest.raises(TypeError):
            hash(descriptor)


class TestPhoneRepository:
    def test_indexes_physical_identity_and_connections(self) -> None:
        phone = Phone(_connection("usb-1"), hardware_serial="SERIAL-1")
        phone.add_connection(_connection("wifi-1", kind="wifi"))
        repository = PhoneRepository()

        repository.add(phone)

        assert repository.get("hw:v1:SERIAL-1") is phone
        assert repository.get_by_connection_id("usb-1") is phone
        assert repository.get_by_connection_id("wifi-1") is phone

    def test_reindex_preserves_working_instance(self) -> None:
        phone = Phone(_connection("usb-1"))
        repository = PhoneRepository()
        repository.add(phone)
        old_identity = phone.identity.value

        phone.hardware_serial = "SERIAL-1"
        repository.reindex(
            phone,
            old_identity=old_identity,
            old_connection_ids=("usb-1",),
        )

        assert repository.get(old_identity) is None
        assert repository.get("hw:v1:SERIAL-1") is phone
        assert repository.working_device is phone

    def test_selection_and_removal_require_exact_instance(self) -> None:
        identity = PhoneIdentity("hw:v1:SERIAL-1")
        stored = Phone(_connection("usb-1"), identity=identity)
        clone = Phone(_connection("usb-2"), identity=identity)
        repository = PhoneRepository()
        repository.add(stored)

        with pytest.raises(ValueError):
            repository.working_device = clone
        repository.remove(clone)

        assert repository.get(identity.value) is stored
        repository.remove(stored)
        assert repository.get(identity.value) is None
