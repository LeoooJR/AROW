"""
Central hub for GUI-originating signals (cross-component wiring).

Signals are grouped into logical categories for easy access and maintenance,
mirroring the organization of ``gui.settings``.

When adding a new GUI signal:
1. Add the ``Signal(...)`` on the appropriate category class (``UISignals``, ``DeviceSignals``,
   etc.) with typed arguments matching the payload contract.
2. Emit from the view or block that originates the user intent; connect handlers in the
   controller (``src/controller/domains/``) or other GUI slots as needed.
3. Keep domain events that belong to the core layer in ``src/core/signals.py`` instead; adapt
   them in the controller rather than duplicating core payloads on the GUI bus.
4. Add or extend GUI integration tests when the signal drives navigation, panel state, or async
   job submission.
"""

from PySide6.QtCore import QObject, Signal


class UISignals(QObject):
    """UI chrome, panels, palette, and map-tab activation signals."""

    UiConstraintsDisabled = Signal()
    UpdatePaletteSignal = Signal(str)
    DisplayLeftPanelsRequested = Signal()
    HideLeftPanelsRequested = Signal()
    DisplayRightPanelsRequested = Signal()
    HideRightPanelsRequested = Signal()
    DeviceSelectionPanelVisibilityRequested = Signal(bool)
    ExtendDeviceSelectionPanelRequested = Signal()
    ShortenDeviceSelectionPanelRequested = Signal()
    LocationPanelVisibilityRequested = Signal(bool)
    TargetSelectionRequested = Signal()
    HostPanelVisibilityRequested = Signal(bool)
    LogPanelVisibilityRequested = Signal(bool)
    RunHelperAnimationRequested = Signal()
    MapTabActivated = Signal()
    RenderMapRequested = Signal(str)
    MapRendered = Signal(str, object)  # simulation_id, html_path
    MapRenderFailed = Signal(str, str)  # simulation_id, reason
    MapMarkerClicked = Signal(
        str, str, float, float
    )  # marker_id, line, latitude, longitude


class ADBServerSignals(QObject):
    """ADB server lifecycle signals."""

    ADBServerStarted = Signal()
    ADBServerStopped = Signal()


class DeviceSignals(QObject):
    """Device pairing, selection, refresh, and removal signals."""

    AddDeviceRequested = Signal()
    AuthentificationRequested = Signal()
    AuthentificationCancelled = Signal()
    AuthentificationConfirmed = Signal(str, str, str)
    AuthentificationFailed = Signal(str, int, str)
    AuthentificationSucceeded = Signal(dict)
    DeviceSelectionRequested = Signal(str, str)
    DeviceSelectionCancelled = Signal()
    DeviceSelectionConfirmed = Signal(str, str)
    DeviceSelectionSucceeded = Signal(str, str, str)
    DeviceSelectionFailed = Signal(str, str)
    RefreshDeviceListRequested = Signal()
    DevicesUpdated = Signal(object, object)
    RemoveDeviceRequested = Signal(str)
    RemoveDeviceSucceeded = Signal(str)
    RemoveDeviceFailed = Signal(str)
    RemoveActiveDeviceSucceeded = Signal(str)


class HostSignals(QObject):
    """Host identity and metadata signals."""

    HostDeviceInformationUpdated = Signal(str, str, str)


class ActivityLogSignals(QObject):
    """Activity log file update signals."""

    ActivityLogFileUpdateRequested = Signal(str)
    ActivityLogFileUpdated = Signal(str)


class SimulationSignals(QObject):
    """Simulation start/stop and position/context signals."""

    StartSimulationRequested = Signal()
    StopSimulationRequested = Signal()
    SimulationDeleted = Signal(str)
    SimulationContextChanged = Signal(str, int)
    SimulationLocationRequested = Signal(
        str, str, str, float, float
    )  # simulation_id, marker_id, line, latitude, longitude
    SimulationLocationValidated = Signal(str, str, float, float, object)
    # simulation_id, marker_id, lat, lon, label (str | None)
    SimulationLocationFailed = Signal(str, str, str)
    # simulation_id, marker_id, reason
    SimulationPositionChanged = Signal(float, float)


class Signals(QObject):
    """
    Centralized signal container for all GUI-originating cross-component wiring.
    Access signals through category attributes for consistency.
    """

    def __init__(self) -> None:
        super().__init__()
        self.UI = UISignals(self)
        self.ADB_SERVER = ADBServerSignals(self)
        self.DEVICE = DeviceSignals(self)
        self.HOST = HostSignals(self)
        self.ACTIVITY_LOG = ActivityLogSignals(self)
        self.SIMULATION = SimulationSignals(self)


signals: Signals = Signals()
