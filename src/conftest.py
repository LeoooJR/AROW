"""Pytest wiring for packages under ``src/``."""

import locale
import os

from logger import setup_logger

pytest_plugins = ["core.tests.geo_fixtures"]


def pytest_configure() -> None:
    """Ensure file sink and format are active before importing modules that log at import time."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
    except locale.Error:
        # Locale setting failed (not available on this machine); fallback to default locale.
        pass
    setup_logger()
