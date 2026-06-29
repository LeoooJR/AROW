class SchemaValidationError(Exception):
    """Exception for schema validation errors."""


class MapElementValidationError(Exception):
    """Exception for element validation errors."""


class MilestoneValidationError(MapElementValidationError):
    """Exception for milestone validation errors."""


class RailwayValidationError(MapElementValidationError):
    """Exception for railway validation errors."""


class StationValidationError(MapElementValidationError):
    """Exception for station validation errors."""
