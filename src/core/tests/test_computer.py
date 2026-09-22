"""
Tests for core device model modules.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

import core.devices.computer as computer_devices
from core.devices.computer import (
    Computer,
    ComputerDescriptor,
    ComputerRepository,
    compute_computer_stable_key,
)

pytestmark = [pytest.mark.devices]

# --- Computer ---


class TestComputer:
    """Tests for the Computer device class."""

    def test_computer_creation(self) -> None:
        """Computer can be created with explicit values without relying on host lookup."""
        computer = Computer(
            id="host-1",
            name="Workstation",
            os="macOS",
            ip="192.168.1.10",
            state="online",
        )
        assert computer.descriptor.id == "host-1"
        assert computer.descriptor.name == "Workstation"
        assert computer.descriptor.os == "macos"
        assert computer.descriptor.ip == "192.168.1.10"
        assert computer.descriptor.port is None
        assert computer.descriptor.state == "online"
        assert computer.descriptor.stable_key == ""
        assert computer.stable_key == ""
        assert computer.network_available is True

    def test_computer_creation_with_loopback_ip_marks_network_unavailable(self) -> None:
        computer = Computer(id="host-1", ip="127.0.0.1")
        assert computer.descriptor.ip == "127.0.0.1"
        assert computer.network_available is False

    def test_computer_hostname_lookup_sets_network_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            computer_devices,
            "resolve_network_identity",
            lambda: ("192.168.1.10", True),
        )

        computer = Computer(id="host-1")

        assert computer.descriptor.ip == "192.168.1.10"
        assert computer.network_available is True

    def test_computer_udp_route_probe_used_after_loopback_hostname(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            computer_devices,
            "resolve_network_identity",
            lambda: ("10.0.0.42", True),
        )

        computer = Computer(id="host-1")

        assert computer.descriptor.ip == "10.0.0.42"
        assert computer.network_available is True

    def test_computer_network_resolution_fallback_marks_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            computer_devices,
            "resolve_network_identity",
            lambda: ("127.0.0.1", False),
        )

        computer = Computer(id="host-1")

        assert computer.descriptor.ip == "127.0.0.1"
        assert computer.network_available is False

    def test_refresh_network_identity_updates_previous_unavailable_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        computer = Computer(id="host-1", ip="127.0.0.1")
        assert computer.network_available is False

        monkeypatch.setattr(
            computer, "_resolve_network_identity", lambda: ("192.168.1.10", True)
        )
        computer.refresh_network_identity()

        assert computer.descriptor.ip == "192.168.1.10"
        assert computer.network_available is True

    def test_computer_properties_update_descriptor_state(self) -> None:
        computer = Computer(id="host-1", state=None)

        computer.state = "online"

        assert computer.state == "online"

    def test_computer_set_stable_key_replaces_descriptor_snapshot(self) -> None:
        computer = Computer(id="host-1", ip="127.0.0.1")
        original = computer.descriptor

        computer.set_stable_key("pc:v1:install:token")

        assert computer.descriptor is not original
        assert computer.stable_key == "pc:v1:install:token"

    def test_computer_uses_object_identity(self) -> None:
        first = Computer(id="host-1", name="Workstation", os="macOS", ip="10.0.0.1")
        second = Computer(id="host-1", name="Workstation", os="macOS", ip="10.0.0.1")

        assert first == first
        assert first != second

    def test_computer_is_unhashable_before_and_after_update(self) -> None:
        computer = Computer(id="host-1", name="Workstation", os="macOS", ip="10.0.0.1")

        with pytest.raises(TypeError):
            hash(computer)

        computer.state = "online"

        with pytest.raises(TypeError):
            hash(computer)

    def test_computer_is_not_equal_to_unrelated_types(self) -> None:
        computer = Computer(id="host-1", ip="127.0.0.1")

        assert computer != object()


class TestComputerRepository:
    """Computer repository ownership and selection behavior."""

    def test_selection_and_removal_require_the_stored_computer_instance(self) -> None:
        stored = Computer(id="host-1", name="Stored", ip="127.0.0.1")
        same_id_clone = Computer(id="host-1", name="Clone", ip="127.0.0.1")
        repository = ComputerRepository()
        repository.add(stored)

        repository.working_device = stored
        with pytest.raises(ValueError, match="not in the repository"):
            repository.working_device = same_id_clone
        repository.remove(same_id_clone)

        assert repository.get("host-1") is stored
        assert repository.working_device is stored

        repository.remove(stored)

        assert repository.get("host-1") is None
        assert repository.working_device is None


class TestComputeComputerStableKey:
    """Host install-token stable keys (distinct from phone hw/fp tiers)."""

    def test_compute_computer_stable_key_empty_token(self) -> None:
        assert compute_computer_stable_key("") == ""
        assert compute_computer_stable_key("   ") == ""

    def test_compute_computer_stable_key_normalized(self) -> None:
        u = "550E8400-E29b-41D4-A716-446655440000"
        expected = "pc:v1:install:" + u.casefold()
        assert compute_computer_stable_key(u) == expected


class TestComputerDescriptorEquality:
    """ComputerDescriptor supports state comparison without mutable hashing."""

    def test_stable_key_participates_in_equality(self) -> None:
        token_a = compute_computer_stable_key("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        token_b = compute_computer_stable_key("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        d1 = ComputerDescriptor(
            id="host-1",
            name="n",
            os="o",
            ip="127.0.0.1",
            port=None,
            state=None,
            stable_key=token_a,
        )
        d2 = ComputerDescriptor(
            id="host-1",
            name="n",
            os="o",
            ip="127.0.0.1",
            port=None,
            state=None,
            stable_key=token_b,
        )
        assert d1 == d2
        with pytest.raises(TypeError):
            hash(d1)

        with pytest.raises(FrozenInstanceError):
            d1.name = "updated"  # type: ignore[misc]
        updated = replace(d1, name="updated")
        with pytest.raises(TypeError):
            hash(updated)

        d3 = ComputerDescriptor(
            id="host-1",
            name="n",
            os="o",
            ip="127.0.0.1",
            port=None,
            state=None,
            stable_key=compute_computer_stable_key(
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
            ),
        )
        assert d3 != d1
