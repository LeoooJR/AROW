from __future__ import annotations

from typing import Any

import pytest

from controller.runner import JobError
from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignal,
    CoreSignals,
    DeviceAuthentificationFailedPayload,
    ErrorRaisedPayload,
)
from core.work.authentificate_device_work import DeviceAuthentificationError
from core.work.core_runtime_work import CoreRuntimeWork

pytestmark = [pytest.mark.async_jobs]


def test_apply_failure_routes_auth_error_by_origin() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    auth_error = DeviceAuthentificationError(
        ip="10.0.0.5",
        port=37777,
        association_code="123456",
        reason="Invalid IPv4 address",
    )
    job_error = JobError(
        message="Job failed: authentification_workflow: Invalid IPv4 address",
        traceback="",
        exception=auth_error,
        exception_type=type(auth_error).__qualname__,
        origin="authentification_workflow",
    )

    model_entrypoint.apply_failure(job_error)

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


def test_apply_failure_routes_generic_exception_by_origin() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    generic = RuntimeError("unexpected auth bug")
    job_error = JobError(
        message="Job failed: authentification_workflow: unexpected auth bug",
        traceback="",
        exception=generic,
        exception_type=type(generic).__qualname__,
        origin="authentification_workflow",
    )

    model_entrypoint.apply_failure(job_error)

    assert len(emitted) == 1
    signal, payload = emitted[0]
    assert signal == CoreSignals.ERROR_RAISED
    assert isinstance(payload, ErrorRaisedPayload)
    assert payload.source == "AuthenticateDeviceWork"
    assert payload.message == "unexpected auth bug"
    assert payload.error_type == "RuntimeError"
    assert payload.error_message == "unexpected auth bug"


@pytest.mark.parametrize(
    ("origin", "expected_source"),
    [
        ("startup_core_runtime", "StartupCoreRuntimeWork"),
        ("refresh_device_list", "RefreshKnownDevicesWork"),
        ("host_install_identity", "HostInstallIdentityWork"),
        ("close_core_runtime", "CloseCoreRuntimeWork"),
    ],
)
def test_apply_failure_routes_generic_exception_for_each_work_origin(
    origin: str, expected_source: str
) -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    generic = RuntimeError("worker blew up")
    job_error = JobError(
        message=f"Job failed: {origin}: worker blew up",
        traceback="",
        exception=generic,
        exception_type=type(generic).__qualname__,
        origin=origin,
    )

    model_entrypoint.apply_failure(job_error)

    assert len(emitted) == 1
    signal, payload = emitted[0]
    assert signal == CoreSignals.ERROR_RAISED
    assert isinstance(payload, ErrorRaisedPayload)
    assert payload.source == expected_source
    assert payload.error_type == "RuntimeError"
    assert payload.error_message == "worker blew up"


def test_apply_failure_falls_back_to_exception_type_without_origin() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    auth_error = DeviceAuthentificationError(
        ip="1.2.3.4",
        port=12345,
        association_code="654321",
        reason="wrong pairing code",
    )

    model_entrypoint.apply_failure(auth_error)

    assert emitted == [
        (
            CoreSignals.DEVICE_AUTHENTIFICATION_FAILED,
            DeviceAuthentificationFailedPayload(
                ip="1.2.3.4",
                port=12345,
                association_code="654321",
                reason="wrong pairing code",
            ),
        )
    ]


def test_emit_generic_error_emits_error_raised_payload() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    error = RuntimeError("direct helper test")

    CoreRuntimeWork.emit_generic_error(
        model_entrypoint,
        source="TestSource",
        message="direct helper test",
        error=error,
    )

    assert len(emitted) == 1
    signal, payload = emitted[0]
    assert signal == CoreSignals.ERROR_RAISED
    assert isinstance(payload, ErrorRaisedPayload)
    assert payload.source == "TestSource"
    assert payload.message == "direct helper test"
    assert payload.error_type == "RuntimeError"
    assert payload.error_message == "direct helper test"


def test_apply_failure_uses_generic_handler_for_unknown_job_error() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    job_error = JobError(
        message="Job failed: unknown_job: boom",
        traceback="",
        origin="unknown_job",
    )

    model_entrypoint.apply_failure(job_error)

    assert len(emitted) == 1
    signal, payload = emitted[0]
    assert signal == CoreSignals.ERROR_RAISED
    assert isinstance(payload, ErrorRaisedPayload)
    assert payload.source == "ModelEntrypoint"
    assert payload.message == "Job failed: unknown_job: boom"
