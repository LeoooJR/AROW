"""
Per-async-job outcome callbacks for AdbSubController (startup, pair, list refresh).

Keep AsyncRunner callbacks out of the subcontroller so each job is easy to read.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import core.pair_device_work as pair_device_work
from core.devices import Phone
from core.models import CoreRuntimeModel
from core.pair_device_work import PairDeviceOutcome
from core.startup_work import StartupResult, apply_main_thread
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

    def on_completed(self, result: object) -> None:
        """Handle completion (Qt main thread, from AsyncRunner)."""
        model = self._subcontroller.model
        if not isinstance(model, CoreRuntimeModel):
            logger.warning(
                "Controller: model type mismatch",
                model_type=type(model).__name__,
            )
            return
        if not isinstance(result, StartupResult):
            logger.error(
                "AdbSubController: unexpected startup result type",
                result_type=type(result).__name__,
            )
            return
        logger.info(
            "AdbSubController: startup core runtime completed",
            adb_server=result.adb_server is not None,
        )
        apply_main_thread(model, result)

    def on_failed(self, error: JobError) -> None:
        log_startup_job_failure(error)


def log_pair_device_job_failure(error: JobError) -> None:
    """Log a failed pair-device async job (aside from AsyncRunner's generic log)."""
    logger.error(
        "AdbSubController: pair_device job failed",
        message=error.message,
        return_code=error.return_code,
        traceback=error.traceback or None,
    )


class PairDeviceCallback:
    """Callback for the pair device job."""

    __slots__ = ("_subcontroller", "__weakref__")

    def __init__(self, subcontroller: AdbSubController) -> None:
        self._subcontroller = subcontroller

    def on_completed(self, result: object) -> None:
        model = self._subcontroller.model
        if not isinstance(model, CoreRuntimeModel):
            logger.warning(
                "Controller: model type mismatch",
                model_type=type(model).__name__,
            )
            return
        if not isinstance(result, PairDeviceOutcome):
            logger.error(
                "AdbSubController: unexpected pair_device result type",
                result_type=type(result).__name__,
            )
            return
        pair_device_work.apply_main_thread(model, result)

    def on_failed(self, error: JobError) -> None:
        log_pair_device_job_failure(error)


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

    def on_completed(self, result: object) -> None:
        if not isinstance(self._subcontroller.model, CoreRuntimeModel):
            logger.warning(
                "Controller: model type mismatch",
                model_type=type(self._subcontroller.model).__name__,
            )
            return
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
        from gui.window import MainWindow

        view = self._subcontroller.view
        if not isinstance(view, MainWindow):
            logger.warning(
                "Controller: view type mismatch",
                view_type=type(view).__name__,
            )
            return
        device_ids = [d.descriptor.id for d in result]
        logger.info(
            "AdbSubController: known devices listed (async)",
            device_count=len(device_ids),
            device_ids=device_ids,
        )
        view.forward_devices_updated(device_ids)

    def on_failed(self, error: JobError) -> None:
        log_refresh_device_list_job_failure(error)


# AdbSubController method (async entry) -> attribute on :class:`AdbAsyncJobCallbacks`.
ADB_SUBCONTROLLER_METHOD_TO_CALLBACK_ATTR: dict[str, str] = {
    "_startup_core_runtime": "startup",
    "_on_authentification_confirmed": "pair_device",
    "_on_refresh_device_list_requested": "refresh_device_list",
}


@dataclass(frozen=True, slots=True)
class AdbAsyncJobCallbacks:
    """
    Single holder for AsyncRunner outcome callbacks on :class:`AdbSubController`.

    See :data:`ADB_SUBCONTROLLER_METHOD_TO_CALLBACK_ATTR` for which subcontroller
    method uses which field.
    """

    startup: StartupCoreRuntimeCallback
    pair_device: PairDeviceCallback
    refresh_device_list: RefreshDeviceListCallback

    @classmethod
    def for_subcontroller(cls, subcontroller: AdbSubController) -> AdbAsyncJobCallbacks:
        return cls(
            startup=StartupCoreRuntimeCallback(subcontroller),
            pair_device=PairDeviceCallback(subcontroller),
            refresh_device_list=RefreshDeviceListCallback(subcontroller),
        )
