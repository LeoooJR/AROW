"""Host panel settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HostPanelSettings:
    """Host panel section spacing."""

    SECTION_SPACING: int = 8


host_panel_settings = HostPanelSettings()
