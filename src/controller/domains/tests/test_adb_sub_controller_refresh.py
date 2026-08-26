"""Tests for AdbSubController device-list refresh wiring and at_most_once submission."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from controller.cron import CronJob
from controller.domains.adb_sub_controller import (
    _REFRESH_DEVICE_LIST_INTERVAL_MS,
    AdbSubController,
)
from controller.orchestration.app_controller import AppController
from controller.runner import JobError, JobHandler, JobHandlerSignals
from core.devices.phone import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import DevicesUpdatedPayload
from core.work.refresh_known_devices_work import RefreshKnownDevicesOutcome
from core.work.startup_work import StartupOutcome

pytestmark = [pytest.mark.async_jobs]


@pytest.fixture(scope="session", autouse=True)
def _qt_core_app() -> None:
    """Ensure QTimer is available when AdbSubController constructs repeat timers."""

    app = QApplication.instance()
    if app is None:
        QApplication([])


class _AppStub:
    """Minimal AppController stand-in for AdbSubController unit tests."""

    def __init__(self) -> None:
        self.model_entrypoint = ModelEntrypoint()
        self.view = MagicMock()
        self.submitted: list[dict[str, Any]] = []
        self.cron_submitted: list[CronJob] = []
        self.handle_signals: dict[str, JobHandlerSignals] = {}
        self.runner = MagicMock()
        self.runner.bind_handle_signals = self._bind_handle_signals

    def _bind_handle_signals(self, handle: JobHandler) -> JobHandlerSignals:
        return self.handle_signals[handle.job_id]

    def _submit_model_entrypoint_async_call(self, **kwargs: Any) -> JobHandler:
        self.submitted.append(kwargs)
        handle = JobHandler(job_id=f"job-{len(self.submitted)}", name=kwargs["name"])
        signals = JobHandlerSignals()
        self.handle_signals[handle.job_id] = signals
        if on_completed := kwargs.get("on_completed"):
            signals.Completed.connect(on_completed)
        if on_failed := kwargs.get("on_failed"):
            signals.Failed.connect(on_failed)
        if on_cancelled := kwargs.get("on_cancelled"):
            signals.Cancelled.connect(on_cancelled)
        return handle

    def _submit_cron_job(self, job: CronJob) -> JobHandler:
        self.cron_submitted.append(job)
        handle = JobHandler(
            job_id=f"cron-{len(self.cron_submitted)}",
            name=job.specification.name,
        )
        signals = JobHandlerSignals()
        self.handle_signals[handle.job_id] = signals
        if job.on_completed is not None:
            signals.Completed.connect(job.on_completed)
        if job.on_failed is not None:
            signals.Failed.connect(job.on_failed)
        if job.on_cancelled is not None:
            signals.Cancelled.connect(job.on_cancelled)
        return handle


def _make_adb_sub_controller(app: _AppStub) -> AdbSubController:
    return AdbSubController(cast(AppController, app))


def test_declares_periodic_async_device_refresh() -> None:
    app = _AppStub()
    adb = _make_adb_sub_controller(app)

    jobs = adb.declare_cron_jobs()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.interval_ms == _REFRESH_DEVICE_LIST_INTERVAL_MS
    assert job.specification.name == "refresh_device_list"
    assert job.specification.type == "thread"
    assert job.specification.coalesce_key == "refresh_device_list"
    assert job.specification.at_most_once is True
    assert job.specification.fn == app.model_entrypoint.refresh_known_devices
    assert job.specification.description == "Refresh device list from ADB"
    assert job.on_completed == app.model_entrypoint.apply_result
    assert job.on_failed == app.model_entrypoint.apply_failure


def test_on_refresh_device_list_requested_submits_async_job() -> None:
    app = _AppStub()
    adb = _make_adb_sub_controller(app)

    adb._on_refresh_device_list_requested()

    assert len(app.cron_submitted) == 1
    assert app.cron_submitted[0] == adb.declare_cron_jobs()[0]


def test_refresh_submission_completed_applies_result() -> None:
    app = _AppStub()
    apply_calls: list[object] = []
    app.model_entrypoint.apply_result = lambda result: apply_calls.append(result)  # type: ignore[method-assign]
    adb = _make_adb_sub_controller(app)
    outcome = RefreshKnownDevicesOutcome(devices=[Phone(id="device-1", state="device")])

    adb._on_refresh_device_list_requested()
    app.handle_signals["cron-1"].Completed.emit(outcome)

    assert apply_calls == [outcome]


def test_refresh_submission_failed_applies_failure() -> None:
    app = _AppStub()
    failure_calls: list[object] = []
    app.model_entrypoint.apply_failure = lambda error: failure_calls.append(error)  # type: ignore[method-assign]
    adb = _make_adb_sub_controller(app)
    error = JobError(
        message="Job failed: refresh_device_list: ADB unavailable",
        traceback="",
        origin="refresh_device_list",
    )

    adb._on_refresh_device_list_requested()
    app.handle_signals["cron-1"].Failed.emit(error)

    assert failure_calls == [error]


def test_startup_applies_before_enqueuing_host_identity() -> None:
    app = _AppStub()
    events: list[str] = []
    app.model_entrypoint.apply_result = lambda result: events.append("applied")  # type: ignore[method-assign]
    adb = _make_adb_sub_controller(app)
    adb._enqueue_host_install_identity_job = lambda: events.append("host-enqueued")  # type: ignore[method-assign]
    outcome = StartupOutcome()

    adb._startup_core_runtime()
    app.handle_signals["job-1"].Completed.emit(outcome)

    assert events == ["applied", "host-enqueued"]
    assert app.submitted[0]["on_completed"] == app.model_entrypoint.apply_result
    assert app.submitted[0]["on_failed"] == app.model_entrypoint.apply_failure


def test_startup_does_not_enqueue_host_identity_for_unsupported_payload() -> None:
    app = _AppStub()
    events: list[str] = []
    app.model_entrypoint.apply_result = lambda result: events.append("applied")  # type: ignore[method-assign]
    adb = _make_adb_sub_controller(app)
    adb._enqueue_host_install_identity_job = lambda: events.append("host-enqueued")  # type: ignore[method-assign]

    adb._startup_core_runtime()
    app.handle_signals["job-1"].Completed.emit(object())

    assert events == ["applied"]


@pytest.mark.parametrize("terminal_signal", ["Completed", "Failed"])
def test_close_hook_runs_after_core_apply(
    terminal_signal: str,
) -> None:
    app = _AppStub()
    events: list[str] = []
    app.model_entrypoint.apply_result = lambda result: events.append("applied")  # type: ignore[method-assign]
    app.model_entrypoint.apply_failure = lambda error: events.append("failed")  # type: ignore[method-assign]
    adb = _make_adb_sub_controller(app)

    adb._enqueue_close_core_runtime(after_apply=lambda: events.append("hook"))
    payload = (
        object()
        if terminal_signal == "Completed"
        else JobError(message="boom", traceback="", origin="close_core_runtime")
    )
    getattr(app.handle_signals["job-1"], terminal_signal).emit(payload)

    expected_apply = "applied" if terminal_signal == "Completed" else "failed"
    assert events == [expected_apply, "hook"]
    assert adb._pending_after_close_apply is None


def test_on_devices_updated_forwards_device_id_rebindings_to_view() -> None:
    app = _AppStub()
    adb = _make_adb_sub_controller(app)
    phone = Phone(id="device-1", state="device", model="Pixel")
    payload = DevicesUpdatedPayload(
        devices=[phone.serialize()],
        device_id_rebindings={"old-device-1": "device-1"},
    )

    adb._on_devices_updated(payload)

    app.view.forward_devices_updated.assert_called_once_with(
        payload.devices,
        {"old-device-1": "device-1"},
    )
