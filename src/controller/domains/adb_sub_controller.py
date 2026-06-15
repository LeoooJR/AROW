"""
ADB and device list orchestration (server lifecycle, pairing, list refresh, core device signals).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer

from controller.core_work_callbacks import (
    AdbAsyncJobCallbacks,
    AuthentificateDeviceCallback,
    HostInstallIdentityCallback,
    RefreshDeviceListCallback,
    StartupCoreRuntimeCallback,
)
from controller.domains.app_sub_controller import AppSubController
from controller.helper import repeat, validate_model_entrypoint, validate_view
from core.signals import (
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignal,
    DeviceAuthentificationFailedPayload,
    DeviceAuthentificationSucceededPayload,
    DevicesUpdatedPayload,
)
from gui.signals import signals
from gui.window import MainWindow
from logger import logger

if TYPE_CHECKING:
    from controller.orchestration.app_controller import AppController

_REFRESH_DEVICE_LIST_INTERVAL_MS = 30000


class AdbSubController(AppSubController):
    """Subcontroller for ADB server and device list flows (no own AsyncRunner)."""

    def __init__(self, app: AppController) -> None:
        super().__init__(app)
        self._async_job_callbacks: AdbAsyncJobCallbacks = (
            AdbAsyncJobCallbacks.for_subcontroller(self)
        )
        self._refresh_device_list_timer: QTimer = repeat(
            _REFRESH_DEVICE_LIST_INTERVAL_MS
        )(self._on_refresh_device_list_requested)
        # One-shot hook after CloseCoreRuntime apply (e.g. quit nested QEventLoop); held on
        # self so AsyncRunner slots keep a long-lived CloseCoreRuntimeCallback on AdbAsyncJobCallbacks.
        self._pending_after_close_apply: Callable[[], None] | None = None

    def _submit_model_entrypoint_async_call(self, *args, **kwargs):
        return self._app._submit_model_entrypoint_async_call(*args, **kwargs)

    def connect_view_signals(self) -> None:
        """Connect view signals for ADB and pairing (called from AppController)."""
        signals.DEVICE.AuthentificationConfirmed.connect(
            self._on_authentification_confirmed
        )
        signals.DEVICE.RefreshDeviceListRequested.connect(
            self._on_refresh_device_list_requested
        )
        signals.DEVICE.RemoveDeviceRequested.connect(self._on_remove_device_requested)

    def connect_model_signals(self) -> None:
        """Subscribe to core ADB and device events."""
        self.model_entrypoint.subscribe(
            CoreSignal.ADB_SERVER_STARTED, self._on_adb_server_started
        )
        self.model_entrypoint.subscribe(
            CoreSignal.ADB_SERVER_STOPPED, self._on_adb_server_stopped
        )
        self.model_entrypoint.subscribe(
            CoreSignal.DEVICES_UPDATED, self._on_devices_updated
        )
        self.model_entrypoint.subscribe(
            CoreSignal.DEVICE_AUTHENTIFICATION_SUCCEEDED,
            self._on_device_authentification_succeeded,
        )
        self.model_entrypoint.subscribe(
            CoreSignal.DEVICE_AUTHENTIFICATION_FAILED,
            self._on_device_authentification_failed,
        )

    def run_startup(self) -> None:
        """
        Start core runtime on a worker and apply results on the main thread when done.

        Invoked from AppController after all signal wiring is in place.
        """
        self._startup_core_runtime()

    @validate_model_entrypoint
    def _startup_core_runtime(self) -> None:
        callback: StartupCoreRuntimeCallback = self._async_job_callbacks.startup
        if callback is None:
            raise ValueError("StartupCoreRuntimeCallback is not set")
        self._submit_model_entrypoint_async_call(
            name="startup_core_runtime",
            fn=self.model_entrypoint.startup,
            description="Startup the core runtime",
            job_type="thread",
            coalesce_key="startup",
            on_completed=callback.on_completed,
            on_failed=callback.on_failed,
        )

    @validate_model_entrypoint
    def _enqueue_host_install_identity_job(self) -> None:
        """
        After startup apply finishes, persist/load install UUID off the main thread and
        attach ``stable_key`` on completion (serialized after core runtime startup).
        """
        callback: HostInstallIdentityCallback = (
            self._async_job_callbacks.host_install_identity
        )
        if callback is None:
            raise ValueError("HostInstallIdentityCallback is not set")
        self._submit_model_entrypoint_async_call(
            name="host_install_identity",
            fn=self.model_entrypoint.run_host_install_identity,
            description="Load or create persisted host install UUID",
            job_type="thread",
            coalesce_key="host_install_identity",
            on_completed=callback.on_completed,
            on_failed=callback.on_failed,
        )

    @validate_model_entrypoint
    def _on_authentification_confirmed(
        self, ip: str, port: str, association_code: str
    ) -> None:
        """Authentification workflow runs on a worker thread."""
        logger.debug(
            "AdbSubController: authentification workflow confirmed",
            ip=ip,
            port=port,
            association_code=association_code,
        )
        callback: AuthentificateDeviceCallback = (
            self._async_job_callbacks.authentificate_device
        )
        if callback is None:
            raise ValueError("AuthentificateDeviceCallback is not set")
        _port = int(port)
        self._submit_model_entrypoint_async_call(
            name="authentification_workflow",
            fn=self.model_entrypoint.authentificate_device,
            args=(ip, _port, association_code),
            description="Authenticate a device over ADB",
            job_type="thread",
            coalesce_key="authentification",
            on_completed=callback.on_completed,
            on_failed=callback.on_failed,
        )

    @validate_model_entrypoint
    def _on_refresh_device_list_requested(self) -> None:
        """ADB list query on a worker."""
        logger.debug("AdbSubController: refresh device list requested")
        callback: RefreshDeviceListCallback = (
            self._async_job_callbacks.refresh_device_list
        )
        if callback is None:
            raise ValueError("RefreshDeviceListCallback is not set")
        self._submit_model_entrypoint_async_call(
            name="refresh_device_list",
            fn=self.model_entrypoint.refresh_known_devices,
            description="Refresh device list from ADB",
            job_type="thread",
            coalesce_key="refresh_device_list",
            at_most_once=True,
            on_completed=callback.on_completed,
            on_failed=callback.on_failed,
        )

    def _on_remove_device_requested(self, id: str) -> None:
        """Remove device from ADB on a worker."""
        pass  # TODO: Implement the thread job to remove device

    @validate_model_entrypoint
    def _enqueue_close_core_runtime(
        self,
        *,
        after_apply: Callable[[], None] | None = None,
    ) -> None:
        """Stop ADB on a worker; apply outcome on main thread via callback."""
        self._pending_after_close_apply = after_apply
        callback = self._async_job_callbacks.close
        self._submit_model_entrypoint_async_call(
            name="close_core_runtime",
            fn=self.model_entrypoint.close_core_runtime,
            description="Stop ADB server and detach core runtime",
            job_type="thread",
            coalesce_key="close",
            on_completed=callback.on_completed,
            on_failed=callback.on_failed,
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
        descriptors = [vars(d.descriptor) for d in payload.devices]
        logger.info(
            "AdbSubController: devices updated",
            device_count=len(descriptors),
            device_descriptors=descriptors,
        )
        self.view.forward_devices_updated(descriptors)

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
        self.view.forward_device_authentification_succeeded(vars(desc))

    @validate_view
    def _on_device_authentification_failed(
        self, payload: DeviceAuthentificationFailedPayload
    ) -> None:
        logger.warning(
            "AdbSubController: device authentification failed",
            ip=payload.ip,
            port=payload.port,
            association_code=payload.association_code,
            reason=payload.reason,
        )
        self.view.forward_device_authentification_failed(
            ip=payload.ip,
            port=payload.port,
            association_code=payload.association_code,
            reason=payload.reason,
        )
