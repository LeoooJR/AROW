"""
ADB and device list orchestration (server lifecycle, pairing, list refresh, core device signals).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Slot

from controller.domains.app_sub_controller import AppSubController
from controller.helper import repeat, validate_model_entrypoint, validate_view
from core.signals import (
    AdbServerStartedPayload,
    AdbServerStoppedPayload,
    CoreSignals,
    DeviceAuthentificationFailedPayload,
    DeviceAuthentificationSucceededPayload,
    DevicesUpdatedPayload,
)
from core.work.startup_work import StartupOutcome
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
        self._refresh_device_list_timer: QTimer = repeat(
            _REFRESH_DEVICE_LIST_INTERVAL_MS
        )(self._on_refresh_device_list_requested)
        # One-shot hook after CloseCoreRuntime apply (e.g. quit a nested QEventLoop).
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
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.ADB_SERVER_STARTED, self._on_adb_server_started
        )
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.ADB_SERVER_STOPPED, self._on_adb_server_stopped
        )
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.DEVICES_UPDATED, self._on_devices_updated
        )
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.DEVICE_AUTHENTIFICATION_SUCCEEDED,
            self._on_device_authentification_succeeded,
        )
        self.model_entrypoint.signal_bus.subscribe(
            CoreSignals.DEVICE_AUTHENTIFICATION_FAILED,
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
        handle = self._submit_model_entrypoint_async_call(
            name="startup_core_runtime",
            fn=self.model_entrypoint.startup,
            description="Startup the core runtime",
            job_type="thread",
            coalesce_key="startup",
            on_completed=self.model_entrypoint.apply_result,
            on_failed=self.model_entrypoint.apply_failure,
        )
        if handle is not None:
            handle_signals = self._app.runner.bind_handle_signals(handle)
            # Connected after apply_result so host identity starts only after startup
            # state and signals have been applied on the Qt main thread.
            handle_signals.Completed.connect(self._on_startup_core_runtime_applied)

    @validate_model_entrypoint
    def _enqueue_host_install_identity_job(self) -> None:
        """
        After startup apply finishes, persist/load install UUID off the main thread and
        attach ``stable_key`` on completion (serialized after core runtime startup).
        """
        self._submit_model_entrypoint_async_call(
            name="host_install_identity",
            fn=self.model_entrypoint.run_host_install_identity,
            description="Load or create persisted host install UUID",
            job_type="thread",
            coalesce_key="host_install_identity",
            on_completed=self.model_entrypoint.apply_result,
            on_failed=self.model_entrypoint.apply_failure,
        )

    ### Slots ###

    @validate_model_entrypoint
    @Slot(str, str, str)
    def _on_authentification_confirmed(
        self, ip: str, port: str, association_code: str
    ) -> None:
        """Authentification workflow runs on a worker thread."""
        logger.debug(
            "Device pairing workflow queued",
            ip=ip,
            port=port,
            association_code=association_code,
        )
        _port = int(port)
        self._submit_model_entrypoint_async_call(
            name="authentification_workflow",
            fn=self.model_entrypoint.authentificate_device,
            args=(ip, _port, association_code),
            description="Authenticate a device over ADB",
            job_type="thread",
            coalesce_key="authentification",
            on_completed=self.model_entrypoint.apply_result,
            on_failed=self.model_entrypoint.apply_failure,
        )

    @validate_model_entrypoint
    @Slot()
    def _on_refresh_device_list_requested(self) -> None:
        """ADB list query on a worker."""
        logger.debug("Device list refresh queued")
        self._submit_model_entrypoint_async_call(
            name="refresh_device_list",
            fn=self.model_entrypoint.refresh_known_devices,
            description="Refresh device list from ADB",
            job_type="thread",
            coalesce_key="refresh_device_list",
            at_most_once=True,
            on_completed=self.model_entrypoint.apply_result,
            on_failed=self.model_entrypoint.apply_failure,
        )

    @Slot(str)
    def _on_remove_device_requested(self, id: str) -> None:
        """Remove device from ADB on a worker."""
        pass  # TODO: Implement the thread job to remove device

    @validate_model_entrypoint
    def _enqueue_close_core_runtime(
        self,
        *,
        after_apply: Callable[[], None] | None = None,
    ) -> None:
        """Stop ADB on a worker and apply its outcome on the main thread."""
        self._pending_after_close_apply = after_apply
        handle = self._submit_model_entrypoint_async_call(
            name="close_core_runtime",
            fn=self.model_entrypoint.close_core_runtime,
            description="Stop ADB server and detach core runtime",
            job_type="thread",
            coalesce_key="close",
            on_completed=self.model_entrypoint.apply_result,
            on_failed=self.model_entrypoint.apply_failure,
        )
        if handle is not None:
            handle_signals = self._app.runner.bind_handle_signals(handle)
            # These are connected after the core appliers above, so the shutdown
            # waiter is released only once main-thread application has finished.
            handle_signals.Completed.connect(self._on_close_core_runtime_applied)
            handle_signals.Failed.connect(self._on_close_core_runtime_applied)

    @Slot(object)
    def _on_startup_core_runtime_applied(self, result: object) -> None:
        """Chain host identity only after a validated startup outcome was applied."""
        if not isinstance(result, StartupOutcome):
            logger.error(
                "Host identity setup skipped because startup returned an unexpected result",
                result_type=type(result).__name__,
            )
            return
        self._enqueue_host_install_identity_job()

    @Slot(object)
    def _on_close_core_runtime_applied(self, _result_or_error: object) -> None:
        """Consume the one-shot shutdown hook after close success or failure apply."""
        hook = self._pending_after_close_apply
        self._pending_after_close_apply = None
        if hook is not None:
            hook()

    @validate_view
    def _on_adb_server_started(self, payload: AdbServerStartedPayload) -> None:
        self.view.forward_adb_server_started()

    @validate_view
    def _on_adb_server_stopped(self, payload: AdbServerStoppedPayload) -> None:
        self.view.forward_adb_server_stopped()

    @validate_view
    def _on_devices_updated(self, payload: DevicesUpdatedPayload) -> None:
        self.view.forward_devices_updated(
            payload.devices,
            dict(payload.device_id_rebindings),
        )

    @validate_view
    def _on_device_authentification_succeeded(
        self, payload: DeviceAuthentificationSucceededPayload
    ) -> None:
        descriptor = payload.device
        self.view.forward_device_authentification_succeeded(descriptor)

    @validate_view
    def _on_device_authentification_failed(
        self, payload: DeviceAuthentificationFailedPayload
    ) -> None:
        self.view.forward_device_authentification_failed(
            ip=payload.ip,
            port=payload.port,
            association_code=payload.association_code,
            reason=payload.reason,
        )
