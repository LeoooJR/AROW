"""Stable logical identities for Android phones."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass

_STABLE_HW_PREFIX = "hw:v1:"
_STABLE_FP_PREFIX = "fp:v1:"
_FINGERPRINT_V1_MARKER = "|fp|v1|"


class StableKey(ABC):
    """Canonical stable identity for an Android phone."""

    @property
    @abstractmethod
    def value(self) -> str:
        """Return the canonical persisted representation."""

    @abstractmethod
    def is_collision_resistant(self) -> bool:
        """Whether this identity is safe for cross-session reconciliation."""

    @classmethod
    def from_value(cls, value: str | None) -> StableKey | None:
        """Parse a persisted phone stable-key value, if it is recognized."""
        normalized = (value or "").strip()
        if normalized.startswith(_STABLE_HW_PREFIX):
            serial = normalized.removeprefix(_STABLE_HW_PREFIX)
            return (
                FirstTierStableKey(serial)
                if _is_valid_hardware_serial(serial)
                else None
            )
        if normalized.startswith(_STABLE_FP_PREFIX):
            digest = normalized.removeprefix(_STABLE_FP_PREFIX)
            return SecondTierStableKey.from_digest(digest)
        return None


def _is_valid_hardware_serial(value: str) -> bool:
    return bool(value.strip()) and value.strip().casefold() != "unknown"


@dataclass(frozen=True)
class FirstTierStableKey(StableKey):
    """Tier-1 identity derived from ``ro.serialno``."""

    hardware_serial: str

    def __post_init__(self) -> None:
        normalized = self.hardware_serial.strip()
        if not _is_valid_hardware_serial(normalized):
            raise ValueError("hardware_serial must be non-empty and not 'unknown'")
        object.__setattr__(self, "hardware_serial", normalized)

    @property
    def value(self) -> str:
        return f"{_STABLE_HW_PREFIX}{self.hardware_serial}"

    def is_collision_resistant(self) -> bool:
        return True


@dataclass(frozen=True)
class SecondTierStableKey(StableKey):
    """Tier-2 fingerprint derived from manufacturer, product, and model."""

    digest: str

    def __post_init__(self) -> None:
        normalized = self.digest.strip().lower()
        if len(normalized) != 64 or any(
            char not in "0123456789abcdef" for char in normalized
        ):
            raise ValueError("digest must be a SHA-256 hexadecimal digest")
        object.__setattr__(self, "digest", normalized)

    @classmethod
    def from_components(
        cls,
        *,
        product: str,
        model: str,
        manufacturer: str | None = None,
    ) -> SecondTierStableKey | None:
        """Create a fingerprint when at least one stable component is available."""
        manufacturer_value = (manufacturer or "").strip()
        product_value = product.strip()
        model_value = model.strip()
        if not (manufacturer_value or product_value or model_value):
            return None
        payload = (
            _FINGERPRINT_V1_MARKER
            + manufacturer_value.lower()
            + "|"
            + product_value.lower()
            + "|"
            + model_value.lower()
        )
        return cls(hashlib.sha256(payload.encode("utf-8")).hexdigest())

    @classmethod
    def from_digest(cls, digest: str) -> SecondTierStableKey | None:
        """Create a fingerprint key from a previously persisted digest."""
        try:
            return cls(digest)
        except ValueError:
            return None

    @property
    def value(self) -> str:
        return f"{_STABLE_FP_PREFIX}{self.digest}"

    def is_collision_resistant(self) -> bool:
        return False


def compute_phone_stable_key(
    *,
    hardware_serial: str | None,
    product: str,
    model: str,
    manufacturer: str | None = None,
    fingerprint_when_no_serial: bool = False,
) -> StableKey | None:
    """Return a Tier-1 key or the optional Tier-2 fingerprint fallback."""
    if hardware_serial and _is_valid_hardware_serial(hardware_serial):
        return FirstTierStableKey(hardware_serial)
    if fingerprint_when_no_serial:
        return SecondTierStableKey.from_components(
            product=product,
            model=model,
            manufacturer=manufacturer,
        )
    return None
