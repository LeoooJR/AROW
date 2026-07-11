"""
Pytest configuration and shared fixtures for src/core/tests tests.
"""

from pathlib import Path

import pytest

from core.work.startup_work import _resolve_adb_binary_path

pytest_plugins = ["core.tests.geo_fixtures"]


@pytest.fixture(scope="session")
def adb_binary_path() -> Path:
    """Path to the ADB binary shipped under ``src/assets/{macos,linux,win}/platform-tools``."""
    return _resolve_adb_binary_path()
