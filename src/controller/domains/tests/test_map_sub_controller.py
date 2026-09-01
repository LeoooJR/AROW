"""Tests for MapSubController async map rendering wiring."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from application_paths import ApplicationPaths
from controller.domains.map_sub_controller import MapSubController
from controller.orchestration.app_controller import AppController
from controller.runner import JobError, JobHandler, JobHandlerSignals
from core.entrypoint import ModelEntrypoint
from core.signals import (
    MapRenderedPayload,
    MapRenderFailedPayload,
    SimulationDeletedPayload,
    SimulationLocationRejectedPayload,
    SimulationLocationValidatedPayload,
    SimulationLocationValidationRequestedPayload,
)
from core.simulation import Simulation
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
        self._tmp_path = tmp_path if tmp_path is not None else Path(tempfile.mkdtemp())
        self.model_entrypoint = ModelEntrypoint(
            paths=ApplicationPaths(
                self._tmp_path,
                self._tmp_path / "config",
                self._tmp_path / "src",
                "linux",
            )
        )
        self.view = MagicMock()
        self.submitted: list[dict[str, Any]] = []
        self.cancelled_job_ids: list[str] = []
        self.handle_signals: dict[str, JobHandlerSignals] = {}
        self.runner = MagicMock()
        self.runner.cancel = lambda job_id: self.cancelled_job_ids.append(job_id)
        self.runner.bind_handle_signals = self._bind_handle_signals

    def _bind_handle_signals(self, handle: JobHandler) -> JobHandlerSignals:
        return self.handle_signals[handle.job_id]

    def _submit_model_entrypoint_async_call(self, **kwargs: Any) -> JobHandler | None:
        preflight = kwargs.get("preflight")
        if preflight is not None and not preflight():
            return None
        self.submitted.append(kwargs)
        handle = JobHandler(
            job_id=f"job-{len(self.submitted)}",
            name=kwargs.get("name", ""),
        )
        signals = JobHandlerSignals()
        self.handle_signals[handle.job_id] = signals
        if on_completed := kwargs.get("on_completed"):
            signals.Completed.connect(on_completed)
        if on_failed := kwargs.get("on_failed"):
            signals.Failed.connect(on_failed)
        if on_cancelled := kwargs.get("on_cancelled"):
            signals.Cancelled.connect(on_cancelled)
        return handle


def _make_map_sub_controller(app: _AppStub) -> MapSubController:
    return MapSubController(cast(AppController, app))


def _add_simulation(
    model_entrypoint: ModelEntrypoint, simulation_id: str
) -> Simulation:
    simulation = Simulation(id=simulation_id)
    model_entrypoint.restore_persisted_simulation(simulation)
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
    assert submit_kwargs["args"] == (
        "sim-1",
        app.model_entrypoint.paths.simulation_map_dir("sim-1"),
    )
    assert callable(submit_kwargs["preflight"])
    assert submit_kwargs["preflight"]() is True
    assert map_controller._render_jobs_by_simulation_id["sim-1"].job_id == "job-1"
    assert submit_kwargs["on_completed"] == app.model_entrypoint.apply_result
    assert submit_kwargs["on_failed"] == app.model_entrypoint.apply_failure
    assert "on_cancelled" not in submit_kwargs


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


def test_simulation_exists_preflight_rejects_missing_simulation() -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)

    preflight = map_controller._simulation_exists_preflight("sim-1")

    assert preflight() is False


def test_on_map_rendered_forwards_to_view() -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)
    payload = MapRenderedPayload(
        simulation_id="sim-1", html_path=Path("/tmp/sim-1.html")
    )

    map_controller._on_map_rendered(payload)

    app.view.forward_map_rendered.assert_called_once_with(
        "sim-1",
        payload.html_path,
    )


def test_on_map_render_failed_forwards_to_view() -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)
    payload = MapRenderFailedPayload(simulation_id="sim-1", reason="failed")

    map_controller._on_map_render_failed(payload)

    app.view.forward_map_render_failed.assert_called_once_with("sim-1", "failed")


def test_render_job_completion_applies_result_then_clears_handle(
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    apply_calls: list[object] = []
    app.model_entrypoint.apply_result = lambda result: apply_calls.append(result)  # type: ignore[method-assign]
    map_controller = _make_map_sub_controller(app)
    _add_simulation(app.model_entrypoint, "sim-1")
    outcome = RenderMapOutcome(simulation_id="sim-1", html_path=Path("/tmp/sim-1.html"))

    map_controller._on_render_map_requested("sim-1")
    app.handle_signals["job-1"].Completed.emit(outcome)

    assert apply_calls == [outcome]
    assert "sim-1" not in map_controller._render_jobs_by_simulation_id


def test_render_job_failure_applies_failure_then_clears_handle(tmp_path: Path) -> None:
    app = _AppStub(tmp_path)
    apply_calls: list[object] = []
    app.model_entrypoint.apply_failure = lambda error: apply_calls.append(error)  # type: ignore[method-assign]
    map_controller = _make_map_sub_controller(app)
    _add_simulation(app.model_entrypoint, "sim-1")
    error = JobError(message="boom", traceback="", origin="render_map")

    map_controller._on_render_map_requested("sim-1")
    app.handle_signals["job-1"].Failed.emit(error)

    assert apply_calls == [error]
    assert "sim-1" not in map_controller._render_jobs_by_simulation_id


def test_render_job_cancellation_clears_tracked_handle(tmp_path: Path) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    _add_simulation(app.model_entrypoint, "sim-1")

    map_controller._on_render_map_requested("sim-1")
    app.handle_signals["job-1"].Cancelled.emit()

    assert "sim-1" not in map_controller._render_jobs_by_simulation_id


def test_render_job_cancelled_from_superseded_job_keeps_current_handle() -> None:
    app = _AppStub()
    map_controller = _make_map_sub_controller(app)
    map_controller._render_jobs_by_simulation_id["sim-1"] = JobHandler(
        job_id="job-2", name="render_map"
    )

    map_controller._on_render_job_cancelled("sim-1", "job-1")

    assert map_controller._render_jobs_by_simulation_id["sim-1"].job_id == "job-2"


def test_render_job_completed_from_superseded_job_keeps_current_handle(
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    map_controller._render_jobs_by_simulation_id["sim-1"] = JobHandler(
        job_id="job-2", name="render_map"
    )
    outcome = RenderMapOutcome(simulation_id="sim-1", html_path=Path("/tmp/sim-1.html"))

    map_controller._on_render_job_finished("sim-1", "job-1", outcome)

    assert map_controller._render_jobs_by_simulation_id["sim-1"].job_id == "job-2"


def test_on_simulation_deleted_cancels_render_job_and_forwards(
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    simulation = _add_simulation(app.model_entrypoint, "sim-1")
    map_controller._render_jobs_by_simulation_id["sim-1"] = JobHandler(
        job_id="job-1", name="render_map"
    )

    map_controller._on_simulation_deleted(
        SimulationDeletedPayload(simulation_id="sim-1")
    )

    assert app.cancelled_job_ids == ["job-1"]
    assert "sim-1" not in map_controller._render_jobs_by_simulation_id
    app.view.forward_simulation_deleted.assert_called_once_with("sim-1")


def test_on_simulation_location_requested_submits_thread_job(
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    _add_simulation(app.model_entrypoint, "sim-1")

    map_controller._on_simulation_location_requested(
        "sim-1",
        1,
        "001000",
        1,
        48.88533318609319,
        2.363530409238113,
    )

    assert len(app.submitted) == 1
    submit_kwargs = app.submitted[0]
    assert submit_kwargs["name"] == "validate_simulation_marker_location"
    assert submit_kwargs["job_type"] == "thread"
    assert submit_kwargs["coalesce_key"] == "validate_simulation_marker_location:sim-1"
    assert (
        submit_kwargs["fn"] == app.model_entrypoint.validate_simulation_marker_location
    )
    assert submit_kwargs["args"] == (
        "sim-1",
        1,
        "001000",
        1,
        48.88533318609319,
        2.363530409238113,
    )
    assert callable(submit_kwargs["preflight"])
    assert submit_kwargs["preflight"]() is True
    assert submit_kwargs["on_completed"] == app.model_entrypoint.apply_result
    assert submit_kwargs["on_failed"] == app.model_entrypoint.apply_failure


def test_on_simulation_location_requested_skips_when_simulation_missing(
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)

    map_controller._on_simulation_location_requested(
        "sim-1",
        1,
        "001000",
        1,
        48.88533318609319,
        2.363530409238113,
    )

    assert app.submitted == []


def test_on_simulation_location_rejected_forwards_to_view(
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    payload = SimulationLocationRejectedPayload(
        simulation_id="sim-1",
        km=1,
        line_code="001000",
        line_troncon=1,
        lat=0.0,
        lon=0.0,
        reason="invalid marker",
    )

    map_controller._on_simulation_location_rejected(payload)

    app.view.forward_simulation_location_rejected.assert_called_once_with(
        simulation_id=payload.simulation_id,
        km=payload.km,
        line_code="001000",
        line_troncon=1,
        lat=payload.lat,
        lon=payload.lon,
        reason=payload.reason,
    )


def test_on_simulation_location_validated_forwards_to_view(
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    payload = SimulationLocationValidatedPayload(
        simulation_id="sim-1",
        lat=48.88533318609319,
        lon=2.363530409238113,
        km=1,
        line_id="line-id",
        line_code="001000",
        line_troncon=1,
        line_type="type",
        line_label="label",
        label="001+000",
        milestone_type="Kilometer",
        line_geometry_wkb_b64="",
    )

    map_controller._on_simulation_location_validated(payload)

    app.view.forward_simulation_location_validated.assert_called_once_with(
        simulation_id=payload.simulation_id,
        km=1,
        line_code="001000",
        line_troncon=1,
        lat=payload.lat,
        lon=payload.lon,
        label="001+000",
    )


def test_on_simulation_location_validation_requested_submits_async_job(
    tmp_path: Path,
) -> None:
    app = _AppStub(tmp_path)
    map_controller = _make_map_sub_controller(app)
    _add_simulation(app.model_entrypoint, "sim-1")
    payload = SimulationLocationValidationRequestedPayload(
        simulation_id="sim-1",
        km=1,
        line_code="001000",
        line_troncon=1,
        lat=48.88533318609319,
        lon=2.363530409238113,
    )

    map_controller._on_simulation_location_validation_requested(payload)

    assert len(app.submitted) == 1
    submit_kwargs = app.submitted[0]
    assert submit_kwargs["name"] == "validate_simulation_marker_location"
    assert submit_kwargs["args"] == (
        "sim-1",
        1,
        "001000",
        1,
        48.88533318609319,
        2.363530409238113,
    )
