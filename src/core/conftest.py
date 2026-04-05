"""
Pytest configuration and shared fixtures for src/core tests.
"""

from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "devices: mark test as belonging to the devices module (Device, Phone, Computer, DeviceState).",
    )
    config.addinivalue_line(
        "markers",
        "adb: mark test as belonging to the adb module (AdbServer, AdbClient, server start/kill).",
    )
    config.addinivalue_line(
        "markers",
        "adb_server: mark test as exercising ADB server commands (start-server, kill-server) only.",
    )
    config.addinivalue_line(
        "markers",
        "async_jobs: mark tests as exercising the controller async framework (AsyncRunner, pools, signals).",
    )


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Project repository root (parent of src)."""
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="session")
def adb_binary_path(repo_root: Path) -> Path:
    """Path to the ADB binary for the current platform (macos by default in assets)."""
    base = repo_root / "src" / "assets" / "macos" / "platform-tools" / "adb"
    if not base.exists():
        base = repo_root / "src" / "assets" / "macos" / "adb"
    return base
