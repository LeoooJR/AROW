"""
Tests for core device model modules.
"""

from __future__ import annotations

import datetime
from dataclasses import FrozenInstanceError, replace

import pytest

from core.devices.computer import ComputerDescriptor
from core.devices.phone import (
    DEFAULT_PHONE_DISPLAY_NAME,
    Phone,
    PhoneDescriptor,
    PhoneRepository,
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

    def test_phone_descriptor_is_read_only_and_type_safe(self) -> None:
        phone = Phone(id="id", name="Pixel", state="online")

        with pytest.raises(AttributeError):
            phone.descriptor = ComputerDescriptor()  # type: ignore[misc,assignment]
        with pytest.raises(FrozenInstanceError):
            phone.descriptor.state = "offline"  # type: ignore[misc]

    def test_phone_str_repr(self) -> None:
        """Phone __str__ and __repr__ are defined and non-empty."""
        phone = Phone(id="x", name="n", os="o", ip="i", port=1, state="s")
        assert "n" in str(phone)
        assert "Phone" in repr(phone)
        assert "x" in repr(phone)

    def test_phone_descriptor_str_uses_human_friendly_labels(self) -> None:
        phone = Phone(
            id="192.168.1.20:5555",
            os="15",
            model="Pixel 8",
            state="device",
            android_api_level=35,
        )

        assert str(phone.descriptor) == (
            "Pixel 8 | Android 15 (API 35) | "
            "Wi-Fi: 192.168.1.20:5555 | State: device"
        )

    def test_phone_descriptor_repr_quotes_string_values(self) -> None:
        descriptor = Phone(id="device-1", model="Pixel 8").descriptor

        assert "id='device-1'" in repr(descriptor)
        assert "model='Pixel 8'" in repr(descriptor)

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            ({"id": "serial-123"}, "usb"),
            ({"id": "emulator-5554"}, "usb"),
            ({"id": "192.168.1.20:5555"}, "wifi"),
            ({"id": "adb-serial._adb-tls-connect._tcp"}, "wifi"),
            ({"id": "adb-guid", "ip": "192.168.1.20", "port": 37777}, "wifi"),
        ],
    )
    def test_phone_infers_connectivity_type(
        self, kwargs: dict[str, object], expected: str
    ) -> None:
        phone = Phone(**kwargs)  # type: ignore[arg-type]

        assert phone.connectivity_type == expected

    def test_distinct_phones_use_object_identity(self) -> None:
        usb = Phone(id="device-1", model="Pixel", connectivity_type="usb")
        same_metadata = Phone(id="device-1", model="Pixel", connectivity_type="usb")

        assert usb == usb
        assert usb != same_metadata

    def test_phone_is_unhashable_before_and_after_update(self) -> None:
        phone = Phone(id="device-1", model="Pixel")

        with pytest.raises(TypeError):
            hash(phone)

        phone.model = "Pixel Pro"

        with pytest.raises(TypeError):
            hash(phone)

    def test_phone_connectivity_type_round_trips_and_old_payload_infers(self) -> None:
        phone = Phone(
            id="adb-guid",
            ip="192.168.1.20",
            port=37777,
            connectivity_type="wifi",
        )
        payload = phone.serialize()

        assert payload["connectivity_type"] == "wifi"
        assert Phone.deserialize(payload).connectivity_type == "wifi"
        payload.pop("connectivity_type")
        assert Phone.deserialize(payload).connectivity_type == "wifi"

    def test_phone_has_no_generic_update_state_escape_hatch(self) -> None:
        phone = Phone(id="a")

        assert not hasattr(phone, "update_state")

    def test_phone_is_not_equal_to_unrelated_types(self) -> None:
        phone = Phone(id="connection", model="OceanPhone")

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

    def test_apply_shell_enrichment_updates_one_snapshot_atomically(self) -> None:
        phone = Phone(id="device-1", product="ocean", model="List model", os="14")
        original = phone.descriptor

        phone.apply_shell_enrichment(
            manufacturer=" FabCo ",
            model="OceanPhone",
            shell_device_name=" Field handset ",
            os="15",
            android_api_level=35,
            hardware_serial=" SERIAL-1 ",
        )

        assert phone.descriptor is not original
        assert phone.manufacturer == "FabCo"
        assert phone.model == "OceanPhone"
        assert phone.shell_device_name == "Field handset"
        assert phone.name == "Field handset"
        assert phone.os == "15"
        assert phone.android_api_level == 35
        assert phone.hardware_serial == "SERIAL-1"
        assert phone.stable_key == "hw:v1:SERIAL-1"

    def test_apply_shell_enrichment_preserves_non_empty_values_on_blanks(self) -> None:
        phone = Phone(
            id="device-1",
            manufacturer="FabCo",
            model="OceanPhone",
            os="14",
            hardware_serial="SERIAL-1",
            android_api_level=34,
        )

        phone.apply_shell_enrichment(
            manufacturer=" ",
            model="",
            shell_device_name=" ",
            os="",
            android_api_level=None,
            hardware_serial="unknown",
        )

        assert phone.manufacturer == "FabCo"
        assert phone.model == "OceanPhone"
        assert phone.shell_device_name == ""
        assert phone.os == "14"
        assert phone.android_api_level == 34
        assert phone.hardware_serial == "SERIAL-1"
        assert phone.stable_key == "hw:v1:SERIAL-1"

    def test_descriptor_constructor_preserves_keyless_discovery_state(self) -> None:
        descriptor = PhoneDescriptor(
            product="ocean",
            model="OceanPhone",
            manufacturer="FabCo",
        )

        assert descriptor.stable_key == ""

    def test_deserialize_preserves_persisted_stable_key(self) -> None:
        persisted_key = "hw:v1:PERSISTED-SERIAL"

        phone = Phone.deserialize(
            {
                "id": "device-1",
                "name": "OceanPhone",
                "stable_key": persisted_key,
            }
        )

        assert phone.stable_key == persisted_key

    def test_apply_discovery_replaces_snapshot_and_refreshes_connection_name(
        self,
    ) -> None:
        phone = Phone(id="adb-X9ZZ99000012345678-aBc1dE")
        assert phone.name == f"{DEFAULT_PHONE_DISPLAY_NAME} (8-aBc1dE)"
        original = phone.descriptor
        discovered = Phone(id="emulator-5554", state="device", model="Pixel")

        phone.apply_discovery(discovered)

        assert phone.descriptor is discovered.descriptor
        assert phone.descriptor is not original
        assert phone.id == "emulator-5554"
        assert phone.name == "Pixel"


class TestComputePhoneStableKey:
    """Tests for stable key derivation."""

    def test_tier_one_known_serial(self) -> None:
        key = compute_phone_stable_key(hardware_serial=" SN1 ", product="x", model="y")
        assert isinstance(key, FirstTierStableKey)
        assert key.value == "hw:v1:SN1"
        assert key.is_collision_resistant() is True

    def test_tier_one_keys_are_immutable_hashable_identity_values(self) -> None:
        first = FirstTierStableKey("SERIAL-1")
        second = FirstTierStableKey("SERIAL-1")

        assert first == second
        assert hash(first) == hash(second)
        assert {first: "phone"}[second] == "phone"
        with pytest.raises(FrozenInstanceError):
            first.hardware_serial = "SERIAL-2"  # type: ignore[misc]

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


class TestPhoneDescriptorEquality:
    """PhoneDescriptor supports state comparison without mutable hashing."""

    def test_stable_key_participates_in_equality(self) -> None:
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
        assert d1 == d2
        with pytest.raises(TypeError):
            hash(d1)

        transient_update = replace(
            d2,
            id="adb-2",
            state="offline",
            last_communication=fixed_last + datetime.timedelta(seconds=1),
        )
        assert d1 == transient_update
        with pytest.raises(FrozenInstanceError):
            d2.state = "offline"  # type: ignore[misc]
        with pytest.raises(TypeError):
            hash(transient_update)

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


class TestPhoneRepository:
    """Phone repository indexes used by device-domain workflows."""

    def test_index_by_stable_identity_keeps_first_tier_one_phone(
        self,
    ) -> None:
        first = Phone(id="device-1", hardware_serial="SERIAL-1")
        duplicate = Phone(id="device-2", hardware_serial="SERIAL-1")
        without_stable_key = Phone(id="device-3")
        fingerprint = Phone(id="device-4", model="Pixel")
        fingerprint.manufacturer = "Google"
        repository = PhoneRepository()
        for phone in (first, duplicate, without_stable_key, fingerprint):
            repository.add(phone)

        indexed = repository.index_by_stable_identity()

        stable_identity = FirstTierStableKey("SERIAL-1")
        assert indexed == {stable_identity: first}
        assert indexed[stable_identity] is first
