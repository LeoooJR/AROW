"""
Tests for core device model modules.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from core.devices.base import DeviceDescriptor

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

    def test_device_descriptor_is_immutable_and_unhashable(self) -> None:
        """Descriptor snapshots are immutable without becoming identity keys."""
        descriptor = DeviceDescriptor(id="device-1")

        with pytest.raises(TypeError):
            hash(descriptor)
        with pytest.raises(FrozenInstanceError):
            descriptor.name = "Updated device"  # type: ignore[misc]

        updated = replace(descriptor, name="Updated device")

        with pytest.raises(TypeError):
            hash(updated)
        assert updated.name == "Updated device"
        assert descriptor.name == ""
