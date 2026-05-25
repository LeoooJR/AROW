"""Tests for host identity and ADB bridge card blocks."""

from __future__ import annotations

import pytest

from gui.blocks.card import BridgeStatusCardBlock, IdentityCardBlock
from gui.icons import OperatingSystemIcons
from gui.signals import view_signals

pytestmark = pytest.mark.usefixtures("qapp")


def test_identity_card_seeds_placeholder_values_on_init(qtbot) -> None:
    card = IdentityCardBlock()
    qtbot.addWidget(card)

    assert card.content.host_name_label.text() == card.texts.placeholder_host_name
    assert card.content.host_summary_label.text() == card.texts.placeholder_summary
    assert (
        card.content.ip_address_row.value_label.text()
        == card.texts.placeholder_ip_address
    )
    assert (
        card.content.platform_row.value_label.text() == card.texts.placeholder_platform
    )
    assert card.indicator.property("indicator-state") == "valid"


def test_identity_card_setters_update_values_and_preserve_omitted_fields(qtbot) -> None:
    card = IdentityCardBlock()
    qtbot.addWidget(card)
    original_summary = card.content.host_summary_label.text()

    card.set_host_values(host_name="Build Host", ip_address="10.0.0.5")
    card.set_host_values(platform="linux")

    assert card.content.host_name_label.text() == "Build Host"
    assert card.content.host_summary_label.text() == original_summary
    assert card.content.ip_address_row.value_label.text() == "10.0.0.5"
    assert card.content.platform_row.value_label.text() == "linux"


def test_identity_card_debug_signal_restores_placeholder_values(qtbot) -> None:
    card = IdentityCardBlock()
    qtbot.addWidget(card)
    card.set_host_values(
        host_name="Temporary",
        summary="Temporary summary",
        ip_address="127.0.0.1",
        platform="test",
        os_icon=OperatingSystemIcons.LINUX,
        identity_state="error",
    )

    view_signals.UiConstraintsDisabled.emit()
    qtbot.wait(0)

    assert card.content.host_name_label.text() == card.texts.placeholder_host_name
    assert card.content.host_summary_label.text() == card.texts.placeholder_summary
    assert card.indicator.property("indicator-state") == "valid"


def test_identity_card_can_display_error_state(qtbot) -> None:
    card = IdentityCardBlock()
    qtbot.addWidget(card)

    card.set_host_values(identity_state="error")

    assert card.indicator.property("indicator-state") == "error"


def test_bridge_status_card_seeds_placeholder_values_on_init(qtbot) -> None:
    card = BridgeStatusCardBlock()
    qtbot.addWidget(card)

    assert (
        card.content.status_row.value_label.text()
        == card.texts.placeholder_server_state_text.capitalize()
    )
    assert (
        card.content.version_row.value_label.text()
        == card.texts.placeholder_adb_version
    )
    assert card.content.daemon_row.value_label.text() == card.texts.placeholder_daemon
    assert (
        card.content.devices_row.value_label.text()
        == card.texts.placeholder_connected_devices
    )
    assert card.content.helper_note.text() == card.texts.placeholder_helper_note
    assert card.indicator.property("indicator-state") == "valid"


def test_bridge_status_card_setters_update_values_and_preserve_omitted_fields(
    qtbot,
) -> None:
    card = BridgeStatusCardBlock()
    qtbot.addWidget(card)
    original_helper = card.content.helper_note.text()

    card.set_adb_values(server_state="stopped", adb_version="1.0.41")
    card.set_adb_values(daemon="tcp:5037")

    assert card.content.status_row.value_label.text() == "Stopped"
    assert card.content.status_row.value_label.property("adb-server-state") == "stopped"
    assert card.content.version_row.value_label.text() == "1.0.41"
    assert card.content.daemon_row.value_label.text() == "tcp:5037"
    assert card.content.helper_note.text() == original_helper


def test_bridge_status_card_debug_signal_restores_placeholder_values(qtbot) -> None:
    card = BridgeStatusCardBlock()
    qtbot.addWidget(card)
    card.set_adb_values(
        server_state="error",
        adb_version="broken",
        daemon="missing",
        connected_devices="0",
        helper_note="Temporary",
        indicator_state="error",
    )

    view_signals.UiConstraintsDisabled.emit()
    qtbot.wait(0)

    assert (
        card.content.version_row.value_label.text()
        == card.texts.placeholder_adb_version
    )
    assert card.content.helper_note.text() == card.texts.placeholder_helper_note
    assert card.indicator.property("indicator-state") == "valid"


def test_bridge_status_card_can_display_error_state(qtbot) -> None:
    card = BridgeStatusCardBlock()
    qtbot.addWidget(card)

    card.set_adb_values(server_state="error", indicator_state="error")

    assert card.content.status_row.value_label.text() == "Error"
    assert card.content.status_row.value_label.property("adb-server-state") == "error"
    assert card.indicator.property("indicator-state") == "error"


def test_bridge_status_card_adb_server_started(qtbot) -> None:
    card = BridgeStatusCardBlock()
    qtbot.addWidget(card)

    view_signals.ADBServerStarted.emit()
    qtbot.wait(0)

    assert card.content.status_row.value_label.text() == "Running"
    assert card.content.status_row.value_label.property("adb-server-state") == "running"
    assert card.indicator.property("indicator-state") == "valid"


def test_bridge_status_card_adb_server_stopped(qtbot) -> None:
    card = BridgeStatusCardBlock()
    qtbot.addWidget(card)

    view_signals.ADBServerStopped.emit()
    qtbot.wait(0)

    assert card.content.status_row.value_label.text() == "Stopped"
    assert card.content.status_row.value_label.property("adb-server-state") == "stopped"
    assert card.indicator.property("indicator-state") == "error"


def test_identity_card_host_device_information_updated(qtbot) -> None:
    card = IdentityCardBlock()
    qtbot.addWidget(card)

    view_signals.HostDeviceInformationUpdated.emit("Build Host", "linux", "192.168.1.1")
    qtbot.wait(0)

    assert card.content.host_name_label.text() == "Build Host"
    assert card.content.ip_address_row.value_label.text() == "192.168.1.1"
    assert card.content.platform_row.value_label.text() == "linux"
    assert card.indicator.property("indicator-state") == "valid"
