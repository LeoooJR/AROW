"""Tests for work-specific CoreException subclasses."""

from __future__ import annotations

from core.exceptions import CoreException
from core.work.authentificate_device_work import DeviceAuthentificationError
from core.work.close_work import CloseCoreRuntimeError
from core.work.host_install_identity_work import HostInstallIdentityError
from core.work.refresh_known_devices_work import RefreshKnownDevicesError
from core.work.startup_work import StartupCoreRuntimeError


def test_work_exceptions_subclass_core_exception() -> None:
    for exc_cls in (
        StartupCoreRuntimeError,
        RefreshKnownDevicesError,
        HostInstallIdentityError,
        CloseCoreRuntimeError,
        DeviceAuthentificationError,
    ):
        assert issubclass(exc_cls, CoreException)


def test_work_exceptions_expose_reason() -> None:
    error = RefreshKnownDevicesError("refresh preflight failed")
    assert error.reason == "refresh preflight failed"
    assert str(error) == "refresh preflight failed"
