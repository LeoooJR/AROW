"""Shared geo-related pytest fixtures and sample coordinates for core tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from core.geo.railway import clear_lignes_par_type_cache

SAMPLE_LINE_CODE = "001000"
SAMPLE_LINE_TRONCON = 1
SAMPLE_LATITUDE = 48.88533318609319
SAMPLE_LONGITUDE = 2.363530409238113


@pytest.fixture
def clear_lignes_cache() -> Iterator[None]:
    """Reset the lignes-par-type in-memory cache before and after a geo test."""
    clear_lignes_par_type_cache()
    yield
    clear_lignes_par_type_cache()
