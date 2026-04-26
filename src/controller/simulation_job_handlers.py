"""
Per-async-job outcome handlers (success / fail) for SimulationController.

Keep AsyncRunner callbacks out of the large controller class so each job is
debuggable in one place.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import core.pair_device_work as pair_device_work
from core.devices import Phone
from core.models import CoreRuntimeModel
from core.pair_device_work import PairDeviceOutcome
from core.startup_work import StartupResult, apply_main_thread
from logger import logger

if TYPE_CHECKING:
    from controller.controller import SimulationController

_async = importlib.import_module("controller.async")
JobError = _async.JobError


def log_startup_job_failure(error: JobError) -> None:
    """
    Log a failed core-runtime startup job (controller-facing; single place
    for this scenario aside from AsyncRunner's generic job failure log).
    """
    logger.error(
        "SimulationController: core runtime startup job failed",
        message=error.message,
        return_code=error.return_code,
        traceback=error.traceback or None,
    )


class StartupCoreRuntimeJob:
    """Async job: model.startup() on a worker, apply on the main thread."""

    # __weakref__ required so Qt can weak-ref bound methods used as signal slots.
    __slots__ = ("_controller", "__weakref__")

    def __init__(self, controller: SimulationController) -> None:
        self._controller = controller

    def on_completed(self, result: object) -> None:
        """Handle completion (Qt main thread, from AsyncRunner)."""
        model = self._controller.model
        if not isinstance(model, CoreRuntimeModel):
            logger.warning(
                "Controller: model type mismatch",
                model_type=type(model).__name__,
            )
            return
        if not isinstance(result, StartupResult):
            logger.error(
                "SimulationController: unexpected startup result type",
                result_type=type(result).__name__,
            )
            return
        logger.info(
            "SimulationController: startup core runtime completed",
            adb_server=result.adb_server is not None,
        )
        apply_main_thread(model, result)

    def on_failed(self, error: JobError) -> None:
        log_startup_job_failure(error)


def log_pair_device_job_failure(error: JobError) -> None:
    """Log a failed pair-device async job (aside from AsyncRunner's generic log)."""
    logger.error(
        "SimulationController: pair_device job failed",
        message=error.message,
        return_code=error.return_code,
        traceback=error.traceback or None,
    )


class PairDeviceJob:
    """Async job: pairing I/O on a worker, bus emit on the main thread."""

    __slots__ = ("_controller", "__weakref__")

    def __init__(self, controller: SimulationController) -> None:
        self._controller = controller

    def on_completed(self, result: object) -> None:
        model = self._controller.model
        if not isinstance(model, CoreRuntimeModel):
            logger.warning(
                "Controller: model type mismatch",
                model_type=type(model).__name__,
            )
            return
        if not isinstance(result, PairDeviceOutcome):
            logger.error(
                "SimulationController: unexpected pair_device result type",
                result_type=type(result).__name__,
            )
            return
        pair_device_work.apply_main_thread(model, result)

    def on_failed(self, error: JobError) -> None:
        log_pair_device_job_failure(error)


def log_refresh_device_list_job_failure(error: JobError) -> None:
    """Log a failed refresh-device-list async job."""
    logger.error(
        "SimulationController: refresh_device_list job failed",
        message=error.message,
        return_code=error.return_code,
        traceback=error.traceback or None,
    )


class RefreshDeviceListJob:
    """Async job: ADB list query on a worker, view update on the main thread."""

    __slots__ = ("_controller", "__weakref__")

    def __init__(self, controller: SimulationController) -> None:
        self._controller = controller

    def on_completed(self, result: object) -> None:
        if not isinstance(self._controller.model, CoreRuntimeModel):
            logger.warning(
                "Controller: model type mismatch",
                model_type=type(self._controller.model).__name__,
            )
            return
        if not isinstance(result, list):
            logger.error(
                "SimulationController: unexpected refresh_device_list result type",
                result_type=type(result).__name__,
            )
            return
        for item in result:
            if not isinstance(item, Phone):
                logger.error(
                    "SimulationController: refresh list contained non-Phone",
                    item_type=type(item).__name__,
                )
                return
        from gui.window import MainWindow

        view = self._controller.view
        if not isinstance(view, MainWindow):
            logger.warning(
                "Controller: view type mismatch",
                view_type=type(view).__name__,
            )
            return
        device_ids = [d.descriptor.id for d in result]
        logger.info(
            "SimulationController: known devices listed (async)",
            device_count=len(device_ids),
            device_ids=device_ids,
        )
        view.on_devices_updated(device_ids)

    def on_failed(self, error: JobError) -> None:
        log_refresh_device_list_job_failure(error)
