"""Pytest wiring for packages under ``src/``."""

import os

from logger import setup_logger


def pytest_configure() -> None:
    """Ensure file sink and format are active before importing modules that log at import time."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    setup_logger()
