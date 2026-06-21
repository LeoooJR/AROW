"""Tests for AdbSubController device-list refresh wiring and at_most_once submission."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

import controller.domains.adb_sub_controller as adb_sub_controller_module
from controller.core_work_callbacks import RefreshDeviceListCallback
from controller.domains.adb_sub_controller import (
    _REFRESH_DEVICE_LIST_INTERVAL_MS,
    AdbSubController,
)
from controller.orchestration.app_controller import AppController
from controller.runner import JobError
from core.devices import Phone
from core.entrypoint import ModelEntrypoint
from core.signals import DevicesUpdatedPayload
from core.work.refresh_known_devices_work import RefreshKnownDevicesOutcome

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

    def _submit_model_entrypoint_async_call(self, **kwargs: Any) -> None:
        self.submitted.append(kwargs)


def _make_adb_sub_controller(app: _AppStub) -> AdbSubController:
    return AdbSubController(cast(AppController, app))


def _patch_controller_type_checks(monkeypatch: pytest.MonkeyPatch, probe: _AppStub) -> None:
    real_isinstance = builtins.isinstance

    def _isinstance(obj: object, cls: object) -> bool:
        cls_name = getattr(cls, "__name__", "")
        if cls_name == "MainWindow" and obj is probe.view:
            return True
        if cls_name == "ModelEntrypoint" and obj is probe.model_entrypoint:
            return True
        return real_isinstance(obj, cls)

    monkeypatch.setattr(builtins, "isinstance", _isinstance)


@pytest.fixture
def patch_repeat_timer(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Capture repeat() wiring without starting a real periodic QTimer."""

    captured: dict[str, Any] = {}

    def fake_repeat(ms: int) -> Callable[[Callable[..., Any]], MagicMock]:
        def inner(function: Callable[..., Any]) -> MagicMock:
            captured["interval_ms"] = ms
            captured["fn"] = function
            return MagicMock(name="refresh_device_list_timer")

        return inner

    monkeypatch.setattr(adb_sub_controller_module, "repeat", fake_repeat)
    return captured


def test_init_wires_repeat_timer_for_refresh(
    patch_repeat_timer: dict[str, Any],
) -> None:
    app = _AppStub()
    adb = _make_adb_sub_controller(app)

    assert patch_repeat_timer["interval_ms"] == _REFRESH_DEVICE_LIST_INTERVAL_MS
    wired_refresh_handler = patch_repeat_timer["fn"]
    assert getattr(wired_refresh_handler, "__self__", None) is adb
    assert (
        wired_refresh_handler.__name__ == adb._on_refresh_device_list_requested.__name__
    )


def test_on_refresh_device_list_requested_submits_async_job(
    patch_repeat_timer: dict[str, Any],
) -> None:
    app = _AppStub()
    adb = _make_adb_sub_controller(app)

    adb._on_refresh_device_list_requested()

    assert len(app.submitted) == 1
    submit_kwargs = app.submitted[0]
    assert submit_kwargs["name"] == "refresh_device_list"
    assert submit_kwargs["job_type"] == "thread"
    assert submit_kwargs["coalesce_key"] == "refresh_device_list"
    assert submit_kwargs["at_most_once"] is True
    assert submit_kwargs["fn"] == app.model_entrypoint.refresh_known_devices
    assert submit_kwargs["description"] == "Refresh device list from ADB"
    assert (
        submit_kwargs["on_completed"]
        == adb._async_job_callbacks.refresh_device_list.on_completed
    )
    assert (
        submit_kwargs["on_failed"]
        == adb._async_job_callbacks.refresh_device_list.on_failed
    )


def test_refresh_callback_on_completed_applies_result(
    patch_repeat_timer: dict[str, Any],
) -> None:
    app = _AppStub()
    adb = _make_adb_sub_controller(app)
    apply_calls: list[object] = []
    app.model_entrypoint.apply_result = lambda result: apply_calls.append(result)  # type: ignore[method-assign]
    callback = adb._async_job_callbacks.refresh_device_list
    outcome = RefreshKnownDevicesOutcome(devices=[Phone(id="device-1", state="device")])

    callback.on_completed(outcome)

    assert apply_calls == [outcome]


def test_refresh_callback_on_failed_applies_failure(
    patch_repeat_timer: dict[str, Any],
) -> None:
    app = _AppStub()
    adb = _make_adb_sub_controller(app)
    failure_calls: list[object] = []
    app.model_entrypoint.apply_failure = lambda error: failure_calls.append(error)  # type: ignore[method-assign]
    callback = RefreshDeviceListCallback(adb)
    error = JobError(
        message="Job failed: refresh_device_list: ADB unavailable",
        traceback="",
        origin="refresh_device_list",
    )

    callback.on_failed(error)

    assert failure_calls == [error]


def test_on_devices_updated_forwards_device_id_rebindings_to_view(
    monkeypatch: pytest.MonkeyPatch,
    patch_repeat_timer: dict[str, Any],
) -> None:
    app = _AppStub()
    adb = _make_adb_sub_controller(app)
    _patch_controller_type_checks(monkeypatch, app)
    payload = DevicesUpdatedPayload(
        devices=[Phone(id="device-1", state="device", model="Pixel")],
        device_id_rebindings={"old-device-1": "device-1"},
    )

    adb._on_devices_updated(payload)

    app.view.forward_devices_updated.assert_called_once_with(
        [vars(payload.devices[0].descriptor)],
        {"old-device-1": "device-1"},
    )
