"""
Central hub for GUI-originating signals (cross-component wiring).

Signals are grouped into logical categories for easy access and maintenance,
mirroring the organization of ``gui.settings``.
"""

from PySide6.QtCore import QObject, Signal


class UISignals(QObject):
    """UI chrome, panels, palette, and map-tab activation signals."""

    UiConstraintsDisabled = Signal()
    UpdatePaletteSignal = Signal(str)
    LeftPanelsVisibilityRequested = Signal(bool)
    RightPanelsVisibilityRequested = Signal(bool)
    DeviceSelectionPanelVisibilityRequested = Signal(bool)
    ExtendDeviceSelectionPanelRequested = Signal()
    ShortenDeviceSelectionPanelRequested = Signal()
    LocationPanelVisibilityRequested = Signal(bool)
    TargetSelectionRequested = Signal()
    HostPanelVisibilityRequested = Signal(bool)
    LogPanelVisibilityRequested = Signal(bool)
    RunHelperAnimationRequested = Signal()
    MapTabActivated = Signal()


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
    DeviceSelectionSucceeded = Signal(str, str)
    DeviceSelectionFailed = Signal(str, str)
    RefreshDeviceListRequested = Signal()
    DevicesUpdated = Signal(object)
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
    SimulationContextChanged = Signal(str, int)
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
