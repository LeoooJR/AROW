"""
Tests for src/core/devices.py (DeviceDescriptor, Device, Phone, Computer).
"""

from __future__ import annotations

import datetime

import pytest

import core.devices as devices
from core.devices import (
    DEFAULT_PHONE_DISPLAY_NAME,
    Computer,
    ComputerDescriptor,
    DeviceDescriptor,
    Phone,
    PhoneDescriptor,
    apply_phone_android_api_level_enrichment,
    apply_phone_android_release_enrichment,
    apply_phone_device_name_enrichment,
    apply_phone_manufacturer_enrichment,
    apply_phone_product_model_enrichment,
    apply_phone_ro_serial_enrichment,
    compute_computer_stable_key,
    compute_phone_stable_key,
    connect_to_device,
    phone_stable_key_is_collision_resistant,
)

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
        assert phone.stable_key == ""

    def test_phone_hardware_serial_derives_stable_key_tier_one(self) -> None:
        """Explicit hardware_serial produces hw:v1: Tier-1 stable_key."""
        phone = Phone(
            id="x",
            name="n",
            product="prod",
            model="mod",
            hardware_serial="  SN999  ",
            manufacturer="",
        )
        assert phone.hardware_serial == "SN999"
        assert phone.stable_key == "hw:v1:SN999"

    def test_apply_phone_ro_serial_enrichment_updates_stable_key(self) -> None:
        phone = Phone(
            id="dev",
            name="Pixel",
            product="prod",
            model="mod",
            state="device",
        )
        apply_phone_ro_serial_enrichment(phone, "ABC123DEVICE\n")
        assert phone.hardware_serial == "ABC123DEVICE"
        assert phone.stable_key == "hw:v1:ABC123DEVICE"

    def test_apply_phone_manufacturer_and_model_updates_tier_two_stable_key(
        self,
    ) -> None:
        """Without serial, manufacturer + model enrichment produces fp:v1: stable_key."""
        phone = Phone(
            id="dev", name="Pixel", product="ocean", model="m1", state="device"
        )
        assert phone.stable_key == ""
        apply_phone_manufacturer_enrichment(phone, "FabCo")
        apply_phone_product_model_enrichment(phone, "OceanView")
        assert phone.descriptor.manufacturer == "FabCo"
        assert phone.descriptor.model == "OceanView"
        assert phone.stable_key.startswith("fp:v1:")

    def test_apply_shell_property_enrichment_tier_one_unchanged(self) -> None:
        """After Tier-1 serial, model enrichment does not change hw stable_key."""
        phone = Phone(
            id="dev", name="Pixel", product="ocean", model="m1", state="device"
        )
        apply_phone_ro_serial_enrichment(phone, "SERIALX")
        key = phone.stable_key
        apply_phone_product_model_enrichment(phone, "OceanView")
        assert phone.descriptor.model == "OceanView"
        assert phone.stable_key == key == "hw:v1:SERIALX"

    def test_apply_phone_android_release_sets_os(self) -> None:
        phone = Phone(id="x", name="n", os="", state="device")
        apply_phone_android_release_enrichment(phone, " 15 \n")
        assert phone.descriptor.os == "15"

    def test_apply_phone_device_name_blank_clears_shell_and_recomputes_display(
        self,
    ) -> None:
        """Blank ``device_name`` clears shell override; label falls back to list token / model."""
        phone = Phone(
            id="x",
            name="keep-token",
            model="ModX",
            state="device",
        )
        apply_phone_device_name_enrichment(phone, "  ")
        assert phone.descriptor.shell_device_name == ""
        # Model beats legacy name-as-list-token for display.
        assert phone.descriptor.name == "ModX"

    def test_display_name_model_only_before_manufacturer(self) -> None:
        phone = Phone(
            id="dev1",
            product="ocean",
            model="OceanPhone",
            device="Handset1",
            state="device",
        )
        assert phone.descriptor.name == "OceanPhone"

    def test_display_name_manufacturer_and_model_after_enrichment(self) -> None:
        phone = Phone(
            id="dev1",
            model="OceanPhone",
            device="Handset1",
            state="device",
        )
        apply_phone_manufacturer_enrichment(phone, "FabCo")
        assert phone.descriptor.name == "FabCo OceanPhone"

    def test_display_name_getprop_overrides_manufacturer_model(self) -> None:
        phone = Phone(id="d", model="X", manufacturer="Fab", state="device")
        assert "Fab" in phone.descriptor.name
        apply_phone_device_name_enrichment(phone, "Living Room Phone")
        assert phone.descriptor.name == "Living Room Phone"
        assert phone.descriptor.shell_device_name == "Living Room Phone"

    def test_connect_to_device_default_display(self) -> None:
        phone = connect_to_device("192.168.1.20", 5555, "123456")
        assert phone.descriptor.name == DEFAULT_PHONE_DISPLAY_NAME

    def test_sync_phone_display_name_long_id_suffix(self) -> None:
        pid = "adb-X9ZZ99000012345678-aBc1dE"
        phone = Phone(id=pid, state="device")
        assert phone.descriptor.name == f"{DEFAULT_PHONE_DISPLAY_NAME} (8-aBc1dE)"

    def test_sync_phone_display_name_emulator_id(self) -> None:
        phone = Phone(id="emulator-5554", state="offline")
        assert phone.descriptor.name == "emulator-5554"

    def test_apply_phone_android_api_level(self) -> None:
        phone = Phone(id="x", name="n", state="device")
        apply_phone_android_api_level_enrichment(phone, 35)
        assert phone.descriptor.android_api_level == 35
        apply_phone_android_api_level_enrichment(phone, None)
        assert phone.descriptor.android_api_level == 35


class TestComputePhoneStableKey:
    """Tests for stable key derivation."""

    def test_tier_one_known_serial(self) -> None:
        assert (
            compute_phone_stable_key(hardware_serial="SN1", product="x", model="y")
            == "hw:v1:SN1"
        )

    def test_unknown_serial_falls_through(self) -> None:
        """unknown (any case) is not treated as Tier-1."""

        fp = compute_phone_stable_key(
            hardware_serial="unknown",
            product="prod",
            model="mod",
            fingerprint_when_no_serial=True,
        )
        assert fp.startswith("fp:v1:")
        fp2 = compute_phone_stable_key(
            hardware_serial="unknown",
            product="prod",
            model="mod",
            fingerprint_when_no_serial=False,
        )
        assert fp2 == ""

    def test_fingerprint_stable_for_same_inputs(self) -> None:
        a = compute_phone_stable_key(
            hardware_serial=None,
            product=" Prod ",
            model=" Mod ",
            manufacturer="Fab",
            fingerprint_when_no_serial=True,
        )
        b = compute_phone_stable_key(
            hardware_serial="",
            product=" Prod ",
            model=" Mod ",
            manufacturer="Fab ",
            fingerprint_when_no_serial=True,
        )
        assert a == b and a.startswith("fp:v1:")

    @pytest.mark.parametrize(
        ("stable_key", "expected"),
        [
            ("hw:v1:SER-123", True),
            ("fp:v1:deadbeef", False),
            ("pc:v1:install:host-token", False),
            ("", False),
        ],
    )
    def test_collision_resistance_only_allows_tier_one_keys(
        self, stable_key: str, expected: bool
    ) -> None:
        assert phone_stable_key_is_collision_resistant(stable_key) is expected


class TestPhoneDescriptorHash:
    """PhoneDescriptor equality and hashing reflect full dataclass state including ``stable_key``."""

    def test_stable_key_participates_in_hash_and_eq(self) -> None:
        fixed_last = datetime.datetime(2025, 6, 15, 10, 30, 0)
        sk_tier_one = compute_phone_stable_key(
            hardware_serial="SN123",
            product="prod",
            model="mod",
            fingerprint_when_no_serial=False,
        )
        assert sk_tier_one == "hw:v1:SN123"

        d1 = PhoneDescriptor(
            id="adb-1",
            name="n",
            os="Android",
            ip="10.0.0.1",
            port=5555,
            product="prod",
            model="mod",
            transport_id="1",
            state="device",
            last_communication=fixed_last,
            hardware_serial="SN123",
            stable_key=sk_tier_one,
            manufacturer="",
        )
        d2 = PhoneDescriptor(
            id="adb-1",
            name="n",
            os="Android",
            ip="10.0.0.1",
            port=5555,
            product="prod",
            model="mod",
            transport_id="1",
            state="device",
            last_communication=fixed_last,
            hardware_serial="SN123",
            stable_key=sk_tier_one,
            manufacturer="",
        )
        assert d1 == d2 and hash(d1) == hash(d2)

        sk_fingerprint = compute_phone_stable_key(
            hardware_serial=None,
            product="prod",
            model="mod",
            manufacturer="Fab",
            fingerprint_when_no_serial=True,
        )
        assert sk_fingerprint.startswith("fp:v1:")
        d3 = PhoneDescriptor(
            id="adb-1",
            name="n",
            os="Android",
            ip="10.0.0.1",
            port=5555,
            product="prod",
            model="mod",
            transport_id="1",
            state="device",
            last_communication=fixed_last,
            hardware_serial="",
            stable_key=sk_fingerprint,
            manufacturer="Fab",
        )
        assert d3 != d1


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
        assert computer.is_network_available() is True

    def test_computer_creation_with_loopback_ip_marks_network_unavailable(self) -> None:
        computer = Computer(id="host-1", ip="127.0.0.1")
        assert computer.descriptor.ip == "127.0.0.1"
        assert computer.is_network_available() is False

    def test_computer_hostname_lookup_sets_network_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(devices.socket, "gethostname", lambda: "workstation")
        monkeypatch.setattr(
            devices.socket, "gethostbyname", lambda _hostname: "192.168.1.10"
        )

        computer = Computer(id="host-1")

        assert computer.descriptor.ip == "192.168.1.10"
        assert computer.is_network_available() is True

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

        monkeypatch.setattr(devices.socket, "gethostname", lambda: "workstation")
        monkeypatch.setattr(
            devices.socket, "gethostbyname", lambda _hostname: "127.0.0.1"
        )
        monkeypatch.setattr(
            devices.socket,
            "socket",
            lambda _family, _type: FakeSocket(),
        )

        computer = Computer(id="host-1")

        assert computer.descriptor.ip == "10.0.0.42"
        assert computer.is_network_available() is True

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

        monkeypatch.setattr(devices.socket, "gethostname", lambda: "workstation")
        monkeypatch.setattr(
            devices.socket,
            "gethostbyname",
            lambda _hostname: (_ for _ in ()).throw(OSError("lookup failed")),
        )
        monkeypatch.setattr(
            devices.socket,
            "socket",
            lambda _family, _type: FailingSocket(),
        )

        computer = Computer(id="host-1")

        assert computer.descriptor.ip == "127.0.0.1"
        assert computer.is_network_available() is False

    def test_refresh_network_identity_updates_previous_unavailable_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        computer = Computer(id="host-1", ip="127.0.0.1")
        assert computer.is_network_available() is False

        monkeypatch.setattr(
            computer, "_resolve_network_identity", lambda: ("192.168.1.10", True)
        )
        computer.refresh_network_identity()

        assert computer.descriptor.ip == "192.168.1.10"
        assert computer.is_network_available() is True


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
