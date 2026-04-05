"""
Tests for src/core/devices.py (DeviceState, Device, Phone, Computer).
"""

from __future__ import annotations

import datetime

import pytest

from core.devices import Computer, DeviceState, Phone

pytestmark = [pytest.mark.devices]


# --- DeviceState ---


class TestDeviceState:
    """Tests for the DeviceState dataclass."""

    def test_device_state_defaults(self) -> None:
        """DeviceState has expected default values."""
        state = DeviceState()
        assert state.id == ""
        assert state.name == ""
        assert state.os == ""
        assert state.ip == ""
        assert state.port is None
        assert state.state is None
        assert state.last_communication is None

    def test_device_state_custom_values(self) -> None:
        """DeviceState accepts and stores custom values."""
        now = datetime.datetime.now()
        state = DeviceState(
            id="abc123",
            name="Pixel",
            os="Android",
            ip="192.168.1.1",
            port=5555,
            state="device",
            last_communication=now,
        )
        assert state.id == "abc123"
        assert state.name == "Pixel"
        assert state.os == "Android"
        assert state.ip == "192.168.1.1"
        assert state.port == 5555
        assert state.state == "device"
        assert state.last_communication is now


# --- Phone ---


class TestPhone:
    """Tests for the Phone device class."""

    def test_phone_from_string_success(self) -> None:
        """Phone.from_string parses a valid device line (exactly 6 space-separated fields)."""
        line = "abc123 device product:model device:name 5555 transport_id:1"
        phone = Phone.from_string(line)
        assert phone.state.id == "abc123"
        assert phone.state.name == "device"
        assert phone.state.os == "product:model"
        assert phone.state.ip == "device:name"
        assert phone.state.port == 5555
        assert phone.state.state == "transport_id:1"

    def test_phone_from_string_minimal(self) -> None:
        """Phone.from_string with minimal tokens (id name os ip port state)."""
        line = "emulator-5554 Android device 10.0.2.2 5555 device"
        phone = Phone.from_string(line)
        assert phone.state.id == "emulator-5554"
        assert phone.state.name == "Android"
        assert phone.state.os == "device"
        assert phone.state.ip == "10.0.2.2"
        assert phone.state.port == 5555
        assert phone.state.state == "device"

    def test_phone_from_string_invalid_too_few_tokens(self) -> None:
        """Phone.from_string raises when there are too few fields."""
        with pytest.raises(ValueError, match="not enough values to unpack"):
            Phone.from_string("id name os")

    def test_phone_from_string_invalid_port_not_int(self) -> None:
        """Phone.from_string raises when port is not an integer."""
        with pytest.raises(ValueError, match="invalid literal"):
            Phone.from_string("id name os ip not_a_number state")

    def test_phone_str_repr(self) -> None:
        """Phone __str__ and __repr__ are defined and non-empty."""
        phone = Phone(id="x", name="n", os="o", ip="i", port=1, state="s")
        assert "n" in str(phone)
        assert "Phone" in repr(phone)
        assert "x" in repr(phone)

    def test_phone_update_state(self) -> None:
        """Phone.update_state updates only given fields."""
        phone = Phone(id="a", name="b", os="c", ip="d", port=1, state="e")
        phone.update_state(name="updated", port=9999)
        assert phone.state.name == "updated"
        assert phone.state.port == 9999
        assert phone.state.id == "a"


# --- Computer ---


class TestComputer:
    """Tests for the Computer device class."""

    def test_computer_creation(self) -> None:
        """Computer can be created with an id and has platform-derived fields."""
        computer = Computer(id="host-1")
        assert computer.state.id == "host-1"
        assert computer.state.name
        assert computer.state.os
        assert computer.state.ip
        assert computer.state.port is None
        assert computer.state.state is None

    def test_computer_from_string_not_implemented(self) -> None:
        """Computer.from_string is not implemented (returns None / pass)."""
        # Current implementation is "pass" with no return; calling it may return None.
        result = Computer.from_string("any")
        assert result is None
