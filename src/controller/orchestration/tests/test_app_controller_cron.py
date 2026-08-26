"""Tests for application-level recurring job orchestration."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, call

import pytest

import controller.orchestration.app_controller as app_controller_module
from controller.cron import CronJob
from controller.orchestration.app_controller import AppController
from controller.runner import JobSpecification


def _job(name: str) -> CronJob:
    return CronJob(
        interval_ms=1_000,
        specification=JobSpecification(name=name, fn=lambda: None),
    )


def test_commit_cron_jobs_collects_all_domains_before_commit() -> None:
    simulation_job = _job("simulation")
    adb_job = _job("adb")
    probe = MagicMock()
    probe._simulation.declare_cron_jobs.return_value = (simulation_job,)
    probe._adb.declare_cron_jobs.return_value = (adb_job,)
    probe._map.declare_cron_jobs.return_value = ()

    AppController._commit_cron_jobs(cast(AppController, probe))

    assert probe.cron_manager.method_calls == [
        call.declare(simulation_job),
        call.declare(adb_job),
        call.commit(),
    ]


class _LoopStub:
    def isRunning(self) -> bool:
        return False

    def exec(self) -> None:
        return None

    def quit(self) -> None:
        return None


class _TimerStub:
    def isActive(self) -> bool:
        return True

    def stop(self) -> None:
        return None


def test_shutdown_stops_cron_before_runner_teardown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    probe = MagicMock()
    probe.cron_manager.stop.side_effect = lambda: events.append("cron-stopped")
    probe._wait_for_adb_bootstrap_jobs.side_effect = lambda: events.append(
        "bootstrap-drained"
    )

    def enqueue_close(*, after_apply) -> None:
        events.append("close-enqueued")
        after_apply()

    probe._adb._enqueue_close_core_runtime.side_effect = enqueue_close
    probe._simulation.persist_simulation_repository.side_effect = lambda: events.append(
        "repository-persisted"
    )
    probe.runner.shutdown.side_effect = lambda: events.append("runner-shutdown")
    monkeypatch.setattr(app_controller_module, "QEventLoop", _LoopStub)
    monkeypatch.setattr(
        app_controller_module,
        "watchdog",
        lambda _ms: lambda _callback: _TimerStub(),
    )

    AppController._on_application_about_to_quit(cast(AppController, probe))

    assert events == [
        "cron-stopped",
        "bootstrap-drained",
        "close-enqueued",
        "repository-persisted",
        "runner-shutdown",
    ]
