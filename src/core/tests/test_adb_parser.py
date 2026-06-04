"""
Unit tests for ADB stdout/stderr parsing (no real adb binary).
"""

from __future__ import annotations

import pytest

from core.adb import ADB_COMMAND_PARSERS, ADBCommandParser, AdbCommands
from core.devices import DEFAULT_PHONE_DISPLAY_NAME, Phone

pytestmark = [pytest.mark.adb_parser]

# Verbatim excerpts from adb-commands-output at repo root.

OUTPUT_DEVICES = """List of devices attached
adb-AYLVBB5220900344-bReb3a._adb-tls-connect._tcp device product:ALT-NX1EEA model:ALT_NX1 device:HNALT-Q1 transport_id:1
"""

OUTPUT_BATTERY = """Current Battery Service state:
  AC powered: false
  USB powered: false
  Wireless powered: false
  Dock powered: false
  Max charging current: 0
  Max charging voltage: 0
  Charge counter: 2848000
  status: 3
  health: 2
  present: true
  level: 54
  scale: 100
  voltage: 3906
  temperature: 220
  technology: Li-ion
  Charging state: 0
  Charging policy: 0
"""

WINDOW_SNIPPET = """
      screenState=SCREEN_STATE_OFF
WINDOW MANAGER ANIMATOR STATE (dumpsys window animator)
    Display{#0 state=OFF size=1080x2412 ROTATION_0}:
  DisplayPolicy
    mAwake=false mScreenOnEarly=false mScreenOnFully=false
  mCurrentFocus=Window{bdf3658 u0 NotificationShade}
  mFocusedApp=ActivityRecord{3e3682b u0 com.android.settings/com.hihonor.settingslib.SubSettings t1019}
"""


def test_get_devices_parser_returns_phone() -> None:
    phones = ADBCommandParser.GET_DEVICES.parse(OUTPUT_DEVICES)
    assert len(phones) == 1
    p = phones[0]
    assert isinstance(p, Phone)
    assert p.descriptor.id == "adb-AYLVBB5220900344-bReb3a._adb-tls-connect._tcp"
    assert p.descriptor.state == "device"
    assert "ALT_NX1" in p.descriptor.model
    assert p.descriptor.name == "ALT_NX1"
    assert p.descriptor.device == "HNALT-Q1"


def test_parse_devices_line_success() -> None:
    """`_parse_devices` (GET_DEVICES parser) maps a six-token ``devices -l`` row to ``Phone``."""
    blob = """List of devices attached
abc123 device product:model model:pixel device:Pixel transport_id:1
"""
    phones = ADBCommandParser.GET_DEVICES.parse(blob)
    assert len(phones) == 1
    p = phones[0]
    assert isinstance(p, Phone)
    assert p.descriptor.id == "abc123"
    assert p.descriptor.name == "pixel"
    assert p.descriptor.product == "model"
    assert p.descriptor.model == "pixel"
    assert p.descriptor.device == "Pixel"
    assert p.descriptor.state == "device"
    assert p.descriptor.transport_id == "1"
    assert p.stable_key == ""


def test_parse_devices_emulator_line() -> None:
    """Offline emulator row uses the same six-token positional mapping."""
    blob = """List of devices attached
emulator-5554 offline product:sdk model:sdk_gphone device:emulator transport_id:9
"""
    phones = ADBCommandParser.GET_DEVICES.parse(blob)
    assert len(phones) == 1
    p = phones[0]
    assert isinstance(p, Phone)
    assert p.descriptor.id == "emulator-5554"
    assert p.descriptor.name == "sdk_gphone"
    assert p.descriptor.product == "sdk"
    assert p.descriptor.model == "sdk_gphone"
    assert p.descriptor.device == "emulator"
    assert p.descriptor.state == "offline"
    assert p.descriptor.transport_id == "9"


def test_parse_devices_skips_short_or_malformed_lines() -> None:
    """Lines with fewer than six whitespace-separated tokens are skipped (no exception)."""
    blob = """List of devices attached
id name os
emulator-5554 offline product:sdk model:sdk_gphone device:emulator transport_id:9
"""
    phones = ADBCommandParser.GET_DEVICES.parse(blob)
    assert len(phones) == 1
    p = phones[0]
    assert isinstance(p, Phone)
    assert p.descriptor.id == "emulator-5554"


def test_battery_parser_keys_and_concatenated_log() -> None:
    d = ADBCommandParser.GET_BATTERY_INFOS.parse(OUTPUT_BATTERY)
    assert d["level"] == 54
    assert d["scale"] == 100
    assert d["ac_powered"] is False
    assert d["usb_powered"] is False
    assert d["technology"] == "Li-ion"


def test_window_summary_from_dumpsys_window() -> None:
    summary = ADBCommandParser.DUMPSYS_WINDOW.parse(WINDOW_SNIPPET)
    assert summary["m_awake"] is False
    assert summary["m_screen_on_fully"] is False
    assert summary["screen_state"] == "SCREEN_STATE_OFF"
    assert summary["display_size"] == "1080x2412"
    assert summary["m_current_focus"] is not None
    assert "NotificationShade" in summary["m_current_focus"]
    assert summary["m_focused_app"] is not None
    assert "com.android.settings" in summary["m_focused_app"]


def test_scalar_parsers_match_capture_file() -> None:
    assert ADBCommandParser.GET_ANDROID_VERSION.parse("15\n") == "15"
    assert ADBCommandParser.GET_MANUFACTURER.parse("HONOR\n") == "HONOR"
    assert ADBCommandParser.GET_PRODUCT_MODEL.parse("ALT-NX1") == "ALT-NX1"
    assert ADBCommandParser.GET_SDK_VERSION.parse("35") == 35
    assert ADBCommandParser.GET_LOCATION_MODE.parse("3") == 3
    assert ADBCommandParser.GET_DEVICE_NAME.parse("") == ""
    assert (
        ADBCommandParser.GET_SERIAL_NO.parse("AYLVBB5220900344\n") == "AYLVBB5220900344"
    )


def test_optional_int_empty() -> None:
    assert ADBCommandParser.GET_SDK_VERSION.parse("") is None
    assert ADBCommandParser.GET_SDK_VERSION.parse("   \n") is None


def test_shell_enrichment_properties_parser() -> None:
    parsed = ADBCommandParser.GET_SHELL_ENRICHMENT_PROPERTIES.parse(
        "\n".join(
            [
                "manufacturer=Google",
                "model=Pixel 8",
                "device_name=Operator phone",
                "android_release=15",
                "sdk=35",
                "ro_serialno=ABC123",
                "ignored=value",
            ]
        )
    )
    assert parsed == {
        "manufacturer": "Google",
        "model": "Pixel 8",
        "device_name": "Operator phone",
        "android_release": "15",
        "sdk": 35,
        "ro_serialno": "ABC123",
    }


def test_send_notification_post_confirmation() -> None:
    assert (
        ADBCommandParser.SEND_NOTIFICATION.parse(
            "posting:\n  Notification(channel=*** shortcut=null"
        )
        is True
    )
    assert ADBCommandParser.SEND_NOTIFICATION.parse("") is False


def test_mdns_check_success_marker() -> None:
    assert (
        ADBCommandParser.MDNS_CHECK.parse(
            "mdns daemon version [Openscreen discovery 0.0.0]\n"
        )
        is True
    )


@pytest.mark.parametrize("output", ["", "mdns unavailable\n", "daemon not running\n"])
def test_mdns_check_unknown_or_failure_output(output: str) -> None:
    assert ADBCommandParser.MDNS_CHECK.parse(output) is False


# --- `adb pair` (PAIR parser): shape matches tool output; literals are test fixtures only. ---


def test_parse_pair_success_builds_phone() -> None:
    out = (
        "Successfully paired to 10.0.0.42:37125 " "[guid=adb-X9ZZ99000012345678-aBc1dE]"
    )
    phone = ADBCommandParser.PAIR.parse(out)
    assert phone is not None
    assert phone.descriptor.id == "adb-X9ZZ99000012345678-aBc1dE"
    assert phone.descriptor.name == f"{DEFAULT_PHONE_DISPLAY_NAME} (8-aBc1dE)"
    assert phone.descriptor.ip == "10.0.0.42"
    assert phone.descriptor.port == 37125
    assert phone.descriptor.state == "device"


@pytest.mark.parametrize(
    "line",
    [
        # Case-insensitive fixed phrase (regex uses IGNORECASE).
        "successfully paired to 192.168.88.1:40000 [guid=adb-AA11bb22CC]",
        "SUCCESSFULLY PAIRED TO 192.168.88.1:40000 [guid=adb-AA11bb22CC]",
    ],
)
def test_parse_pair_case_insensitive_fixed_phrase(line: str) -> None:
    phone = ADBCommandParser.PAIR.parse(line)
    assert phone is not None
    assert phone.descriptor.id == "adb-AA11bb22CC"
    assert phone.descriptor.port == 40000


def test_parse_pair_port_boundaries() -> None:
    low = ADBCommandParser.PAIR.parse(
        "Successfully paired to 10.0.0.1:1 [guid=adb-low]"
    )
    assert low is not None and low.descriptor.port == 1
    high = ADBCommandParser.PAIR.parse(
        "Successfully paired to 10.0.0.1:65535 [guid=adb-high]"
    )
    assert high is not None and high.descriptor.port == 65535


def test_parse_pair_picks_first_matching_line() -> None:
    """Earlier lines win; used when logs contain multiple candidate lines."""
    blob = (
        "Successfully paired to 10.1.1.1:11111 [guid=adb-first]\n"
        "Successfully paired to 10.2.2.2:22222 [guid=adb-second]\n"
    )
    phone = ADBCommandParser.PAIR.parse(blob)
    assert phone is not None
    assert phone.descriptor.id == "adb-first"
    assert phone.descriptor.ip == "10.1.1.1"
    assert phone.descriptor.port == 11111


def test_parse_pair_finds_line_in_mixed_blob() -> None:
    """Typical host/notify lines plus success (as in captured adb or pair() concat)."""
    blob = (
        "* daemon not running; starting now at tcp:5037\n"
        "Successfully paired to 172.16.254.9:41008 "
        "[guid=adb-QQ77aa000099887766-ZzYy9x]\n"
        "OK\n"
    )
    phone = ADBCommandParser.PAIR.parse(blob)
    assert phone is not None
    assert phone.descriptor.id == "adb-QQ77aa000099887766-ZzYy9x"
    assert phone.descriptor.ip == "172.16.254.9"
    assert phone.descriptor.port == 41008


def test_parse_pair_merged_stdout_stderr_shape() -> None:
    """Same string shape as ``AdbClient.pair``: newline-join streams then strip."""
    stdout = "adb: protocol message\n"
    stderr = "Successfully paired to 203.0.113.7:49152 [guid=adb-mergeStdStreams01]\n"
    combined = f"{stdout}\n{stderr}".strip()
    phone = ADBCommandParser.PAIR.parse(combined)
    assert phone is not None
    assert phone.descriptor.id == "adb-mergeStdStreams01"
    assert phone.descriptor.ip == "203.0.113.7"
    assert phone.descriptor.port == 49152


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "   \n\t  ",
        "Failed: wrong pairing code",
        # No colon in host:port token — IPv4 parser requires a port delimiter.
        "Successfully paired to singlehost [guid=adb-x]",
        "Successfully paired to 10.0.0.1:notaport [guid=adb-badport]",
        "Successfully paired to 10.0.0.1:0 [guid=adb-port0]",
        "Successfully paired to 10.0.0.1:65536 [guid=adb-portmax]",
        # Empty guid payload.
        "Successfully paired to 10.0.0.1:5555 [guid=]",
        # Wrong prose — no match.
        "Paired OK to 10.0.0.1:5555 [guid=adb-nope]",
    ],
)
def test_parse_pair_invalid_returns_none(invalid: str) -> None:
    assert ADBCommandParser.PAIR.parse(invalid) is None


def test_adb_command_parsers_registry() -> None:
    expected = {
        AdbCommands.GET_DEVICES,
        AdbCommands.GET_ANDROID_VERSION,
        AdbCommands.GET_MANUFACTURER,
        AdbCommands.GET_DEVICE_NAME,
        AdbCommands.GET_PRODUCT_MODEL,
        AdbCommands.GET_SDK_VERSION,
        AdbCommands.GET_LOCATION_MODE,
        AdbCommands.GET_SERIAL_NO,
        AdbCommands.GET_SHELL_ENRICHMENT_PROPERTIES,
        AdbCommands.GET_BATTERY_INFOS,
        AdbCommands.DUMPSYS_WINDOW,
        AdbCommands.SEND_NOTIFICATION,
        AdbCommands.MDNS_CHECK,
    }
    assert set(ADB_COMMAND_PARSERS.keys()) == expected
    for cmd, parser in ADB_COMMAND_PARSERS.items():
        assert isinstance(cmd, AdbCommands)
        assert isinstance(parser, ADBCommandParser)
