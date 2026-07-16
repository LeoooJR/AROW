"""
Tests for core device model modules.
"""

from __future__ import annotations

import datetime

import pytest

import core.devices.computer as computer_devices
from core.devices.computer import (
    Computer,
    ComputerDescriptor,
    compute_computer_stable_key,
)

pytestmark = [pytest.mark.devices]

# --- Computer ---


class TestComputer:
    """Tests for the Computer device class."""

    def test_computer_creation(self) -> None:
        """Computer can be created with explicit values without relying on host lookup."""
        now = datetime.datetime.now()
        computer = Computer(
            id="host-1",
            name="Workstation",
            os="macOS",
            ip="192.168.1.10",
            state="online",
            last_communication=now,
        )
        assert computer.descriptor.id == "host-1"
        assert computer.descriptor.name == "Workstation"
        assert computer.descriptor.os == "macos"
        assert computer.descriptor.ip == "192.168.1.10"
        assert computer.descriptor.port is None
        assert computer.descriptor.state == "online"
        assert computer.descriptor.last_communication is now
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
            computer_devices.socket, "gethostname", lambda: "workstation"
        )
        monkeypatch.setattr(
            computer_devices.socket, "gethostbyname", lambda _hostname: "192.168.1.10"
        )

        computer = Computer(id="host-1")

        assert computer.descriptor.ip == "192.168.1.10"
        assert computer.network_available is True

    def test_computer_udp_route_probe_used_after_loopback_hostname(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeSocket:
            def __enter__(self) -> "FakeSocket":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def connect(self, _address: tuple[str, int]) -> None:
                return None

            def getsockname(self) -> tuple[str, int]:
                return ("10.0.0.42", 54321)

        monkeypatch.setattr(
            computer_devices.socket, "gethostname", lambda: "workstation"
        )
        monkeypatch.setattr(
            computer_devices.socket, "gethostbyname", lambda _hostname: "127.0.0.1"
        )
        monkeypatch.setattr(
            computer_devices.socket,
            "socket",
            lambda _family, _type: FakeSocket(),
        )

        computer = Computer(id="host-1")

        assert computer.descriptor.ip == "10.0.0.42"
        assert computer.network_available is True

    def test_computer_network_resolution_fallback_marks_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FailingSocket:
            def __enter__(self) -> "FailingSocket":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def connect(self, _address: tuple[str, int]) -> None:
                raise OSError("no route")

        monkeypatch.setattr(
            computer_devices.socket, "gethostname", lambda: "workstation"
        )
        monkeypatch.setattr(
            computer_devices.socket,
            "gethostbyname",
            lambda _hostname: (_ for _ in ()).throw(OSError("lookup failed")),
        )
        monkeypatch.setattr(
            computer_devices.socket,
            "socket",
            lambda _family, _type: FailingSocket(),
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
        computer = Computer(id="host-1", state=None, last_communication=None)
        now = datetime.datetime(2025, 6, 15, 10, 30, 0)

        computer.state = "online"
        computer.last_communication = now

        assert computer.state == "online"
        assert computer.last_communication is now

    def test_computer_equality_and_hash_delegate_to_descriptor(self) -> None:
        first = Computer(id="host-1", name="Workstation", os="macOS", ip="10.0.0.1")
        second = Computer(id="host-1", name="Workstation", os="macOS", ip="10.0.0.1")

        assert first == second
        assert hash(first) == hash(second)

        second.state = "online"
        assert first == second
        assert hash(first) == hash(second)

        third = Computer(id="host-1", name="Workstation 2", os="macOS", ip="10.0.0.1")

        assert first != third
        assert hash(first) != hash(third)

    def test_computer_equality_returns_not_implemented_for_unrelated_types(
        self,
    ) -> None:
        computer = Computer(id="host-1", ip="127.0.0.1")

        assert computer.__eq__(object()) is NotImplemented
        assert computer != object()


class TestComputeComputerStableKey:
    """Host install-token stable keys (distinct from phone hw/fp tiers)."""

    def test_compute_computer_stable_key_empty_token(self) -> None:
        assert compute_computer_stable_key("") == ""
        assert compute_computer_stable_key("   ") == ""

    def test_compute_computer_stable_key_normalized(self) -> None:
        u = "550E8400-E29b-41D4-A716-446655440000"
        expected = "pc:v1:install:" + u.casefold()
        assert compute_computer_stable_key(u) == expected


class TestComputerDescriptorHash:
    """ComputerDescriptor equality and hashing include ``stable_key`` (parity with PhoneDescriptor tests)."""

    def test_stable_key_participates_in_hash_and_eq(self) -> None:
        token_a = compute_computer_stable_key("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        token_b = compute_computer_stable_key("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        d1 = ComputerDescriptor(
            id="host-1",
            name="n",
            os="o",
            ip="127.0.0.1",
            port=None,
            state=None,
            last_communication=None,
            stable_key=token_a,
        )
        d2 = ComputerDescriptor(
            id="host-1",
            name="n",
            os="o",
            ip="127.0.0.1",
            port=None,
            state=None,
            last_communication=None,
            stable_key=token_b,
        )
        assert d1 == d2 and hash(d1) == hash(d2)

        d3 = ComputerDescriptor(
            id="host-1",
            name="n",
            os="o",
            ip="127.0.0.1",
            port=None,
            state=None,
            last_communication=None,
            stable_key=compute_computer_stable_key(
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
            ),
        )
        assert d3 != d1
