"""
Pytest configuration and shared fixtures for src/core tests.
"""

from pathlib import Path

import pytest

from core.work.startup_work import _resolve_adb_binary_path


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "devices: mark test as belonging to the devices module (Device, Phone, Computer, DeviceDescriptor).",
    )
    config.addinivalue_line(
        "markers",
        "adb: mark test as belonging to the adb module (AdbServer, AdbClient, server start/kill).",
    )
    config.addinivalue_line(
        "markers",
        "adb_parser: mark test as belonging to the adb_parser module (ADBCommandParser).",
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
def adb_binary_path() -> Path:
    """Path to the ADB binary shipped under ``src/assets/{macos,linux,win}/platform-tools``."""
    return _resolve_adb_binary_path()
