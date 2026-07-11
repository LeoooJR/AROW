from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from controller.core_work_callbacks import (
    AuthentificateDeviceCallback,
    CloseCoreRuntimeCallback,
)
from controller.runner import JobError
from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignal,
    CoreSignals,
    DeviceAuthentificationFailedPayload,
)
from core.work.authentificate_device_work import DeviceAuthentificationError


def test_authentificate_device_on_failed_delegates_to_apply_failure() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    subcontroller = MagicMock()
    subcontroller.model_entrypoint = model_entrypoint
    callback = AuthentificateDeviceCallback(subcontroller)
    auth_error = DeviceAuthentificationError(
        ip="10.0.0.5",
        port=37777,
        association_code="123456",
        reason="Invalid IPv4 address",
    )
    error = JobError(
        message="Job failed: authentification_workflow: Invalid IPv4 address",
        traceback="",
        exception=auth_error,
        exception_type=type(auth_error).__qualname__,
        origin="authentification_workflow",
    )

    callback.on_failed(error)

    assert emitted == [
        (
            CoreSignals.DEVICE_AUTHENTIFICATION_FAILED,
            DeviceAuthentificationFailedPayload(
                ip="10.0.0.5",
                port=37777,
                association_code="123456",
                reason="Invalid IPv4 address",
            ),
        )
    ]


def test_close_on_failed_consumes_pending_shutdown_hook() -> None:
    hook_calls: list[None] = []

    def hook() -> None:
        hook_calls.append(None)

    subcontroller = MagicMock()
    subcontroller.model_entrypoint = ModelEntrypoint()
    subcontroller._pending_after_close_apply = hook
    callback = CloseCoreRuntimeCallback(subcontroller)

    callback.on_failed(
        JobError(
            message="Job failed: close_core_runtime: boom",
            traceback="",
            origin="close_core_runtime",
        )
    )

    assert hook_calls == [None]
    assert subcontroller._pending_after_close_apply is None
