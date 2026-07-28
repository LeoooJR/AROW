"""Pytest wiring for packages under ``src/``."""

import locale
import os
from collections.abc import Iterator
from typing import Any

import pytest
from loguru import logger

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


@pytest.fixture
def log_records() -> Iterator[list[dict[str, Any]]]:
    """Capture Loguru records without replacing the configured application sink."""
    records: list[dict[str, Any]] = []
    handler_id = logger.add(lambda message: records.append(message.record), level=0)
    try:
        yield records
    finally:
        logger.remove(handler_id)
