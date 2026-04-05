from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QTimer, Signal


class ActivityTracker(QObject):
    """Track user activity and idle state."""

    became_active = Signal()  # Emitted when user becomes active
    became_idle = Signal()  # Emitted when user becomes idle

    def __init__(
        self, parent=None, idle_ms: int = 30_000, track_mouse_move: bool = False
    ):
        super().__init__(parent)
        self.idle_ms = idle_ms  # Idle timeout in milliseconds
        self.track_mouse_move = track_mouse_move  # Track mouse movement

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(
            self._on_idle_timeout
        )  # Connect the timeout signal to the _on_idle_timeout method

        # throttle mouse move (sinon spam)
        self._mm_timer = QElapsedTimer()
        self._mm_interval_ms = 200
        self._mm_timer.start()

        self._is_idle = False
        self.reset_idle_timer()

    def reset_idle_timer(self):
        self._idle_timer.stop()
        self._idle_timer.start(self.idle_ms)

    def _mark_activity(self):
        if self._is_idle:
            self._is_idle = False
        self.became_active.emit()
        self.reset_idle_timer()

    def _on_idle_timeout(self):
        self._is_idle = True
        self.became_idle.emit()

    def eventFilter(self, obj, event):
        et = event.type()

        if et in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.Wheel,
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
            QEvent.Type.FocusIn,
            QEvent.Type.TouchBegin,
            QEvent.Type.TouchUpdate,
            QEvent.Type.TouchEnd,
        ):
            self._mark_activity()
            return False

        # Mouse move: utile pour "présence", mais à limiter
        if self.track_mouse_move and et == QEvent.Type.MouseMove:
            if self._mm_timer.elapsed() >= self._mm_interval_ms:
                self._mm_timer.restart()
                self._mark_activity()
            return False

        return False
