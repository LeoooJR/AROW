"""Tests for centralized application paths."""

from __future__ import annotations

import pickle
from datetime import datetime
from pathlib import Path

import pytest

import application_paths
from application_paths import APPLICATION_PATHS, ApplicationPaths


def _paths(tmp_path: Path, *, platform: str = "linux") -> ApplicationPaths:
    return ApplicationPaths(
        application_dir=tmp_path / "data",
        config_dir=tmp_path / "config",
        source_dir=tmp_path / "src",
        platform=platform,
    )


def test_application_paths_exports_one_stable_default_instance() -> None:
    assert isinstance(APPLICATION_PATHS, ApplicationPaths)
    assert application_paths.APPLICATION_PATHS is APPLICATION_PATHS


def test_from_environment_preserves_unix_application_location(tmp_path: Path) -> None:
    paths = ApplicationPaths.from_environment(
        platform="darwin",
        environment={},
        home_dir=tmp_path,
        source_dir=tmp_path / "src",
    )

    assert paths.application_dir == tmp_path / ".arow"
    assert paths.config_dir == tmp_path / ".config" / "arow"


def test_from_environment_uses_xdg_config_home(tmp_path: Path) -> None:
    paths = ApplicationPaths.from_environment(
        platform="linux",
        environment={"XDG_CONFIG_HOME": "custom-config"},
        home_dir=tmp_path,
    )

    assert paths.config_dir == (tmp_path / "custom-config" / "arow").resolve()


def test_from_environment_resolves_xdg_tilde_against_injected_home(
    tmp_path: Path,
) -> None:
    paths = ApplicationPaths.from_environment(
        platform="linux",
        environment={"XDG_CONFIG_HOME": "~/xdg"},
        home_dir=tmp_path,
    )

    assert paths.config_dir == (tmp_path / "xdg" / "arow").resolve()


def test_from_environment_uses_windows_environment_paths(tmp_path: Path) -> None:
    paths = ApplicationPaths.from_environment(
        platform="windows",
        environment={
            "LOCALAPPDATA": str(tmp_path / "local"),
            "APPDATA": str(tmp_path / "roaming"),
        },
        home_dir=tmp_path / "home",
    )

    assert paths.application_dir == tmp_path / "local" / "arow"
    assert paths.config_dir == tmp_path / "roaming" / "arow"
    assert paths.platform == "win32"


def test_from_environment_uses_windows_fallbacks(tmp_path: Path) -> None:
    paths = ApplicationPaths.from_environment(
        platform="win32",
        environment={},
        home_dir=tmp_path,
    )

    assert paths.application_dir == tmp_path / "AppData" / "Local" / "arow"
    assert paths.config_dir == tmp_path / "AppData" / "Roaming" / "arow"


def test_log_paths_are_deterministic_when_inputs_are_supplied(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    fixed_now = datetime(2026, 5, 31, 14, 30, 0)
    run_identifier = "01fdb29d-2e6b-49d1-8956-9d1caa576d2c"

    assert paths.activity_log_file(now=fixed_now) == (
        tmp_path / "data" / "logs" / "activity_20260531.log"
    )
    assert paths.application_log_file(run_identifier=run_identifier) == (
        tmp_path / "data" / "logs" / f"{run_identifier}.log"
    )


def test_writable_paths_have_no_directory_creation_side_effects(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    _ = (
        paths.logs_dir,
        paths.install_identity_file,
        paths.simulations_dir,
        paths.simulation_index_file,
        paths.simulation_metadata_file("sim-1"),
        paths.simulation_log_file("sim-1"),
        paths.simulation_map_file("sim-1"),
    )

    assert not paths.application_dir.exists()
    assert not paths.config_dir.exists()


@pytest.mark.parametrize(
    ("platform", "relative_path"),
    [
        ("darwin", Path("assets/macos/platform-tools/adb")),
        ("linux", Path("assets/linux/platform-tools/adb")),
        ("win32", Path("assets/win/platform-tools/adb.exe")),
    ],
)
def test_adb_binary_uses_platform_asset(
    tmp_path: Path,
    platform: str,
    relative_path: Path,
) -> None:
    paths = _paths(tmp_path, platform=platform)

    assert paths.adb_binary == paths.source_dir / relative_path


def test_adb_binary_rejects_unsupported_platform(tmp_path: Path) -> None:
    paths = _paths(tmp_path, platform="freebsd")

    with pytest.raises(RuntimeError, match="Unsupported operating system"):
        _ = paths.adb_binary


def test_geo_resource_paths_use_source_root(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    assert paths.geo_dataset_file("railway.sqlite") == (
        paths.source_dir / "core" / "geo" / "statics" / "railway.sqlite"
    )
    assert paths.geo_icon_file("station.svg") == (
        paths.source_dir / "core" / "geo" / "assets" / "station.svg"
    )


def test_application_paths_is_pickle_serializable(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    assert pickle.loads(pickle.dumps(paths)) == paths
