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
from controller.runner import JobError, JobHandler
from core.entrypoint import ModelEntrypoint
from core.signals import (
    MapRenderedPayload,
    MapRenderFailedPayload,
    SimulationDeletedPayload,
)
from core.simulation import Simulation, SimulationRepository
from core.work.render_map_work import RenderMapOutcome

pytestmark = [pytest.mark.async_jobs]


@pytest.fixture(scope="session", autouse=True)
def _qt_core_app() -> None:
    app = QApplication.instance()
    if app is None:
        QApplication([])


class _AppStub:
    """Minimal AppController stand-in for MapSubController unit tests."""

    def __init__(self, tmp_path: Path | None = None) -> None:
        self.model_entrypoint = ModelEntrypoint()
        if tmp_path is not None:
            self.model_entrypoint._simulations = SimulationRepository(
                tmp_path / "simulations"
            )
        self.view = MagicMock()
        self.submitted: list[dict[str, Any]] = []
        self.cancelled_job_ids: list[str] = []
        self.runner = MagicMock()
        self.runner.cancel = lambda job_id: self.cancelled_job_ids.append(job_id)

    def _submit_model_entrypoint_async_call(self, **kwargs: Any) -> JobHandler:
        self.submitted.append(kwargs)
        return JobHandler(job_id="job-1", name=kwargs.get("name", ""))


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


def _add_simulation(
    model_entrypoint: ModelEntrypoint, simulation_id: str
) -> Simulation:
    simulation = Simulation(id=simulation_id)
    model_entrypoint._simulations.add(simulation)
    return simulation


def test_on_render_map_requested_submits_process_job(tmp_path: Path) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    _add_simulation(app.model_entrypoint, "sim-1")

    map_controller._on_render_map_requested("sim-1")

    assert len(app.submitted) == 1
    submit_kwargs = app.submitted[0]
    assert submit_kwargs["name"] == "render_map"
    assert submit_kwargs["job_type"] == "process"
    assert submit_kwargs["coalesce_key"] == "render_map:sim-1"
    assert submit_kwargs["fn"] == app.model_entrypoint.render_map
    assert submit_kwargs["args"] == ("sim-1", app.model_entrypoint.application_dir)
    assert map_controller._render_jobs_by_simulation_id["sim-1"].job_id == "job-1"
    on_completed = submit_kwargs["on_completed"]
    on_failed = submit_kwargs["on_failed"]
    on_cancelled = submit_kwargs["on_cancelled"]
    assert on_completed.func == map_controller._on_render_job_completed
    assert on_completed.args == ("sim-1",)
    assert on_failed.func == map_controller._on_render_job_failed
    assert on_failed.args == ("sim-1",)
    assert on_cancelled.func == map_controller._on_render_job_cancelled
    assert on_cancelled.args == ("sim-1",)


def test_on_render_map_requested_reuses_existing_html_without_submitting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    simulation_id = "sim-1"
    html_path = Path("/tmp/sim-1.html")
    simulation = _add_simulation(app.model_entrypoint, simulation_id)
    simulation.map_file = html_path
    monkeypatch.setattr(Path, "exists", lambda self: self == html_path)

    map_controller._on_render_map_requested(simulation_id)

    assert app.submitted == []
    app.view.forward_map_rendered.assert_called_once_with(simulation_id, html_path)


def test_on_render_map_requested_skips_when_simulation_missing() -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)

    map_controller._on_render_map_requested("sim-1")

    assert app.submitted == []
    app.view.forward_map_rendered.assert_not_called()


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


def test_render_job_callbacks_clear_tracked_handle(tmp_path: Path) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    _add_simulation(app.model_entrypoint, "sim-1")
    map_controller._render_jobs_by_simulation_id["sim-1"] = JobHandler(
        job_id="job-1", name="render_map"
    )
    outcome = RenderMapOutcome(simulation_id="sim-1", html_path=Path("/tmp/sim-1.html"))
    apply_calls: list[object] = []
    app.model_entrypoint.apply_result = lambda result: apply_calls.append(result)  # type: ignore[method-assign]

    map_controller._on_render_job_completed("sim-1", outcome)

    assert apply_calls == [outcome]
    assert "sim-1" not in map_controller._render_jobs_by_simulation_id


def test_render_job_failed_callback_clears_tracked_handle(tmp_path: Path) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    map_controller._render_jobs_by_simulation_id["sim-1"] = JobHandler(
        job_id="job-1", name="render_map"
    )
    error = JobError(message="boom", traceback="", origin="render_map")
    apply_calls: list[object] = []
    app.model_entrypoint.apply_failure = lambda error: apply_calls.append(error)  # type: ignore[method-assign]

    map_controller._on_render_job_failed("sim-1", error)

    assert apply_calls == [error]
    assert "sim-1" not in map_controller._render_jobs_by_simulation_id


def test_render_job_cancelled_callback_clears_tracked_handle() -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)
    map_controller._render_jobs_by_simulation_id["sim-1"] = JobHandler(
        job_id="job-1", name="render_map"
    )

    map_controller._on_render_job_cancelled("sim-1")

    assert "sim-1" not in map_controller._render_jobs_by_simulation_id


def test_on_simulation_deleted_cancels_render_job_and_forwards(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    _patch_controller_type_checks(monkeypatch, app)
    map_controller = _make_map_sub_controller(app)
    simulation = _add_simulation(app.model_entrypoint, "sim-1")
    map_controller._render_jobs_by_simulation_id["sim-1"] = JobHandler(
        job_id="job-1", name="render_map"
    )

    map_controller._on_simulation_deleted(
        SimulationDeletedPayload(simulation=simulation)
    )

    assert app.cancelled_job_ids == ["job-1"]
    assert "sim-1" not in map_controller._render_jobs_by_simulation_id
    app.view.forward_simulation_deleted.assert_called_once_with("sim-1")
