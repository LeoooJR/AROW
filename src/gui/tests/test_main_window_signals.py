"""Signal-forwarding tests for MainWindow view callbacks."""

from __future__ import annotations

from typing import cast

from gui.signals import signals
from gui.window import MainWindow


def test_forward_devices_updated_emits_rebindings_without_info_log(
    qtbot, log_records
) -> None:
    devices = [{"id": "device-1", "name": "Pixel 9"}]
    rebindings = {"old-device-1": "device-1"}

    with qtbot.waitSignal(signals.DEVICE.DevicesUpdated) as blocker:
        MainWindow.forward_devices_updated(
            cast(MainWindow, object()), devices, rebindings
        )

    assert blocker.args == [devices, rebindings]
    assert not [
        record
        for record in log_records
        if record["function"] == "forward_devices_updated"
        and record["level"].name == "INFO"
    ]


def test_forward_devices_updated_defaults_rebindings_to_empty_dict(qtbot) -> None:
    devices = [{"id": "device-1", "name": "Pixel 9"}]

    with qtbot.waitSignal(signals.DEVICE.DevicesUpdated) as blocker:
        MainWindow.forward_devices_updated(cast(MainWindow, object()), devices)

    assert blocker.args == [devices, {}]
