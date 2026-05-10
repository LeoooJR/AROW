"""Pytest wiring for packages under ``src/``."""

from logger import setup_logger


def pytest_configure() -> None:
    """Ensure file sink and format are active before importing modules that log at import time."""
    setup_logger()
