from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    """Central signal hub for app-wide communication."""

    UiConstraintsDisabled = Signal()
    UpdatePaletteSignal = Signal(str)
    LeftPanelsVisibilityRequested = Signal(bool)
    RightPanelsVisibilityRequested = Signal(bool)
    DeviceSelectionPanelVisibilityRequested = Signal(bool)
    LocationPanelVisibilityRequested = Signal(bool)
    HostPanelVisibilityRequested = Signal(bool)
    LogPanelVisibilityRequested = Signal(bool)
    AddDeviceRequested = Signal()
    AuthentificationRequested = Signal()
    AuthentificationCancelled = Signal()
    AuthentificationConfirmed = Signal(str, str, str)
    AuthentificationFailed = Signal(str)
    AuthentificationSucceeded = Signal(str)
    DeviceSelectionSucceeded = Signal(str)
    DeviceSelected = Signal(object)
    DeviceConnectionRequested = Signal(str)
    DeviceConnectionCancelled = Signal()
    RefreshDeviceListRequested = Signal()
    DevicesUpdated = Signal(object)
    HostDeviceInformationUpdated = Signal(str, str, str)
    StartSimulationRequested = Signal()
    StopSimulationRequested = Signal()
    SimulationContextChanged = Signal(str, int)
    SimulationPositionChanged = Signal(float, float)


app_signals: AppSignals = AppSignals()
