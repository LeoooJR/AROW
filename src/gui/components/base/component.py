"""Abstract base for GUI components."""

from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod

from PySide6.QtCore import QObject

from gui.constants.colors import Theme


class QtABCMeta(type(QObject), ABCMeta):  # type: ignore[misc]
    """Merges QObject's metaclass with abc.ABCMeta so Qt widgets can inherit from Component."""

    pass


class Component(ABC, metaclass=QtABCMeta):
    """
    Abstract base for all graphical components in this module.
    """

    def _finalize_ui_hooks(self) -> None:
        """Run the standard UI hook sequence after widget construction."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    @abstractmethod
    def _set_size_policy(self) -> None:
        """Set the size policy for elements composing the widget."""
        ...

    @abstractmethod
    def _set_alignment(self) -> None:
        """Set the alignment for elements composing the widget."""
        ...

    @abstractmethod
    def _connect_signals(self) -> None:
        """Connect signals for elements composing the widget."""
        ...

    @abstractmethod
    def apply_theme_icons(self, theme: Theme) -> None:
        """Apply theme icons to elements composing the widget."""
        ...
