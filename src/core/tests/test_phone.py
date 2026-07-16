"""
Tests for core device model modules.
"""

from __future__ import annotations

import datetime

import pytest

from core.devices.phone import (
    DEFAULT_PHONE_DISPLAY_NAME,
    Phone,
    PhoneDescriptor,
)
from core.devices.stable_key import (
    FirstTierStableKey,
    SecondTierStableKey,
    StableKey,
    compute_phone_stable_key,
)

pytestmark = [pytest.mark.devices]

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

    def test_phone_equality_ignores_connection_id_and_last_communication(
        self,
    ) -> None:
        paired = Phone(id="old-connection", model="OceanPhone", state="device")
        discovered = Phone(id="new-connection", model="OceanPhone", state="device")
        discovered.last_communication = datetime.datetime(2025, 6, 15, 10, 30, 0)

        assert paired == discovered
        assert hash(paired) == hash(discovered)

    def test_phone_equality_ignores_state(self) -> None:
        paired = Phone(id="connection-a", model="OceanPhone", state="device")
        discovered = Phone(id="connection-b", model="OceanPhone", state="offline")

        assert paired == discovered
        assert hash(paired) == hash(discovered)

    def test_phone_equality_returns_not_implemented_for_unrelated_types(self) -> None:
        phone = Phone(id="connection", model="OceanPhone")

        assert phone.__eq__(object()) is NotImplemented
        assert phone != object()

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

    def test_hardware_serial_setter_updates_stable_key(self) -> None:
        phone = Phone(
            id="dev",
            name="Pixel",
            product="prod",
            model="mod",
            state="device",
        )
        phone.hardware_serial = "ABC123DEVICE\n"
        assert phone.hardware_serial == "ABC123DEVICE"
        assert phone.stable_key == "hw:v1:ABC123DEVICE"

    def test_manufacturer_and_model_setters_update_tier_two_stable_key(
        self,
    ) -> None:
        """Without serial, manufacturer + model enrichment produces fp:v1: stable_key."""
        phone = Phone(
            id="dev", name="Pixel", product="ocean", model="m1", state="device"
        )
        assert phone.stable_key == ""
        phone.manufacturer = "FabCo"
        phone.model = "OceanView"
        assert phone.descriptor.manufacturer == "FabCo"
        assert phone.descriptor.model == "OceanView"
        assert phone.stable_key.startswith("fp:v1:")

    def test_model_setter_leaves_tier_one_key_unchanged(self) -> None:
        """After Tier-1 serial, model enrichment does not change hw stable_key."""
        phone = Phone(
            id="dev", name="Pixel", product="ocean", model="m1", state="device"
        )
        phone.hardware_serial = "SERIALX"
        key = phone.stable_key
        phone.model = "OceanView"
        assert phone.descriptor.model == "OceanView"
        assert phone.stable_key == key == "hw:v1:SERIALX"

    def test_os_setter_applies_android_release(self) -> None:
        phone = Phone(id="x", name="n", os="", state="device")
        phone.os = " 15 \n"
        assert phone.descriptor.os == "15"

    def test_shell_device_name_setter_clears_override_and_recomputes_display(
        self,
    ) -> None:
        """Blank ``device_name`` clears shell override; label falls back to list token / model."""
        phone = Phone(
            id="x",
            name="keep-token",
            model="ModX",
            state="device",
        )
        phone.shell_device_name = "  "
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
        phone.manufacturer = "FabCo"
        assert phone.descriptor.name == "FabCo OceanPhone"

    def test_display_name_getprop_overrides_manufacturer_model(self) -> None:
        phone = Phone(id="d", model="X", manufacturer="Fab", state="device")
        assert "Fab" in phone.descriptor.name
        phone.shell_device_name = "Living Room Phone"
        assert phone.descriptor.name == "Living Room Phone"
        assert phone.descriptor.shell_device_name == "Living Room Phone"

    def test_sync_phone_display_name_long_id_suffix(self) -> None:
        pid = "adb-X9ZZ99000012345678-aBc1dE"
        phone = Phone(id=pid, state="device")
        assert phone.descriptor.name == f"{DEFAULT_PHONE_DISPLAY_NAME} (8-aBc1dE)"

    def test_sync_phone_display_name_emulator_id(self) -> None:
        phone = Phone(id="emulator-5554", state="offline")
        assert phone.descriptor.name == "emulator-5554"

    def test_android_api_level_setter(self) -> None:
        phone = Phone(id="x", name="n", state="device")
        phone.android_api_level = 35
        assert phone.descriptor.android_api_level == 35
        phone.android_api_level = None
        assert phone.descriptor.android_api_level == 35

    def test_identity_and_os_setters_ignore_blank_values(self) -> None:
        phone = Phone(
            id="x",
            os="14",
            manufacturer="FabCo",
            model="OceanPhone",
        )

        phone.os = "  "
        phone.manufacturer = "  "
        phone.model = "  "

        assert phone.os == "14"
        assert phone.manufacturer == "FabCo"
        assert phone.model == "OceanPhone"

    def test_descriptor_identity_assignment_synchronizes_stable_key(self) -> None:
        phone = Phone(id="device-1", product="ocean", model="OceanPhone")
        assert phone.stable_key == ""

        phone.descriptor.manufacturer = "FabCo"
        assert phone.stable_key.startswith("fp:v1:")

        phone.descriptor.hardware_serial = "SERIAL-1"
        assert phone.stable_key == "hw:v1:SERIAL-1"

    def test_descriptor_non_identity_assignment_preserves_stable_key(self) -> None:
        phone = Phone(id="device-1", product="ocean", model="OceanPhone")
        phone.descriptor.manufacturer = "FabCo"
        stable_key = phone.stable_key

        phone.descriptor.os = "15"
        phone.descriptor.shell_device_name = "Living Room Phone"
        phone.descriptor.android_api_level = 35

        assert phone.stable_key == stable_key

    def test_descriptor_constructor_preserves_keyless_discovery_state(self) -> None:
        descriptor = PhoneDescriptor(
            product="ocean",
            model="OceanPhone",
            manufacturer="FabCo",
        )

        assert descriptor.stable_key == ""

    def test_direct_persisted_stable_key_assignment_is_preserved(self) -> None:
        phone = Phone(id="device-1", product="ocean", model="OceanPhone")
        persisted_key = "hw:v1:PERSISTED-SERIAL"

        phone.descriptor.stable_key = persisted_key

        assert phone.stable_key == persisted_key

    def test_descriptor_display_inputs_follow_name_precedence(self) -> None:
        phone = Phone(id="device-1", device="adb-token")
        assert phone.name == "adb-token"

        phone.descriptor.product = "ocean"
        assert phone.name == "ocean"

        phone.descriptor.model = "OceanPhone"
        assert phone.name == "OceanPhone"

        phone.descriptor.manufacturer = "FabCo"
        assert phone.name == "FabCo OceanPhone"

        phone.descriptor.shell_device_name = "Living Room Phone"
        assert phone.name == "Living Room Phone"

    def test_descriptor_id_rebinding_refreshes_connection_name(self) -> None:
        phone = Phone(id="adb-X9ZZ99000012345678-aBc1dE")
        assert phone.name == f"{DEFAULT_PHONE_DISPLAY_NAME} (8-aBc1dE)"

        phone.descriptor.id = "emulator-5554"

        assert phone.name == "emulator-5554"

    def test_direct_name_assignment_is_preserved_until_display_input_changes(
        self,
    ) -> None:
        phone = Phone(id="device-1", device="adb-token")
        phone.descriptor.name = "Persisted label"
        phone.descriptor.os = "15"

        assert phone.name == "Persisted label"

        phone.descriptor.device = "fresh-adb-token"

        assert phone.name == "fresh-adb-token"


class TestComputePhoneStableKey:
    """Tests for stable key derivation."""

    def test_tier_one_known_serial(self) -> None:
        key = compute_phone_stable_key(hardware_serial=" SN1 ", product="x", model="y")
        assert isinstance(key, FirstTierStableKey)
        assert key.value == "hw:v1:SN1"
        assert key.is_collision_resistant() is True

    def test_unknown_serial_falls_through(self) -> None:
        """unknown (any case) is not treated as Tier-1."""

        fp = compute_phone_stable_key(
            hardware_serial="unknown",
            product="prod",
            model="mod",
            fingerprint_when_no_serial=True,
        )
        assert isinstance(fp, SecondTierStableKey)
        assert fp.value.startswith("fp:v1:")
        assert fp.is_collision_resistant() is False
        fp2 = compute_phone_stable_key(
            hardware_serial="unknown",
            product="prod",
            model="mod",
            fingerprint_when_no_serial=False,
        )
        assert fp2 is None

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
        assert isinstance(a, SecondTierStableKey)
        assert a == b and a.value.startswith("fp:v1:")

    @pytest.mark.parametrize(
        ("stable_key", "expected_type", "expected_collision_resistance"),
        [
            ("hw:v1:SER-123", FirstTierStableKey, True),
            ("fp:v1:" + "a" * 64, SecondTierStableKey, False),
            ("pc:v1:install:host-token", None, None),
            ("", None, None),
            ("fp:v1:not-a-digest", None, None),
        ],
    )
    def test_parse_persisted_stable_key(
        self,
        stable_key: str,
        expected_type: type[StableKey] | None,
        expected_collision_resistance: bool | None,
    ) -> None:
        parsed = StableKey.from_value(stable_key)
        if expected_type is None:
            assert parsed is None
        else:
            assert isinstance(parsed, expected_type)
            assert parsed.is_collision_resistant() is expected_collision_resistance


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
        assert isinstance(sk_tier_one, FirstTierStableKey)

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
            stable_key=sk_tier_one.value,
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
            stable_key=sk_tier_one.value,
            manufacturer="",
        )
        assert d1 == d2 and hash(d1) == hash(d2)

        d2.id = "adb-2"
        d2.last_communication = fixed_last + datetime.timedelta(seconds=1)
        assert d1 == d2 and hash(d1) == hash(d2)

        d2.state = "offline"
        assert d2 == d1
        assert hash(d2) == hash(d1)

        sk_fingerprint = compute_phone_stable_key(
            hardware_serial=None,
            product="prod",
            model="mod",
            manufacturer="Fab",
            fingerprint_when_no_serial=True,
        )
        assert isinstance(sk_fingerprint, SecondTierStableKey)
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
            stable_key=sk_fingerprint.value,
            manufacturer="Fab",
        )
        assert d3 != d1
