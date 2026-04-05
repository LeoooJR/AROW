class CoreException(Exception):
    """
    Base exception for all core exceptions
    """


class AdbException(CoreException):
    """
    Base exception for all adb exceptions
    """


class AdbServerException(AdbException):
    """
    Exception for all adb server exceptions
    """


class AdbClientException(AdbException):
    """
    Exception for all adb client exceptions
    """
