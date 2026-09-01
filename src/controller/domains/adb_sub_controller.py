"""
ADB and device list orchestration (server lifecycle, pairing, list refresh, core device signals).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

from controller.cron import CronJob
from controller.domains.app_sub_controller import AppSubController
from controller.runner import JobSpecification
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
from gui.windows import MainWindow
from logger import logger

if TYPE_CHECKING:
    from controller.orchestration.app_controller import AppController

_REFRESH_DEVICE_LIST_INTERVAL_MS = 30000


class AdbSubController(AppSubController):
    """Subcontroller for ADB server and device list flows (no own AsyncRunner)."""

    def _submit_model_entrypoint_async_call(self, *args, **kwargs):
        return self._app._submit_model_entrypoint_async_call(*args, **kwargs)

    def declare_cron_jobs(self) -> tuple[CronJob, ...]:
        """Declare periodic ADB discovery through the app-owned cron manager."""
        return (self._refresh_device_list_cron_job(),)

    def _refresh_device_list_cron_job(self) -> CronJob:
        return CronJob(
            interval_ms=_REFRESH_DEVICE_LIST_INTERVAL_MS,
            specification=JobSpecification(
                name="refresh_device_list",
                fn=self.model_entrypoint.refresh_known_devices,
                description="Refresh device list from ADB",
                type="thread",
                coalesce_key="refresh_device_list",
                at_most_once=True,
            ),
            on_completed=self.model_entrypoint.apply_result,
            on_failed=self.model_entrypoint.apply_failure,
        )

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

    def run_shutdown(self) -> None:
        """Stop the core ADB runtime through the shared asynchronous runner."""
        self._submit_model_entrypoint_async_call(
            name="close_core_runtime",
            fn=self.model_entrypoint.close_core_runtime,
            description="Stop ADB server and detach core runtime",
            job_type="thread",
            coalesce_key="close",
            on_completed=self.model_entrypoint.apply_result,
            on_failed=self.model_entrypoint.apply_failure,
        )

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

    @Slot()
    def _on_refresh_device_list_requested(self) -> None:
        """ADB list query on a worker."""
        logger.debug("Device list refresh queued")
        self._app._submit_cron_job(self._refresh_device_list_cron_job())

    @Slot(str)
    def _on_remove_device_requested(self, id: str) -> None:
        """Remove device from ADB on a worker."""
        pass  # TODO: Implement the thread job to remove device

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

    def _on_adb_server_started(self, payload: AdbServerStartedPayload) -> None:
        self.view.forward_adb_server_started()

    def _on_adb_server_stopped(self, payload: AdbServerStoppedPayload) -> None:
        self.view.forward_adb_server_stopped()

    def _on_devices_updated(self, payload: DevicesUpdatedPayload) -> None:
        self.view.forward_devices_updated(
            payload.devices,
            dict(payload.device_id_rebindings),
        )

    def _on_device_authentification_succeeded(
        self, payload: DeviceAuthentificationSucceededPayload
    ) -> None:
        descriptor = payload.device
        self.view.forward_device_authentification_succeeded(descriptor)

    def _on_device_authentification_failed(
        self, payload: DeviceAuthentificationFailedPayload
    ) -> None:
        self.view.forward_device_authentification_failed(
            ip=payload.ip,
            port=payload.port,
            association_code=payload.association_code,
            reason=payload.reason,
        )
