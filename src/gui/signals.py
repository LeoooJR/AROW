from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    """Central signal hub for app-wide communication."""

    @dataclass(frozen=True)
    class Text:
        pass

    @dataclass
    class UI:
        pass

    def __init__(self, parent=None):
        super().__init__(parent)
        self.texts = AppSignals.Text()
        self.ui = AppSignals.UI()

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
