from core.exceptions import CoreException


class AdbException(CoreException):
    """Base exception for all ADB exceptions."""


class AdbServerException(AdbException):
    """Exception for all ADB server exceptions."""


class AdbClientException(AdbException):
    """Exception for all ADB client exceptions."""
