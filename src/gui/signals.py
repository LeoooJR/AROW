from PySide6.QtCore import QObject, Signal


class ViewSignals(QObject):
    """Central hub for GUI-originating signals (cross-component wiring)."""

    #### UI Signals ####
    UiConstraintsDisabled = Signal()
    UpdatePaletteSignal = Signal(str)
    LeftPanelsVisibilityRequested = Signal(bool)
    RightPanelsVisibilityRequested = Signal(bool)
    DeviceSelectionPanelVisibilityRequested = Signal(bool)
    ExtendDeviceSelectionPanelRequested = Signal()
    ShortenDeviceSelectionPanelRequested = Signal()
    LocationPanelVisibilityRequested = Signal(bool)
    HostPanelVisibilityRequested = Signal(bool)
    LogPanelVisibilityRequested = Signal(bool)
    RunHelperAnimationRequested = Signal()
    MapTabActivated = Signal()

    #### ADB Server Signals ####
    ADBServerStarted = Signal()
    ADBServerStopped = Signal()

    #### Device Signals ####
    AddDeviceRequested = Signal()
    AuthentificationRequested = Signal()
    AuthentificationCancelled = Signal()
    AuthentificationConfirmed = Signal(str, str, str)
    AuthentificationFailed = Signal(str, int, str)
    AuthentificationSucceeded = Signal(dict)
    DeviceSelectionRequested = Signal(str, str)
    DeviceSelectionCancelled = Signal()
    DeviceSelectionConfirmed = Signal(str, str)
    DeviceSelectionSucceeded = Signal(dict)
    DeviceSelectionFailed = Signal(dict)
    RefreshDeviceListRequested = Signal()
    DevicesUpdated = Signal(object)
    RemoveDeviceRequested = Signal(str)

    #### Host Signals ####
    HostDeviceInformationUpdated = Signal(str, str, str)

    #### Simulation Signals ####
    StartSimulationRequested = Signal()
    StopSimulationRequested = Signal()
    SimulationContextChanged = Signal(str, int)
    SimulationPositionChanged = Signal(float, float)
    SimulationLogFileUpdateRequested = Signal(str)
    SimulationLogFileUpdated = Signal(str, str)


view_signals: ViewSignals = ViewSignals()
