"""
Per-async-job outcome callbacks for AdbSubController (startup, host identity,
authentificate, list refresh, close core runtime).

Keep AsyncRunner callbacks out of the subcontroller so each job is easy to read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from controller.helper import validate_model_entrypoint
from controller.runner import JobError
from core.work.authentificate_device_work import AuthentificateDeviceOutcome
from core.work.close_work import CloseOutcome
from core.work.host_install_identity_work import HostInstallIdentityOutcome
from core.work.refresh_known_devices_work import RefreshKnownDevicesOutcome
from core.work.startup_work import StartupOutcome
from logger import logger

if TYPE_CHECKING:
    from controller.domains.adb_sub_controller import AdbSubController


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

    @validate_model_entrypoint
    def on_completed(self, result: object) -> None:
        """Handle completion (Qt main thread, from AsyncRunner)."""
        model_entrypoint = self._subcontroller.model_entrypoint
        if not isinstance(result, StartupOutcome):
            logger.error(
                "AdbSubController: unexpected startup result type",
                result_type=type(result).__name__,
            )
            return
        logger.success(
            "AdbSubController: startup core runtime completed",
            adb_server=result.adb_server is not None,
        )
        model_entrypoint.apply_result(result)
        self._subcontroller._enqueue_host_install_identity_job()

    @validate_model_entrypoint
    def on_failed(self, error: JobError) -> None:
        log_startup_job_failure(error)
        self._subcontroller.model_entrypoint.apply_failure(error)


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

    @validate_model_entrypoint
    def on_completed(self, result: object) -> None:
        model_entrypoint = self._subcontroller.model_entrypoint
        if not isinstance(result, AuthentificateDeviceOutcome):
            logger.error(
                "AdbSubController: unexpected authentificate device result type",
                result_type=type(result).__name__,
            )
            return
        model_entrypoint.apply_result(result)

    @validate_model_entrypoint
    def on_failed(self, error: JobError) -> None:
        log_authentificate_device_job_failure(error)
        self._subcontroller.model_entrypoint.apply_failure(error)


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

    @validate_model_entrypoint
    def on_completed(self, result: object) -> None:
        model_entrypoint = self._subcontroller.model_entrypoint
        if not isinstance(result, RefreshKnownDevicesOutcome):
            logger.error(
                "AdbSubController: unexpected refresh_device_list result type",
                result_type=type(result).__name__,
            )
            return
        device_ids = [d.descriptor.id for d in result.devices]
        logger.success(
            "AdbSubController: known devices listed (async)",
            device_count=len(device_ids),
            device_ids=device_ids,
        )
        model_entrypoint.apply_result(result)
        self._subcontroller._is_refreshing_device_list = False  # Clear guard to prevent multiple concurrent refresh device list requests

    @validate_model_entrypoint
    def on_failed(self, error: JobError) -> None:
        log_refresh_device_list_job_failure(error)
        self._subcontroller.model_entrypoint.apply_failure(error)
        self._subcontroller._is_refreshing_device_list = False  # Clear guard to prevent multiple concurrent refresh device list requests


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

    @validate_model_entrypoint
    def on_completed(self, result: object) -> None:
        model_entrypoint = self._subcontroller.model_entrypoint
        if not isinstance(result, HostInstallIdentityOutcome):
            logger.error(
                "AdbSubController: unexpected host_install_identity result type",
                result_type=type(result).__name__,
            )
            return
        model_entrypoint.apply_result(result)
        logger.success(
            "AdbSubController: host install identity completed",
        )

    def on_failed(self, error: JobError) -> None:
        """Handle failure (Qt main thread, from AsyncRunner)."""
        log_host_install_identity_job_failure(error)
        self._subcontroller.model_entrypoint.apply_failure(error)


def log_close_core_runtime_job_failure(error: JobError) -> None:
    """Log a failed close-core-runtime async job."""
    logger.error(
        "AdbSubController: close_core_runtime job failed",
        message=error.message,
        return_code=error.return_code,
        traceback=error.traceback or None,
    )


class CloseCoreRuntimeCallback:
    """Callback for closing the core runtime (ADB stop); optional hook after ``apply_result``."""

    __slots__ = ("_subcontroller", "__weakref__")

    def __init__(self, subcontroller: AdbSubController) -> None:
        self._subcontroller = subcontroller

    def _consume_pending_after_close_apply(self) -> None:
        """Clear and invoke one-shot hook registered on ``AdbSubController`` (shutdown / tests)."""
        sc = self._subcontroller
        hook = sc._pending_after_close_apply
        sc._pending_after_close_apply = None
        if hook is not None:
            hook()

    @validate_model_entrypoint
    def on_completed(self, result: object) -> None:
        model_entrypoint = self._subcontroller.model_entrypoint
        if not isinstance(result, CloseOutcome):
            logger.error(
                "AdbSubController: unexpected close_core_runtime result type",
                result_type=type(result).__name__,
            )
            self._consume_pending_after_close_apply()
            return
        model_entrypoint.apply_result(result)
        logger.success(
            "AdbSubController: close_core_runtime completed",
        )
        self._consume_pending_after_close_apply()

    def on_failed(self, error: JobError) -> None:
        log_close_core_runtime_job_failure(error)
        self._subcontroller.model_entrypoint.apply_failure(error)
        self._consume_pending_after_close_apply()


# AdbSubController method (async entry) -> attribute on :class:`AdbAsyncJobCallbacks`.
ADB_SUBCONTROLLER_METHOD_TO_CALLBACK_ATTR: dict[str, str] = {
    "_startup_core_runtime": "startup",
    "_on_authentification_confirmed": "authentificate_device",
    "_on_refresh_device_list_requested": "refresh_device_list",
    "_enqueue_host_install_identity_job": "host_install_identity",
    "_enqueue_close_core_runtime": "close",
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
    close: CloseCoreRuntimeCallback

    @classmethod
    def for_subcontroller(cls, subcontroller: AdbSubController) -> AdbAsyncJobCallbacks:
        return cls(
            startup=StartupCoreRuntimeCallback(subcontroller),
            authentificate_device=AuthentificateDeviceCallback(subcontroller),
            refresh_device_list=RefreshDeviceListCallback(subcontroller),
            host_install_identity=HostInstallIdentityCallback(subcontroller),
            close=CloseCoreRuntimeCallback(subcontroller),
        )
