"""Public geometry serialization helpers for geo domain persistence."""

from __future__ import annotations

import base64
from typing import cast

from shapely import from_wkb
from shapely.geometry.base import BaseGeometry


def serialize_geometry(geometry: BaseGeometry, **kwargs: object) -> bytes | str:
    """Serialize geometry for persistence; base64 when writing JSON metadata."""
    wkb = geometry.wkb
    if kwargs.get("json_compatible", False):
        return base64.b64encode(wkb).decode("ascii")
    return wkb


def deserialize_geometry(raw: object) -> BaseGeometry:
    """Restore geometry from a payload field (raw WKB bytes or base64 text)."""
    if isinstance(raw, str):
        return from_wkb(base64.b64decode(raw))
    return from_wkb(cast(bytes, raw))
