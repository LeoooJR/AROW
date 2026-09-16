from __future__ import annotations

from pathlib import Path


class DatasetError(Exception):
    """Base exception for dataset loading and validation failures."""


class SchemaValidationError(DatasetError):
    """Exception for schema validation errors."""


class DatasetNotFoundError(DatasetError):
    """Raised when a dataset id or packaged asset file is missing."""

    def __init__(
        self,
        dataset_id: str,
        message: str,
        *,
        path: Path | None = None,
    ) -> None:
        """Initialize a missing-dataset error.

        Args:
            dataset_id: Identifier of the missing dataset.
            message: Human-readable failure description.
            path: Expected packaged asset path, when known.
        """
        self.dataset_id = dataset_id
        self.path = path
        super().__init__(message)


class DatasetCorruptionError(DatasetError):
    """Raised when a dataset asset is unreadable or fails integrity checks."""

    def __init__(
        self,
        dataset_id: str,
        message: str,
        *,
        path: Path | None = None,
        expected_hash: str | None = None,
        actual_hash: str | None = None,
    ) -> None:
        """Initialize an unreadable or invalid-dataset error.

        Args:
            dataset_id: Identifier of the corrupt dataset.
            message: Human-readable failure description.
            path: Packaged asset path, when known.
            expected_hash: Expected SHA-256 digest, when available.
            actual_hash: Observed SHA-256 digest, when available.
        """
        self.dataset_id = dataset_id
        self.path = path
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(message)


class MapElementValidationError(Exception):
    """Exception for element validation errors."""


class MilestoneValidationError(MapElementValidationError):
    """Exception for milestone validation errors."""


class RailwayValidationError(MapElementValidationError):
    """Exception for railway validation errors."""


class StationValidationError(MapElementValidationError):
    """Exception for station validation errors."""
