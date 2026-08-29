from __future__ import annotations

import datetime
import os
import threading
import time
import traceback as _traceback
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication

import controller.runner as runner_mod
from controller.runner import AsyncRunner, JobError, JobSpecification

pytestmark = [pytest.mark.async_jobs]


@pytest.fixture(scope="session", autouse=True)
def _qt_core_app() -> None:
    """
    Ensure a Qt GUI application exists for QTimer/signals and pytest-qt widget tests.

    ``QApplication`` subclasses ``QCoreApplication`` and satisfies both
    ``AsyncRunner`` event-loop tests and ``src/gui`` widget tests in one session.
    """

    app = QApplication.instance()
    if app is None:
        QApplication([])


def _process_events_until(
    condition: Callable[[], bool], timeout_s: float = 8.0
) -> None:
    """
    Pump the Qt event queue until `condition()` becomes truthy.

    Raises AssertionError on timeout.
    """

    assert QApplication.instance() is not None
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return
        QApplication.instance().processEvents(QEventLoop.AllEvents, 50)
        time.sleep(0.01)
    assert condition(), "Timed out while waiting for async runner signals"


# --- Job fns used by ThreadPool / ProcessPool (must be picklable for process pool) ---


def _return_value(value: str) -> str:
    return value


def _raise_error(message: str) -> None:
    raise RuntimeError(message)


def _wait_on_event(event: threading.Event, value: str) -> str:
    # Thread-pool only: threading.Event is not picklable.
    event.wait()
    return value


def _sleep_then_return(seconds: float, value: str) -> str:
    time.sleep(seconds)
    return value


def _return_pid_threadid() -> tuple[int, int]:
    # Used to verify process vs thread dispatch (pid differs for processes).
    import os as _os
    import threading as _threading

    return _os.getpid(), _threading.get_ident()


@pytest.fixture(params=["thread", "process"])
def deadline_pool(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[runner_mod.ThreadPool | runner_mod.ProcessPool]:
    """Exercise both pool submit paths without opening system process workers."""

    if request.param == "thread":
        pool: runner_mod.ThreadPool | runner_mod.ProcessPool = runner_mod.ThreadPool(
            max_workers=1
        )
    else:
        monkeypatch.setattr(
            runner_mod,
            "ProcessPoolExecutor",
            lambda **_kwargs: ThreadPoolExecutor(max_workers=1),
        )
        pool = runner_mod.ProcessPool(max_workers=1)
    yield pool
    pool.shutdown()


def _submit_to_pool(
    pool: runner_mod.ThreadPool | runner_mod.ProcessPool,
    *,
    job: JobSpecification,
    cancel_token: runner_mod.CancelToken | None = None,
) -> tuple[
    Future[Any],
    threading.Event,
    list[object],
    list[str],
    list[JobError],
]:
    terminal = threading.Event()
    completed: list[object] = []
    cancelled: list[str] = []
    failed: list[JobError] = []

    def propose_terminal(job_id: str, proposal: runner_mod._TerminalProposal) -> None:
        if isinstance(proposal, runner_mod._CompletedProposal):
            completed.append(proposal.result)
        elif isinstance(proposal, runner_mod._CancelledProposal):
            cancelled.append(job_id)
        else:
            failed.append(proposal.error)
        terminal.set()

    future = pool.submit(
        "job-1",
        job,
        cancel_token or runner_mod.CancelToken(),
        lambda _job_id, _progress: None,
        propose_terminal,
    )
    return future, terminal, completed, cancelled, failed


class TestPoolDeadlines:
    def test_fractional_deadline_fails_and_discards_late_result(
        self,
        deadline_pool: runner_mod.ThreadPool | runner_mod.ProcessPool,
    ) -> None:
        release = threading.Event()
        future, terminal, completed, cancelled, failed = _submit_to_pool(
            deadline_pool,
            job=JobSpecification(
                name="deadline-job",
                fn=_wait_on_event,
                args=(release, "late"),
                timeout=0.02,
                type="thread",
            ),
        )

        assert terminal.wait(1.0), "timeout failure was not emitted at the deadline"
        assert completed == []
        assert cancelled == []
        assert len(failed) == 1
        assert failed[0].origin == "deadline-job"
        assert failed[0].exception_type == "TimeoutError"
        assert isinstance(failed[0].exception, TimeoutError)

        release.set()
        assert future.result(timeout=1.0) == "late"
        time.sleep(0.05)
        assert completed == []
        assert len(failed) == 1

    def test_completion_before_deadline_cancels_timeout(
        self,
        deadline_pool: runner_mod.ThreadPool | runner_mod.ProcessPool,
    ) -> None:
        future, terminal, completed, cancelled, failed = _submit_to_pool(
            deadline_pool,
            job=JobSpecification(
                name="fast-job",
                fn=_return_value,
                args=("done",),
                timeout=0.05,
                type="thread",
            ),
        )

        assert terminal.wait(1.0)
        assert future.result(timeout=1.0) == "done"
        time.sleep(0.08)
        assert completed == ["done"]
        assert cancelled == []
        assert failed == []

    def test_cancelled_job_emits_cancelled_instead_of_timeout(
        self,
        deadline_pool: runner_mod.ThreadPool | runner_mod.ProcessPool,
    ) -> None:
        release = threading.Event()
        cancel_token = runner_mod.CancelToken()
        future, terminal, completed, cancelled, failed = _submit_to_pool(
            deadline_pool,
            job=JobSpecification(
                name="cancelled-job",
                fn=_wait_on_event,
                args=(release, "late"),
                timeout=0.02,
                type="thread",
            ),
            cancel_token=cancel_token,
        )
        cancel_token.cancel()

        assert terminal.wait(1.0)
        assert completed == []
        assert cancelled == ["job-1"]
        assert failed == []

        release.set()
        assert future.result(timeout=1.0) == "late"

    @pytest.mark.parametrize(
        "timeout",
        [0.0, -1.0, float("inf"), float("nan")],
    )
    def test_timeout_must_be_positive_and_finite(self, timeout: float) -> None:
        with pytest.raises(ValueError, match="positive finite"):
            JobSpecification(name="invalid-timeout", fn=_return_value, timeout=timeout)


class _FakePool:
    """
    Minimal pool replacement for tests.

    It does not use threads/processes; it only simulates the async framework
    contract by proposing a terminal outcome while letting `AsyncRunner` handle
    Qt signal marshaling, final arbitration, and cleanup.
    """

    def __init__(
        self,
        *,
        shutdown_cb: Callable[[], None] | None = None,
        pending: dict[str, Callable[[], None]] | None = None,
        pool_name: str | None = None,
        pool_by_job_id: dict[str, str] | None = None,
    ) -> None:
        self._shutdown_cb = shutdown_cb
        self._pending = pending
        self._pool_name = pool_name
        self._pool_by_job_id = pool_by_job_id

    def submit(
        self,
        job_id: str,
        job: JobSpecification,
        cancel_token: Any,
        _emit_progress: Callable[[str, object], None],
        propose_terminal: Callable[[str, runner_mod._TerminalProposal], None],
    ) -> None:
        if self._pool_name is not None and self._pool_by_job_id is not None:
            self._pool_by_job_id[job_id] = self._pool_name

        def _complete() -> None:
            if cancel_token.is_cancelled():
                propose_terminal(job_id, runner_mod._CancelledProposal())
                return

            try:
                if job.fn is None:
                    raise ValueError("JobSpecification.fn must be set (callable)")
                result = job.fn(*job.args, **job.kwargs)
                propose_terminal(job_id, runner_mod._CompletedProposal(result))
            except Exception as e:  # noqa: BLE001 - test helper
                propose_terminal(
                    job_id,
                    runner_mod._FailedProposal(
                        runner_mod._job_error_from_exception(job_name=job.name, exc=e)
                    ),
                )

        if self._pending is not None:
            self._pending[job_id] = _complete
            return None

        _complete()
        return None

    def shutdown(self) -> None:
        if self._shutdown_cb is not None:
            self._shutdown_cb()


@pytest.fixture
def runner_factory(monkeypatch: pytest.MonkeyPatch) -> Callable[..., AsyncRunner]:
    """Create AsyncRunner instances with fake pools to avoid system process limits."""

    def _factory(
        *,
        thread_pending: dict[str, Callable[[], None]] | None = None,
        process_pending: dict[str, Callable[[], None]] | None = None,
        pool_by_job_id: dict[str, str] | None = None,
    ) -> AsyncRunner:
        thread_shutdown_called = {"value": False}
        process_shutdown_called = {"value": False}

        def make_thread_pool() -> _FakePool:
            return _FakePool(
                shutdown_cb=lambda: thread_shutdown_called.__setitem__("value", True),
                pending=thread_pending,
                pool_name="thread",
                pool_by_job_id=pool_by_job_id,
            )

        def make_process_pool() -> _FakePool:
            return _FakePool(
                shutdown_cb=lambda: process_shutdown_called.__setitem__("value", True),
                pending=process_pending,
                pool_name="process",
                pool_by_job_id=pool_by_job_id,
            )

        monkeypatch.setattr(runner_mod, "ThreadPool", make_thread_pool)
        monkeypatch.setattr(runner_mod, "ProcessPool", make_process_pool)

        runner = AsyncRunner()
        runner._test_shutdown_called = {
            "thread": thread_shutdown_called,
            "process": process_shutdown_called,
        }
        return runner

    return _factory


class TestAsyncRunnerThreadSignals:
    def test_thread_timeout_is_marshaled_and_cleans_runner_state(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(runner_mod, "ProcessPool", _FakePool)
        runner = AsyncRunner()
        release = threading.Event()
        runner_failed: list[tuple[str, JobError, int]] = []
        handle_failed: list[tuple[JobError, int]] = []
        completed: list[tuple[str, object]] = []
        main_thread_id = threading.get_ident()

        runner.signals.Failed.connect(
            lambda job_id, error: runner_failed.append(
                (job_id, error, threading.get_ident())
            )
        )
        runner.signals.Completed.connect(
            lambda job_id, result: completed.append((job_id, result))
        )
        handle = runner.submit(
            JobSpecification(
                name="qt-timeout",
                fn=_wait_on_event,
                args=(release, "late"),
                timeout=0.02,
                coalesce_key="timeout-test",
                type="thread",
            )
        )
        assert handle is not None
        runner.bind_handle_signals(handle).Failed.connect(
            lambda error: handle_failed.append((error, threading.get_ident()))
        )

        _process_events_until(lambda: len(runner_failed) == 1)

        assert runner_failed[0][0] == handle.job_id
        assert runner_failed[0][1].origin == "qt-timeout"
        assert runner_failed[0][2] == main_thread_id
        assert handle_failed == [(runner_failed[0][1], main_thread_id)]
        assert completed == []
        assert handle.job_id not in runner.history
        assert "timeout-test" not in runner._coalesce_latest

        release.set()
        time.sleep(0.05)
        QApplication.instance().processEvents(QEventLoop.AllEvents, 50)
        assert completed == []
        assert len(runner_failed) == 1
        runner.shutdown()

    def test_thread_completed_emits_completed_and_cleans_history(
        self, runner_factory: Callable[..., AsyncRunner]
    ) -> None:
        runner = runner_factory()

        completed: list[tuple[str, object]] = []
        failed: list[tuple[str, JobError]] = []

        def on_completed(job_id: str, result: object) -> None:
            completed.append((job_id, result))

        def on_failed(job_id: str, err: JobError) -> None:
            failed.append((job_id, err))

        runner.signals.Completed.connect(on_completed)
        runner.signals.Failed.connect(on_failed)

        spec = JobSpecification(
            name="thread-success",
            description="",
            fn=_return_value,
            args=("ok",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key=None,
            type="thread",
        )
        handle = runner.submit(spec)
        assert handle is not None
        assert handle.job_id in runner.history

        _process_events_until(lambda: len(completed) == 1 or len(failed) == 1)
        assert failed == []
        assert completed[0][1] == "ok"
        assert handle.job_id not in runner.history

        runner.shutdown()

    def test_thread_failed_emits_failed_and_cleans_history(
        self, runner_factory: Callable[..., AsyncRunner]
    ) -> None:
        runner = runner_factory()

        completed: list[tuple[str, object]] = []
        failed: list[tuple[str, JobError]] = []

        runner.signals.Completed.connect(
            lambda job_id, result: completed.append((job_id, result))
        )
        runner.signals.Failed.connect(lambda job_id, err: failed.append((job_id, err)))

        spec = JobSpecification(
            name="thread-failure",
            description="",
            fn=_raise_error,
            args=("boom",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key=None,
            type="thread",
        )
        handle = runner.submit(spec)
        assert handle is not None
        assert handle.job_id in runner.history

        _process_events_until(lambda: len(failed) == 1)
        assert completed == []
        _job_id, err = failed[0]
        assert handle.job_id == _job_id
        assert "Job failed: thread-failure" in err.message
        assert "boom" in err.message
        assert err.origin == "thread-failure"
        assert err.exception_type == "RuntimeError"
        assert isinstance(err.exception, RuntimeError)
        assert str(err.exception) == "boom"
        assert handle.job_id not in runner.history

        runner.shutdown()

    def test_thread_cancelled_emits_cancelled_and_cleans_history(
        self, runner_factory: Callable[..., AsyncRunner]
    ) -> None:
        pending: dict[str, Callable[[], None]] = {}
        runner = runner_factory(thread_pending=pending)

        cancelled: list[str] = []
        completed: list[str] = []

        runner.signals.Cancelled.connect(lambda job_id: cancelled.append(job_id))
        runner.signals.Completed.connect(
            lambda job_id, _result: completed.append(job_id)
        )
        spec = JobSpecification(
            name="thread-cancelled",
            description="",
            fn=_return_value,
            args=("never-emitted",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key=None,
            type="thread",
        )
        handle = runner.submit(spec)
        assert handle is not None
        runner.cancel(handle.job_id)
        assert handle.job_id in pending
        pending[handle.job_id]()
        _process_events_until(lambda: len(cancelled) == 1)
        assert completed == []
        assert cancelled[0] == handle.job_id
        assert handle.job_id not in runner.history

        runner.shutdown()


class TestAsyncRunnerTerminalCommit:
    def test_queued_completion_becomes_cancelled_when_cancelled_before_dispatch(
        self, runner_factory: Callable[..., AsyncRunner]
    ) -> None:
        runner = runner_factory()
        runner_completed: list[tuple[str, object]] = []
        runner_cancelled: list[str] = []
        handle_completed: list[object] = []
        handle_cancelled: list[bool] = []
        runner.signals.Completed.connect(
            lambda job_id, result: runner_completed.append((job_id, result))
        )
        runner.signals.Cancelled.connect(lambda job_id: runner_cancelled.append(job_id))

        handle = runner.submit(
            JobSpecification(
                name="queued-completion",
                fn=_return_value,
                args=("stale",),
                type="thread",
            )
        )
        assert handle is not None
        handle_signals = runner.bind_handle_signals(handle)
        handle_signals.Completed.connect(handle_completed.append)
        handle_signals.Cancelled.connect(lambda: handle_cancelled.append(True))

        runner.cancel(handle.job_id)
        _process_events_until(lambda: runner_cancelled == [handle.job_id])

        assert runner_completed == []
        assert handle_completed == []
        assert handle_cancelled == [True]
        assert handle.job_id not in runner.history
        runner.shutdown()

    def test_superseded_queued_completion_cannot_clear_latest_job(
        self, runner_factory: Callable[..., AsyncRunner]
    ) -> None:
        runner = runner_factory()
        completed: list[tuple[str, object]] = []
        cancelled: list[str] = []
        state_seen_when_first_cancelled: list[tuple[str | None, bool]] = []
        runner.signals.Completed.connect(
            lambda job_id, result: completed.append((job_id, result))
        )
        runner.signals.Cancelled.connect(lambda job_id: cancelled.append(job_id))

        first = runner.submit(
            JobSpecification(
                name="first",
                fn=_return_value,
                args=("stale",),
                coalesce_key="location",
                type="thread",
            )
        )
        assert first is not None
        first_signals = runner.bind_handle_signals(first)

        second = runner.submit(
            JobSpecification(
                name="second",
                fn=_return_value,
                args=("current",),
                coalesce_key="location",
                type="thread",
            )
        )
        assert second is not None
        first_signals.Cancelled.connect(
            lambda: state_seen_when_first_cancelled.append(
                (
                    runner._coalesce_latest.get("location"),
                    second.job_id in runner.history,
                )
            )
        )

        _process_events_until(lambda: len(cancelled) == 1 and len(completed) == 1)

        assert cancelled == [first.job_id]
        assert completed == [(second.job_id, "current")]
        assert state_seen_when_first_cancelled == [(second.job_id, True)]
        assert runner.history == {}
        assert "location" not in runner._coalesce_latest
        runner.shutdown()

    @pytest.mark.parametrize(
        "proposal",
        [
            runner_mod._FailedProposal(
                runner_mod._job_error_from_exception(
                    job_name="queued-failure", exc=RuntimeError("boom")
                )
            ),
            runner_mod._FailedProposal(
                runner_mod._job_error_from_timeout(
                    job_name="queued-timeout", timeout=0.01
                )
            ),
        ],
        ids=["failure", "timeout"],
    )
    def test_cancellation_suppresses_queued_failure_proposals(
        self,
        runner_factory: Callable[..., AsyncRunner],
        proposal: runner_mod._FailedProposal,
    ) -> None:
        pending: dict[str, Callable[[], None]] = {}
        runner = runner_factory(thread_pending=pending)
        failed: list[tuple[str, JobError]] = []
        cancelled: list[str] = []
        runner.signals.Failed.connect(
            lambda job_id, error: failed.append((job_id, error))
        )
        runner.signals.Cancelled.connect(lambda job_id: cancelled.append(job_id))
        handle = runner.submit(
            JobSpecification(name="queued-terminal", fn=_return_value, type="thread")
        )
        assert handle is not None

        runner._terminal_ready.emit(handle.job_id, proposal)
        runner.cancel(handle.job_id)
        _process_events_until(lambda: cancelled == [handle.job_id])

        assert failed == []
        assert handle.job_id not in runner.history
        runner.shutdown()

    def test_late_duplicate_terminal_proposal_is_ignored(
        self, runner_factory: Callable[..., AsyncRunner]
    ) -> None:
        runner = runner_factory()
        completed: list[tuple[str, object]] = []
        cancelled: list[str] = []
        runner.signals.Completed.connect(
            lambda job_id, result: completed.append((job_id, result))
        )
        runner.signals.Cancelled.connect(lambda job_id: cancelled.append(job_id))
        handle = runner.submit(
            JobSpecification(
                name="one-terminal-event",
                fn=_return_value,
                args=("first",),
                type="thread",
            )
        )
        assert handle is not None
        _process_events_until(lambda: completed == [(handle.job_id, "first")])

        runner._terminal_ready.emit(
            handle.job_id, runner_mod._CompletedProposal("duplicate")
        )
        QApplication.instance().processEvents(QEventLoop.AllEvents, 50)

        assert completed == [(handle.job_id, "first")]
        assert cancelled == []
        runner.shutdown()


class TestAsyncRunnerProcessAndCoalesce:
    def test_process_failed_emits_failed_and_cleans_history(
        self, runner_factory: Callable[..., AsyncRunner]
    ) -> None:
        runner = runner_factory()

        completed: list[tuple[str, object]] = []
        failed: list[tuple[str, JobError]] = []

        runner.signals.Completed.connect(
            lambda job_id, result: completed.append((job_id, result))
        )
        runner.signals.Failed.connect(lambda job_id, err: failed.append((job_id, err)))

        spec = JobSpecification(
            name="process-failure",
            description="",
            fn=_raise_error,
            args=("boom",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key=None,
            type="process",
        )
        handle = runner.submit(spec)
        assert handle is not None
        assert handle.job_id in runner.history

        _process_events_until(lambda: len(failed) == 1)
        assert completed == []
        _job_id, err = failed[0]
        assert _job_id == handle.job_id
        assert "Job failed: process-failure" in err.message
        assert "boom" in err.message
        assert handle.job_id not in runner.history

        runner.shutdown()

    def test_coalesce_key_cancels_previous_latest_and_only_latest_completes(
        self,
        runner_factory: Callable[..., AsyncRunner],
    ) -> None:
        pending: dict[str, Callable[[], None]] = {}
        runner = runner_factory(thread_pending=pending)

        cancelled: list[str] = []
        completed: list[tuple[str, object]] = []

        runner.signals.Cancelled.connect(lambda job_id: cancelled.append(job_id))
        runner.signals.Completed.connect(
            lambda job_id, result: completed.append((job_id, result))
        )

        spec1 = JobSpecification(
            name="job-1",
            description="",
            fn=_return_value,
            args=("job-1-result",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key="location",
            type="thread",
        )
        handle1 = runner.submit(spec1)
        assert handle1 is not None

        # Submit a second job with the same coalesce_key. This should cancel `handle1`.
        spec2 = JobSpecification(
            name="job-2",
            description="",
            fn=_return_value,
            args=("job-2-result",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key="location",
            type="thread",
        )
        handle2 = runner.submit(spec2)
        assert handle2 is not None
        assert handle1.job_id in runner.history
        assert handle2.job_id in runner.history

        assert handle1.job_id in pending
        assert handle2.job_id in pending
        assert handle1.cancel_token.is_cancelled()

        # Simulate job completion in-order.
        pending[handle1.job_id]()
        pending[handle2.job_id]()

        _process_events_until(lambda: len(cancelled) == 1 and len(completed) == 1)
        assert cancelled[0] == handle1.job_id
        assert completed[0][0] == handle2.job_id
        assert completed[0][1] == "job-2-result"

        assert handle1.job_id not in runner.history
        assert handle2.job_id not in runner.history

        runner.shutdown()

    def test_auto_resolves_job_type_process_vs_thread_by_name_and_coalesce_key(
        self,
        runner_factory: Callable[..., AsyncRunner],
    ) -> None:
        pool_by_job_id: dict[str, str] = {}
        runner = runner_factory(pool_by_job_id=pool_by_job_id)

        completed_results: dict[str, object] = {}

        def on_completed(job_id: str, result: object) -> None:
            completed_results[job_id] = result

        runner.signals.Completed.connect(on_completed)

        # Auto -> process (name contains "map")
        spec_process = JobSpecification(
            name="map creation",
            description="",
            fn=_return_value,
            args=("process-result",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key=None,
            type="auto",
        )
        handle_process = runner.submit(spec_process)
        assert handle_process is not None

        # Auto -> thread (coalesce_key == "location")
        spec_thread = JobSpecification(
            name="location update",
            description="",
            fn=_return_value,
            args=("thread-result",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key="location",
            type="auto",
        )
        handle_thread = runner.submit(spec_thread)
        assert handle_thread is not None

        _process_events_until(
            lambda: handle_process.job_id in completed_results
            and handle_thread.job_id in completed_results
        )

        assert pool_by_job_id[handle_process.job_id] == "process"
        assert pool_by_job_id[handle_thread.job_id] == "thread"
        assert completed_results[handle_process.job_id] == "process-result"
        assert completed_results[handle_thread.job_id] == "thread-result"

        runner.shutdown()

    def test_completed_coalesced_job_clears_latest_tracking(
        self, runner_factory: Callable[..., AsyncRunner]
    ) -> None:
        """Completing the latest coalesced job removes its coalesce bookkeeping."""
        runner = runner_factory()
        handle = runner.submit(
            JobSpecification(
                name="device refresh",
                description="",
                fn=_return_value,
                args=("done",),
                kwargs={},
                timeout=None,
                priority=0,
                coalesce_key="device",
                type="thread",
            )
        )
        assert handle is not None

        _process_events_until(lambda: handle.job_id not in runner.history)
        assert "device" not in runner._coalesce_latest

        runner.shutdown()

    def test_at_most_once_rejects_duplicate_while_first_job_is_active(
        self,
        runner_factory: Callable[..., AsyncRunner],
        log_records,
    ) -> None:
        """Second submit with same coalesce_key returns None and leaves the first job running."""
        pending: dict[str, Callable[[], None]] = {}
        runner = runner_factory(thread_pending=pending)

        cancelled: list[str] = []
        completed: list[tuple[str, object]] = []

        runner.signals.Cancelled.connect(lambda job_id: cancelled.append(job_id))
        runner.signals.Completed.connect(
            lambda job_id, result: completed.append((job_id, result))
        )

        spec1 = JobSpecification(
            name="refresh-1",
            description="",
            fn=_return_value,
            args=("refresh-1-result",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key="refresh_device_list",
            at_most_once=True,
            type="thread",
        )
        handle1 = runner.submit(spec1)
        assert handle1 is not None
        assert handle1.job_id in runner.history
        assert handle1.job_id in pending

        spec2 = JobSpecification(
            name="refresh-2",
            description="",
            fn=_return_value,
            args=("refresh-2-result",),
            kwargs={},
            timeout=None,
            priority=0,
            coalesce_key="refresh_device_list",
            at_most_once=True,
            type="thread",
        )
        handle2 = runner.submit(spec2)
        assert handle2 is None
        assert len(runner.history) == 1
        assert handle1.job_id in runner.history
        assert not handle1.cancel_token.is_cancelled()
        assert len(pending) == 1

        pending[handle1.job_id]()
        _process_events_until(lambda: len(completed) == 1)
        assert cancelled == []
        assert completed[0][0] == handle1.job_id
        assert completed[0][1] == "refresh-1-result"
        assert handle1.job_id not in runner.history
        assert "refresh_device_list" not in runner._coalesce_latest

        runner.shutdown()
        duplicate_records = [
            record
            for record in log_records
            if record["message"] == "Async job submission skipped"
        ]
        assert len(duplicate_records) == 1
        assert duplicate_records[0]["level"].name == "DEBUG"
        assert duplicate_records[0]["extra"]["reason"] == "at_most_once"


class TestAsyncRunnerPreflight:
    def test_invalid_job_type_is_rejected_before_runner_state_is_registered(
        self,
        runner_factory: Callable[..., AsyncRunner],
    ) -> None:
        runner = runner_factory()

        with pytest.raises(ValueError, match="Invalid job type"):
            runner.submit(
                JobSpecification(
                    name="invalid-dispatch",
                    fn=_return_value,
                    coalesce_key="invalid-dispatch",
                    type=cast(runner_mod.jobtype, "invalid"),
                )
            )

        assert runner.history == {}
        assert "invalid-dispatch" not in runner._coalesce_latest
        runner.shutdown()

    def test_preflight_false_skips_submission_without_side_effects(
        self,
        runner_factory: Callable[..., AsyncRunner],
    ) -> None:
        runner = runner_factory()
        preflight_calls: list[str] = []

        def _reject() -> bool:
            preflight_calls.append("called")
            return False

        handle = runner.submit(
            JobSpecification(
                name="preflight-rejected",
                description="",
                fn=_return_value,
                args=("unused",),
                kwargs={},
                timeout=None,
                priority=0,
                coalesce_key="preflight-test",
                type="thread",
                preflight=_reject,
            )
        )

        assert handle is None
        assert preflight_calls == ["called"]
        assert runner.history == {}
        assert "preflight-test" not in runner._coalesce_latest

        runner.shutdown()

    def test_preflight_true_submits_normally(
        self,
        runner_factory: Callable[..., AsyncRunner],
    ) -> None:
        pending: dict[str, Callable[[], None]] = {}
        runner = runner_factory(thread_pending=pending)
        completed: list[tuple[str, object]] = []
        runner.signals.Completed.connect(
            lambda job_id, result: completed.append((job_id, result))
        )

        handle = runner.submit(
            JobSpecification(
                name="preflight-accepted",
                description="",
                fn=_return_value,
                args=("accepted-result",),
                kwargs={},
                timeout=None,
                priority=0,
                coalesce_key=None,
                type="thread",
                preflight=lambda: True,
            )
        )

        assert handle is not None
        assert handle.job_id in runner.history
        assert handle.job_id in pending

        pending[handle.job_id]()
        _process_events_until(lambda: len(completed) == 1)
        assert completed[0] == (handle.job_id, "accepted-result")

        runner.shutdown()


class TestProcessPoolLogging:
    def test_process_pool_uses_isolated_worker_logger_initializer(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        run_identifier = "01fdb29d-2e6b-49d1-8956-9d1caa576d2c"
        captured: dict[str, object] = {}
        events: list[tuple[str, object]] = []

        class FakeExecutor:
            def __init__(
                self,
                *,
                max_workers: int | None = None,
                initializer: object | None = None,
            ) -> None:
                events.append(("executor", None))
                captured["max_workers"] = max_workers
                captured["initializer"] = initializer

            def submit(self, *_args: object, **_kwargs: object) -> None:
                return None

            def shutdown(self, **_kwargs: object) -> None:
                return None

        monkeypatch.setattr(runner_mod, "ProcessPoolExecutor", FakeExecutor)
        monkeypatch.setattr(
            runner_mod,
            "resolve_worker_application_log_file_path",
            lambda *, process_id: Path(
                f"/logs/{run_identifier}.worker-{process_id}.log"
            ),
        )
        monkeypatch.setattr(
            runner_mod.logger,
            "debug",
            lambda message, **extra: events.append((message, extra)),
        )

        runner_mod.ProcessPool(max_workers=2)

        assert captured["max_workers"] == 2
        assert captured["initializer"] is runner_mod.setup_worker_logger
        assert events[:2] == [
            (
                "Opening process pool",
                {
                    "max_workers": 2,
                    "path": f"/logs/{run_identifier}.worker-{{pid}}.log",
                },
            ),
            ("executor", None),
        ]
