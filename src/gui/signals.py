from PySide6.QtCore import QObject, Signal


class ViewSignals(QObject):
    """Central hub for GUI-originating signals (cross-component wiring)."""

    #### UI Signals ####
    UiConstraintsDisabled = Signal()
    UpdatePaletteSignal = Signal(str)
    LeftPanelsVisibilityRequested = Signal(bool)
    RightPanelsVisibilityRequested = Signal(bool)
    DeviceSelectionPanelVisibilityRequested = Signal(bool)
    LocationPanelVisibilityRequested = Signal(bool)
    HostPanelVisibilityRequested = Signal(bool)
    LogPanelVisibilityRequested = Signal(bool)
    RunHelperAnimationRequested = Signal()

    #### ADB Server Signals ####
    ADBServerStarted = Signal()
    ADBServerStopped = Signal()

    #### Device Signals ####
    AddDeviceRequested = Signal()
    AuthentificationRequested = Signal()
    AuthentificationCancelled = Signal()
    AuthentificationConfirmed = Signal(str, str, str)
    AuthentificationFailed = Signal(str, int, str)
    AuthentificationSucceeded = Signal(str)
    DeviceSelectionSucceeded = Signal(str)
    DeviceSelected = Signal(object)
    DeviceConnectionRequested = Signal(str)
    DeviceConnectionCancelled = Signal()
    RefreshDeviceListRequested = Signal()
    DevicesUpdated = Signal(object)

    #### Host Signals ####
    HostDeviceInformationUpdated = Signal(str, str, str)

    #### Simulation Signals ####
    StartSimulationRequested = Signal()
    StopSimulationRequested = Signal()
    SimulationContextChanged = Signal(str, int)
    SimulationPositionChanged = Signal(float, float)
    SimulationLogFileUpdated = Signal(str, str)


view_signals: ViewSignals = ViewSignals()
