"""Pytest wiring for packages under ``src/``."""

import locale
import os

from logger import setup_logger


def pytest_configure() -> None:
    """Ensure file sink and format are active before importing modules that log at import time."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    locale.setlocale(
        locale.LC_ALL, "en_US.UTF-8"
    )  # Set locale to English for consistent formatting
    setup_logger()
