"""
Tests for src/core/devices.py (DeviceDescriptor, Device, Phone, Computer).
"""

from __future__ import annotations

import datetime

import pytest

from core.devices import Computer, DeviceDescriptor, Phone, connect_to_device

pytestmark = [pytest.mark.devices]


# --- DeviceDescriptor ---


class TestDeviceDescriptor:
    """Tests for the DeviceDescriptor dataclass."""

    def test_device_state_defaults(self) -> None:
        """DeviceDescriptor has expected default values."""
        state = DeviceDescriptor()
        assert state.id == ""
        assert state.name == ""
        assert state.os == ""
        assert state.ip == ""
        assert state.port is None

    def test_device_state_custom_values(self) -> None:
        """DeviceDescriptor accepts and stores custom values."""
        state = DeviceDescriptor(
            id="abc123",
            name="Pixel",
            os="Android",
            ip="192.168.1.1",
            port=5555,
        )
        assert state.id == "abc123"
        assert state.name == "Pixel"
        assert state.os == "Android"
        assert state.ip == "192.168.1.1"
        assert state.port == 5555


# --- Phone ---


class TestPhone:
    """Tests for the Phone device class."""

    def test_phone_from_string_success(self) -> None:
        """Phone.from_string parses an ADB `devices -l` line with six tokens."""
        line = "abc123 device product:model model:pixel device:Pixel transport_id:1"
        phone = Phone.from_string(line)
        assert phone.descriptor.id == "abc123"
        assert phone.descriptor.name == "device:Pixel"
        assert phone.descriptor.product == "product:model"
        assert phone.descriptor.model == "model:pixel"
        assert phone.descriptor.state == "device"
        assert phone.transport_id == ""

    def test_phone_from_string_six_token_line_is_parsed_positionally(self) -> None:
        """Phone.from_string uses the current six-token positional parser."""
        line = "emulator-5554 offline product:sdk model:sdk_gphone device:emulator transport_id:9"
        phone = Phone.from_string(line)
        assert phone.descriptor.id == "emulator-5554"
        assert phone.descriptor.name == "device:emulator"
        assert phone.descriptor.product == "product:sdk"
        assert phone.descriptor.model == "model:sdk_gphone"
        assert phone.descriptor.state == "offline"

    def test_phone_from_string_invalid_too_few_tokens(self) -> None:
        """Phone.from_string raises when there are too few fields."""
        with pytest.raises(ValueError, match="not enough values to unpack"):
            Phone.from_string("id name os")

    def test_phone_descriptor_setter(self) -> None:
        """Assigning `phone.descriptor = ...` updates the nested PhoneDescriptor status field."""
        phone = Phone(id="id", name="Pixel", state="online")
        phone.state = "offline"
        assert phone.descriptor.state == "offline"

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
        assert phone.descriptor.name == "updated"
        assert phone.descriptor.port == 9999
        assert phone.descriptor.id == "a"

    def test_connect_to_device_returns_phone_with_requested_endpoint(self) -> None:
        """connect_to_device returns a Phone configured with the requested ip/port."""
        phone = connect_to_device("192.168.1.20", 5555, "123456")
        assert phone.descriptor.ip == "192.168.1.20"
        assert phone.descriptor.port == 5555
        assert phone.descriptor.state == ""


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

    def test_computer_from_string_not_implemented(self) -> None:
        """Computer.from_string currently raises a NotImplementedError."""
        with pytest.raises(NotImplementedError, match="not implemented yet"):
            Computer.from_string("any")
