"""
Golden-string tests for ADBCommandParser output shapes.
"""

from __future__ import annotations

import pytest

from core.adb import ADB_COMMAND_PARSERS, ADBCommandParser, AdbCommands
from core.devices import Phone

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


def test_send_notification_post_confirmation() -> None:
    assert (
        ADBCommandParser.SEND_NOTIFICATION.parse(
            "posting:\n  Notification(channel=*** shortcut=null"
        )
        is True
    )
    assert ADBCommandParser.SEND_NOTIFICATION.parse("") is False


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
        AdbCommands.GET_BATTERY_INFOS,
        AdbCommands.DUMPSYS_WINDOW,
        AdbCommands.SEND_NOTIFICATION,
    }
    assert set(ADB_COMMAND_PARSERS.keys()) == expected
    for cmd, parser in ADB_COMMAND_PARSERS.items():
        assert isinstance(cmd, AdbCommands)
        assert isinstance(parser, ADBCommandParser)
