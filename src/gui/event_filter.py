from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QTimer, Signal, Slot

from gui.settings import Settings


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
        # Counts consecutive idle timeouts since last activity; drives longer poll intervals.
        self._idle_stretch_index: int = 0
        self.reset_idle_timer()

    def reset_idle_timer(self, msecs: int | None = None):
        """Reset the idle timer.

        Args:
            msecs: The number of milliseconds to reset the idle timer to. If None, the idle timer will be reset to the idle_ms value.
        """
        self._idle_timer.stop()
        self._idle_timer.start(msecs if msecs is not None else self.idle_ms)

    def _mark_activity(self):
        if self._is_idle:
            self._is_idle = False
        self._idle_stretch_index = 0
        self.became_active.emit()
        self.reset_idle_timer()

    ### Slots ###

    @Slot()
    def _on_idle_timeout(self):
        self._is_idle = True
        self.became_idle.emit()
        # Each following timeout uses a longer interval (capped) until the user acts again.
        step = Settings.ANIMATION.ACTIVITY_IDLE_ESCALATION_STEP_MS
        cap = Settings.ANIMATION.ACTIVITY_IDLE_ESCALATION_CAP_MS
        next_ms = min(self.idle_ms + (self._idle_stretch_index + 1) * step, cap)
        self._idle_stretch_index += 1
        self.reset_idle_timer(msecs=next_ms)

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
