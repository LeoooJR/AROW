"""
Per-async-job outcome callbacks for AdbSubController (startup, host identity, authentificate, list refresh).

Keep AsyncRunner callbacks out of the subcontroller so each job is easy to read.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from controller.helper import validate_model, validate_view
from core.devices import Phone
from core.work.authentificate_device_work import AuthentificateDeviceOutcome
from core.work.host_install_identity_work import HostInstallIdentityOutcome
from core.work.startup_work import StartupResult
from logger import logger

if TYPE_CHECKING:
    from controller.adb_sub_controller import AdbSubController

_async = importlib.import_module("controller.async")
JobError = _async.JobError


def log_startup_job_failure(error: JobError) -> None:
    """
    Log a failed core-runtime startup job (controller-facing; single place
    for this scenario aside from AsyncRunner's generic job failure log).
    """
    logger.error(
        "AdbSubController: core runtime startup job failed",
        message=error.message,
        return_code=error.return_code,
        traceback=error.traceback or None,
    )


class StartupCoreRuntimeCallback:
    """Callback for the startup core runtime job."""

    # __weakref__ required so Qt can weak-ref bound methods used as signal slots.
    __slots__ = ("_subcontroller", "__weakref__")

    def __init__(self, subcontroller: AdbSubController) -> None:
        self._subcontroller = subcontroller

    @validate_model
    def on_completed(self, result: object) -> None:
        """Handle completion (Qt main thread, from AsyncRunner)."""
        model = self._subcontroller.model
        if not isinstance(result, StartupResult):
            logger.error(
                "AdbSubController: unexpected startup result type",
                result_type=type(result).__name__,
            )
            return
        logger.success(
            "AdbSubController: startup core runtime completed",
            adb_server=result.adb_server is not None,
        )
        model.apply_result(result)
        self._subcontroller._enqueue_host_install_identity_job()

    def on_failed(self, error: JobError) -> None:
        log_startup_job_failure(error)


def log_authentificate_device_job_failure(error: JobError) -> None:
    """Log a failed authentificate device async job (aside from AsyncRunner's generic log)."""
    logger.error(
        "AdbSubController: authentificate device job failed",
        message=error.message,
        return_code=error.return_code,
        traceback=error.traceback or None,
    )


class AuthentificateDeviceCallback:
    """Callback for the authentificate device job."""

    __slots__ = ("_subcontroller", "__weakref__")

    def __init__(self, subcontroller: AdbSubController) -> None:
        self._subcontroller = subcontroller

    @validate_model
    def on_completed(self, result: object) -> None:
        model = self._subcontroller.model
        if not isinstance(result, AuthentificateDeviceOutcome):
            logger.error(
                "AdbSubController: unexpected authentificate device result type",
                result_type=type(result).__name__,
            )
            return
        model.apply_result(result)

    def on_failed(self, error: JobError) -> None:
        log_authentificate_device_job_failure(error)


def log_refresh_device_list_job_failure(error: JobError) -> None:
    """Log a failed refresh-device-list async job."""
    logger.error(
        "AdbSubController: refresh_device_list job failed",
        message=error.message,
        return_code=error.return_code,
        traceback=error.traceback or None,
    )


class RefreshDeviceListCallback:
    """Callback for the refresh device list job."""

    __slots__ = ("_subcontroller", "__weakref__")

    def __init__(self, subcontroller: AdbSubController) -> None:
        self._subcontroller = subcontroller

    @validate_view
    def on_completed(self, result: object) -> None:
        if not isinstance(result, list):
            logger.error(
                "AdbSubController: unexpected refresh_device_list result type",
                result_type=type(result).__name__,
            )
            return
        for item in result:
            if not isinstance(item, Phone):
                logger.error(
                    "AdbSubController: refresh list contained non-Phone",
                    item_type=type(item).__name__,
                )
                return

        view = self._subcontroller.view
        device_ids = [d.descriptor.id for d in result]
        logger.success(
            "AdbSubController: known devices listed (async)",
            device_count=len(device_ids),
            device_ids=device_ids,
        )
        view.forward_devices_updated(device_ids)

    def on_failed(self, error: JobError) -> None:
        log_refresh_device_list_job_failure(error)


def log_host_install_identity_job_failure(error: JobError) -> None:
    """Log a failed host install-identity disk job."""
    logger.error(
        "AdbSubController: host_install_identity job failed",
        message=error.message,
        return_code=error.return_code,
        traceback=error.traceback or None,
    )


class HostInstallIdentityCallback:
    """Persisted install UUID read/create on a worker thread; apply on Qt main thread."""

    __slots__ = ("_subcontroller", "__weakref__")

    def __init__(self, subcontroller: AdbSubController) -> None:
        self._subcontroller = subcontroller

    @validate_model
    def on_completed(self, result: object) -> None:
        model = self._subcontroller.model
        if not isinstance(result, HostInstallIdentityOutcome):
            logger.error(
                "AdbSubController: unexpected host_install_identity result type",
                result_type=type(result).__name__,
            )
            return
        model.apply_result(result)
        logger.success(
            "AdbSubController: host install identity completed",
        )

    def on_failed(self, error: JobError) -> None:
        log_host_install_identity_job_failure(error)


# AdbSubController method (async entry) -> attribute on :class:`AdbAsyncJobCallbacks`.
ADB_SUBCONTROLLER_METHOD_TO_CALLBACK_ATTR: dict[str, str] = {
    "_startup_core_runtime": "startup",
    "_on_authentification_confirmed": "authentificate_device",
    "_on_refresh_device_list_requested": "refresh_device_list",
    "_enqueue_host_install_identity_job": "host_install_identity",
}


@dataclass(frozen=True, slots=True)
class AdbAsyncJobCallbacks:
    """
    Single holder for AsyncRunner outcome callbacks on :class:`AdbSubController`.

    See :data:`ADB_SUBCONTROLLER_METHOD_TO_CALLBACK_ATTR` for which subcontroller
    method uses which field.
    """

    startup: StartupCoreRuntimeCallback
    authentificate_device: AuthentificateDeviceCallback
    refresh_device_list: RefreshDeviceListCallback
    host_install_identity: HostInstallIdentityCallback

    @classmethod
    def for_subcontroller(cls, subcontroller: AdbSubController) -> AdbAsyncJobCallbacks:
        return cls(
            startup=StartupCoreRuntimeCallback(subcontroller),
            authentificate_device=AuthentificateDeviceCallback(subcontroller),
            refresh_device_list=RefreshDeviceListCallback(subcontroller),
            host_install_identity=HostInstallIdentityCallback(subcontroller),
        )
