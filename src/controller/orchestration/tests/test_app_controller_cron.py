"""Tests for application-level recurring job orchestration."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, call

from controller.cron import CronJob
from controller.orchestration.app_controller import AppController
from controller.runner import JobSpecification


def _job(name: str) -> CronJob:
    return CronJob(
        interval_ms=1_000,
        specification=JobSpecification(name=name, fn=lambda: None, type="thread"),
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
