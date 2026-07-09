"""Tests for render map core runtime work."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.entrypoint import ModelEntrypoint
from core.signals import (
    CoreSignal,
    CoreSignals,
    MapRenderedPayload,
    MapRenderFailedPayload,
)
from core.simulation import Simulation, SimulationRepository
from core.work.render_map_work import (
    RenderMapError,
    RenderMapOutcome,
    RenderMapWork,
)


def _model_entrypoint_with_sims(tmp_path: Path) -> ModelEntrypoint:
    model_entrypoint = ModelEntrypoint()
    model_entrypoint._simulations = SimulationRepository(tmp_path / "simulations")
    return model_entrypoint


def _add_simulation(
    model_entrypoint: ModelEntrypoint, simulation_id: str
) -> Simulation:
    simulation = Simulation(id=simulation_id)
    model_entrypoint._simulations.add(simulation)
    return simulation


def test_render_map_work_run_returns_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    html_path = Path("/tmp/sim-1.html")

    class FakeRenderer:
        def to_html(self, path: Path, prefix: str = "") -> Path:
            assert prefix == "sim-1"
            return html_path

    monkeypatch.setattr(
        "core.work.render_map_work.MapRenderer",
        lambda: FakeRenderer(),
    )

    outcome = RenderMapWork(
        simulation_id="sim-1",
        application_dir=Path("/app"),
    ).run()

    assert outcome == RenderMapOutcome(simulation_id="sim-1", html_path=html_path)


def test_render_map_work_run_raises_render_map_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenRenderer:
        def to_html(self, path: Path, prefix: str = "") -> Path:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "core.work.render_map_work.MapRenderer",
        lambda: BrokenRenderer(),
    )

    with pytest.raises(RenderMapError) as exc_info:
        RenderMapWork(
            simulation_id="sim-1",
            application_dir=Path("/app"),
        ).run()

    assert exc_info.value.simulation_id == "sim-1"


def test_model_entrypoint_render_map_delegates_to_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = RenderMapOutcome(
        simulation_id="sim-1", html_path=Path("/tmp/sim-1.html")
    )
    calls: list[tuple[str, Path]] = []

    class FakeWork:
        def __init__(self, *, simulation_id: str, application_dir: Path) -> None:
            calls.append((simulation_id, application_dir))

        def run(self) -> RenderMapOutcome:
            return expected

    monkeypatch.setattr("core.entrypoint.RenderMapWork", FakeWork)

    result = ModelEntrypoint.render_map("sim-1", Path("/app"))

    assert result == expected
    assert calls == [("sim-1", Path("/app"))]


def test_apply_main_thread_emits_map_rendered(tmp_path: Path) -> None:
    model_entrypoint = _model_entrypoint_with_sims(tmp_path)
    simulation = _add_simulation(model_entrypoint, "sim-1")
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    html_path = Path("/tmp/sim-1.html")

    RenderMapWork.apply_main_thread(
        model_entrypoint,
        RenderMapOutcome(simulation_id="sim-1", html_path=html_path),
    )

    assert simulation.map_file == html_path
    assert emitted == [
        (
            CoreSignals.MAP_RENDERED,
            MapRenderedPayload(simulation_id="sim-1", html_path=html_path),
        )
    ]


def test_apply_main_thread_skips_emit_when_simulation_missing(tmp_path: Path) -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    html_path = tmp_path / "sim-1.html"
    html_path.write_text("<html></html>", encoding="utf-8")

    RenderMapWork.apply_main_thread(
        model_entrypoint,
        RenderMapOutcome(simulation_id="sim-1", html_path=html_path),
    )

    assert emitted == []
    assert not html_path.exists()


def test_apply_main_thread_orphan_cleanup_swallows_oserror(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )
    html_path = tmp_path / "sim-1.html"

    def _unlink_raises(self, missing_ok=False) -> None:  # type: ignore[no-untyped-def]
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "unlink", _unlink_raises)

    RenderMapWork.apply_main_thread(
        model_entrypoint,
        RenderMapOutcome(simulation_id="sim-1", html_path=html_path),
    )

    assert emitted == []


def test_apply_failure_main_thread_emits_map_render_failed(tmp_path: Path) -> None:
    model_entrypoint = _model_entrypoint_with_sims(tmp_path)
    simulation = _add_simulation(model_entrypoint, "sim-1")
    simulation.map_file = Path("/tmp/sim-1.html")
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    RenderMapWork.apply_failure_main_thread(
        model_entrypoint,
        RenderMapError(simulation_id="sim-1", reason="failed"),
    )

    assert simulation.map_file is None
    assert emitted == [
        (
            CoreSignals.MAP_RENDER_FAILED,
            MapRenderFailedPayload(simulation_id="sim-1", reason="failed"),
        )
    ]


def test_apply_failure_main_thread_skips_emit_when_simulation_missing() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    RenderMapWork.apply_failure_main_thread(
        model_entrypoint,
        RenderMapError(simulation_id="sim-1", reason="failed"),
    )

    assert emitted == []


def test_apply_failure_main_thread_falls_back_to_generic_error() -> None:
    model_entrypoint = ModelEntrypoint()
    emitted: list[tuple[CoreSignal[Any], object]] = []
    model_entrypoint._signal_bus.emit = lambda signal, payload: emitted.append(  # type: ignore[method-assign]
        (signal, payload)
    )

    RenderMapWork.apply_failure_main_thread(model_entrypoint, RuntimeError("boom"))

    assert len(emitted) == 1
    assert emitted[0][0] == CoreSignals.ERROR_RAISED
