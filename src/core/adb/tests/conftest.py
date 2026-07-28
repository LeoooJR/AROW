"""Pytest configuration and shared fixtures for core.adb tests."""

from pathlib import Path

import pytest

from application_paths import APPLICATION_PATHS


@pytest.fixture(scope="session")
def adb_binary_path() -> Path:
    """Path to the ADB binary shipped under ``src/assets/{macos,linux,win}/platform-tools``."""
    return APPLICATION_PATHS.adb_binary
