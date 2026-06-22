"""Tests for MapSubController async map rendering wiring."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from controller.domains.map_sub_controller import MapSubController
from controller.orchestration.app_controller import AppController
from controller.runner import JobError
from core.entrypoint import ModelEntrypoint
from core.signals import MapRenderedPayload, MapRenderFailedPayload
from core.work.render_map_work import RenderMapOutcome

pytestmark = [pytest.mark.async_jobs]


@pytest.fixture(scope="session", autouse=True)
def _qt_core_app() -> None:
    app = QApplication.instance()
    if app is None:
        QApplication([])


class _AppStub:
    """Minimal AppController stand-in for MapSubController unit tests."""

    def __init__(self) -> None:
        self.model_entrypoint = ModelEntrypoint()
        self.view = MagicMock()
        self.submitted: list[dict[str, Any]] = []

    def _submit_model_entrypoint_async_call(self, **kwargs: Any) -> None:
        self.submitted.append(kwargs)


def _patch_controller_type_checks(
    monkeypatch: pytest.MonkeyPatch, probe: _AppStub
) -> None:
    real_isinstance = builtins.isinstance

    def _isinstance(obj, cls) -> bool:
        cls_name = getattr(cls, "__name__", "")
        if cls_name == "MainWindow" and obj is probe.view:
            return True
        if cls_name == "ModelEntrypoint" and obj is probe.model_entrypoint:
            return True
        return real_isinstance(obj, cls)

    monkeypatch.setattr(builtins, "isinstance", _isinstance)


def _make_map_sub_controller(app: _AppStub) -> MapSubController:
    return MapSubController(cast(AppController, app))


def test_on_render_map_requested_submits_process_job() -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)

    map_controller._on_render_map_requested("sim-1")

    assert len(app.submitted) == 1
    submit_kwargs = app.submitted[0]
    assert submit_kwargs["name"] == "render_map"
    assert submit_kwargs["job_type"] == "process"
    assert submit_kwargs["coalesce_key"] == "render_map:sim-1"
    assert submit_kwargs["fn"] == app.model_entrypoint.render_map
    assert submit_kwargs["args"] == ("sim-1", app.model_entrypoint.application_dir)
    assert (
        submit_kwargs["on_completed"]
        == map_controller._async_job_callbacks.render_map.on_completed
    )
    assert (
        submit_kwargs["on_failed"]
        == map_controller._async_job_callbacks.render_map.on_failed
    )


def test_on_render_map_requested_reuses_existing_html_without_submitting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)
    simulation_id = "sim-1"
    html_path = (
        app.model_entrypoint.application_dir
        / "simulations"
        / simulation_id
        / "map"
        / f"{simulation_id}.html"
    )
    monkeypatch.setattr(Path, "exists", lambda self: self == html_path)

    map_controller._on_render_map_requested(simulation_id)

    assert app.submitted == []
    app.view.forward_map_rendered.assert_called_once_with(simulation_id, html_path)


def test_render_callback_on_completed_applies_result() -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)
    apply_calls: list[object] = []
    app.model_entrypoint.apply_result = lambda result: apply_calls.append(result)  # type: ignore[method-assign]
    callback = map_controller._async_job_callbacks.render_map
    outcome = RenderMapOutcome(simulation_id="sim-1", html_path=Path("/tmp/sim-1.html"))

    callback.on_completed(outcome)

    assert apply_calls == [outcome]


def test_render_callback_on_failed_delegates_to_apply_failure() -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)
    apply_calls: list[object] = []
    app.model_entrypoint.apply_failure = lambda error: apply_calls.append(error)  # type: ignore[method-assign]
    callback = map_controller._async_job_callbacks.render_map
    error = JobError(
        message="Job failed: render_map: boom",
        traceback="",
        origin="render_map",
    )

    callback.on_failed(error)

    assert apply_calls == [error]


def test_on_map_rendered_forwards_to_view(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _AppStub()
    _patch_controller_type_checks(monkeypatch, app)
    map_controller = _make_map_sub_controller(app)
    payload = MapRenderedPayload(
        simulation_id="sim-1", html_path=Path("/tmp/sim-1.html")
    )

    map_controller._on_map_rendered(payload)

    app.view.forward_map_rendered.assert_called_once_with(
        "sim-1",
        payload.html_path,
    )


def test_on_map_render_failed_forwards_to_view(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _AppStub()
    _patch_controller_type_checks(monkeypatch, app)
    map_controller = _make_map_sub_controller(app)
    payload = MapRenderFailedPayload(simulation_id="sim-1", reason="failed")

    map_controller._on_map_render_failed(payload)

    app.view.forward_map_render_failed.assert_called_once_with("sim-1", "failed")
