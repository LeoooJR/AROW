"""
ADB and device list orchestration (server lifecycle, pairing, list refresh, core device signals).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from controller.adb_job_callbacks import AdbAsyncJobCallbacks
from controller.helper import validate_model, validate_view
from core.models import CoreRuntimeModel
from core.signals import (
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    DeviceAuthentificationFailedPayload,
    DeviceAuthentificationSucceededPayload,
    DevicesUpdatedPayload,
)
from gui.signals import view_signals
from gui.window import MainWindow
from logger import logger

if TYPE_CHECKING:
    from controller.app_controller import AppController


class AdbSubController:
    """Subcontroller for ADB server and device list flows (no own AsyncRunner)."""

    def __init__(self, app: AppController) -> None:
        self._app = app
        self._async_job_callbacks: AdbAsyncJobCallbacks = (
            AdbAsyncJobCallbacks.for_subcontroller(self)
        )

    @property
    def model(self) -> CoreRuntimeModel:
        return self._app.model

    @property
    def view(self) -> MainWindow:
        return self._app.view

    def _submit_model_async_call(self, *args, **kwargs):
        return self._app._submit_model_async_call(*args, **kwargs)

    def connect_view_signals(self) -> None:
        """Connect view signals for ADB and pairing (called from AppController)."""
        view_signals.AuthentificationConfirmed.connect(
            self._on_authentification_confirmed
        )
        view_signals.RefreshDeviceListRequested.connect(
            self._on_refresh_device_list_requested
        )

    def connect_model_signals(self) -> None:
        """Subscribe to core ADB and device events."""
        self.model.subscribe(CoreSignal.ADB_SERVER_STARTED, self._on_adb_server_started)
        self.model.subscribe(CoreSignal.ADB_SERVER_STOPPED, self._on_adb_server_stopped)
        self.model.subscribe(CoreSignal.DEVICES_UPDATED, self._on_devices_updated)
        self.model.subscribe(
            CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED,
            self._on_device_authentification_succeeded,
        )
        self.model.subscribe(
            CoreSignal.DEVICE_AUTHENTIFICATION_FAILED,
            self._on_device_authentification_failed,
        )

    def run_startup(self) -> None:
        """
        Start core runtime on a worker and apply results on the main thread when done.

        Invoked from AppController after all signal wiring is in place.
        """
        self._startup_core_runtime()

    @validate_model
    def _startup_core_runtime(self) -> None:
        self._submit_model_async_call(
            name="startup_core_runtime",
            fn=self.model.startup,
            description="Startup the core runtime",
            job_type="thread",
            coalesce_key="none",
            on_completed=self._async_job_callbacks.startup.on_completed,
            on_failed=self._async_job_callbacks.startup.on_failed,
        )

    @validate_model
    def _on_authentification_confirmed(
        self, ip: str, port: str, association_code: str
    ) -> None:
        """Authentification workflow runs on a worker thread."""
        logger.info(
            "AdbSubController: authentification workflow confirmed",
            ip=ip,
            port=port,
            association_code=association_code,
        )
        port_i = int(port)
        self._submit_model_async_call(
            name="authentification_workflow",
            fn=self.model.authentificate_device,
            args=(ip, port_i, association_code),
            description="Autehntificate a device over ADB",
            job_type="thread",
            coalesce_key="device",
            on_completed=self._async_job_callbacks.authentificate_device.on_completed,
            on_failed=self._async_job_callbacks.authentificate_device.on_failed,
        )

    @validate_model
    def _on_refresh_device_list_requested(self) -> None:
        """ADB list query on a worker."""
        logger.info("AdbSubController: refresh device list requested")
        self._submit_model_async_call(
            name="refresh_device_list",
            fn=self.model.refresh_known_devices,
            description="Refresh device list from ADB",
            job_type="thread",
            coalesce_key="device",
            on_completed=self._async_job_callbacks.refresh_device_list.on_completed,
            on_failed=self._async_job_callbacks.refresh_device_list.on_failed,
        )

    @validate_view
    def _on_adb_server_started(self, payload: AdbServerStartedPayload) -> None:
        logger.info(
            "AdbSubController: ADB server started",
            adb_binary=str(payload.adb_binary),
        )
        self.view.forward_adb_server_started()

    @validate_view
    def _on_adb_server_stopped(self, payload: AdbServerStoppedPayload) -> None:
        logger.info(
            "AdbSubController: ADB server stopped",
            adb_binary=str(payload.adb_binary),
        )
        self.view.forward_adb_server_stopped()

    @validate_view
    def _on_devices_updated(self, payload: DevicesUpdatedPayload) -> None:
        device_ids = [d.descriptor.id for d in payload.devices]
        logger.info(
            "AdbSubController: devices updated",
            device_count=len(device_ids),
            device_ids=device_ids,
        )
        self.view.forward_devices_updated(device_ids)

    @validate_view
    def _on_device_authentification_succeeded(
        self, payload: DeviceAuthentificationSucceededPayload
    ) -> None:
        desc = payload.phone.descriptor
        logger.success(
            "AdbSubController: device authentification succeeded",
            device_id=desc.id,
            device_name=desc.name,
        )
        self.view.forward_device_authentification_succeeded(desc.id)

    @validate_view
    def _on_device_authentification_failed(
        self, payload: DeviceAuthentificationFailedPayload
    ) -> None:
        logger.warning(
            "AdbSubController: device authentification failed",
            ip=payload.ip,
            port=payload.port,
            association_code=payload.association_code,
        )
        self.view.forward_device_authentification_failed(
            payload.ip, payload.port, payload.association_code
        )
