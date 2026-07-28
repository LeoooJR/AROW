"""Centralized, side-effect-free paths owned by the AROW application."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from faker import Faker

__all__ = ["APPLICATION_PATHS", "ApplicationPaths"]

_application_log_faker = Faker("en_US", use_weighting=False)


def _normalize_platform(platform: str) -> str:
    """Normalize common platform spellings to Python's ``sys.platform`` values."""
    normalized = platform.strip().lower()
    aliases = {"windows": "win32", "macos": "darwin"}
    return aliases.get(normalized, normalized)


def _resolved_environment_base(value: str, *, home_dir: Path) -> Path:
    """Resolve an environment-provided directory against an explicit home."""
    if value == "~":
        path = home_dir
    elif value.startswith("~/") or value.startswith("~\\"):
        path = home_dir / value[2:]
    else:
        path = Path(value)
    if not path.is_absolute():
        path = home_dir / path
    return path.resolve(strict=False)


@dataclass(frozen=True, slots=True)
class ApplicationPaths:
    """Resolved roots and derived paths owned by one AROW application runtime."""

    application_dir: Path
    config_dir: Path
    source_dir: Path
    platform: str

    @classmethod
    def from_environment(
        cls,
        *,
        platform: str | None = None,
        environment: Mapping[str, str] | None = None,
        home_dir: Path | None = None,
        source_dir: Path | None = None,
    ) -> ApplicationPaths:
        """Resolve application roots from an OS environment without creating them."""
        resolved_platform = _normalize_platform(platform or sys.platform)
        resolved_environment = os.environ if environment is None else environment
        resolved_home = Path.home() if home_dir is None else home_dir
        resolved_source = (
            Path(__file__).resolve().parent if source_dir is None else source_dir
        )

        if resolved_platform == "win32":
            local_app_data = resolved_environment.get("LOCALAPPDATA", "").strip()
            application_dir = (
                Path(local_app_data) / "arow"
                if local_app_data
                else resolved_home / "AppData" / "Local" / "arow"
            )
            roaming_app_data = resolved_environment.get("APPDATA", "").strip()
            config_base = (
                _resolved_environment_base(
                    roaming_app_data,
                    home_dir=resolved_home,
                )
                if roaming_app_data
                else resolved_home / "AppData" / "Roaming"
            )
        else:
            application_dir = resolved_home / ".arow"
            xdg_config_home = resolved_environment.get("XDG_CONFIG_HOME", "").strip()
            config_base = (
                _resolved_environment_base(
                    xdg_config_home,
                    home_dir=resolved_home,
                )
                if xdg_config_home
                else resolved_home / ".config"
            )
        config_base = config_base.resolve(strict=False)

        return cls(
            application_dir=application_dir,
            config_dir=config_base / "arow",
            source_dir=resolved_source,
            platform=resolved_platform,
        )

    @property
    def logs_dir(self) -> Path:
        """Directory containing user activity and low-level application logs."""
        return self.application_dir / "logs"

    def activity_log_file(self, *, now: datetime | None = None) -> Path:
        """Dated user-facing activity log file."""
        day_stamp = (now or datetime.now()).strftime("%Y%m%d")
        return self.logs_dir / f"activity_{day_stamp}.log"

    def application_log_file(self, *, run_identifier: str | None = None) -> Path:
        """UUID4-named low-level log file for one process run."""
        identifier = run_identifier or _application_log_faker.uuid4()
        return self.logs_dir / f"{identifier}.log"

    @property
    def install_identity_file(self) -> Path:
        """Persisted per-install host identity token."""
        return self.application_dir / "install_identity"

    @property
    def simulations_dir(self) -> Path:
        """Root directory for persisted simulations."""
        return self.application_dir / "simulations"

    @property
    def simulation_index_file(self) -> Path:
        """Persisted simulation repository index."""
        return self.simulations_dir / "index.json"

    def simulation_dir(self, simulation_id: str) -> Path:
        """Directory containing one simulation's artifacts."""
        return self.simulations_dir / simulation_id

    def simulation_metadata_file(self, simulation_id: str) -> Path:
        """Metadata file for one persisted simulation."""
        return self.simulation_dir(simulation_id) / "simulation.json"

    def simulation_log_file(self, simulation_id: str) -> Path:
        """Log file for one persisted simulation."""
        return self.simulation_dir(simulation_id) / f"{simulation_id}.log"

    def simulation_map_dir(self, simulation_id: str) -> Path:
        """Directory containing one simulation's rendered map."""
        return self.simulation_dir(simulation_id) / "map"

    def simulation_map_file(self, simulation_id: str) -> Path:
        """Rendered HTML map file for one simulation."""
        return self.simulation_map_dir(simulation_id) / f"{simulation_id}.html"

    @property
    def assets_dir(self) -> Path:
        """Root directory for application-bundled assets."""
        return self.source_dir / "assets"

    @property
    def adb_binary(self) -> Path:
        """Bundled ADB executable for the configured operating system."""
        platform_parts = {
            "darwin": ("macos", "adb"),
            "linux": ("linux", "adb"),
            "win32": ("win", "adb.exe"),
        }
        try:
            platform_folder, binary_name = platform_parts[self.platform]
        except KeyError:
            raise RuntimeError(
                f"Unsupported operating system for ADB startup: {self.platform}"
            ) from None
        return self.assets_dir / platform_folder / "platform-tools" / binary_name

    @property
    def geo_datasets_dir(self) -> Path:
        """Directory containing bundled geospatial datasets."""
        return self.source_dir / "core" / "geo" / "statics"

    def geo_dataset_file(self, filename: str) -> Path:
        """Path to one bundled geospatial dataset."""
        return self.geo_datasets_dir / filename

    @property
    def geo_icons_dir(self) -> Path:
        """Directory containing bundled map icon assets."""
        return self.source_dir / "core" / "geo" / "assets"

    def geo_icon_file(self, filename: str) -> Path:
        """Path to one bundled map icon."""
        return self.geo_icons_dir / filename


APPLICATION_PATHS: Final[ApplicationPaths] = ApplicationPaths.from_environment()
