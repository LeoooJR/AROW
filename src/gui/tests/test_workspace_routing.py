"""Integration tests for signal-driven workspace routing."""

from gui.layouts import WorkspaceLayout
from gui.routing import PageRoute
from gui.signals import signals


def test_target_selection_routes_to_map_and_emits_activation(qtbot) -> None:
    workspace = WorkspaceLayout()
    qtbot.addWidget(workspace)

    with qtbot.waitSignal(signals.UI.MapTabActivated):
        signals.UI.TargetSelectionRequested.emit()

    assert workspace.ui.router.current_route is PageRoute.MAP


def test_device_selection_and_removal_route_by_name(qtbot) -> None:
    workspace = WorkspaceLayout()
    qtbot.addWidget(workspace)

    signals.DEVICE.DeviceSelectionSucceeded.emit("simulation-1", "device-1", "Pixel")

    assert workspace.ui.router.current_route is PageRoute.MAP
    assert workspace.ui.progress_bar.value() == 1

    signals.DEVICE.RemoveActiveDeviceSucceeded.emit("device-1")

    assert workspace.ui.router.current_route is PageRoute.WELCOME
    assert workspace.ui.progress_bar.value() == 0


def test_location_validation_advances_progress_without_changing_route(qtbot) -> None:
    workspace = WorkspaceLayout()
    qtbot.addWidget(workspace)

    signals.SIMULATION.SimulationLocationValidated.emit(
        "simulation-1", 42, "100000", 1, 48.8, 2.3, "PK 42"
    )

    assert workspace.ui.router.current_route is PageRoute.WELCOME
    assert workspace.ui.progress_bar.value() == 2
