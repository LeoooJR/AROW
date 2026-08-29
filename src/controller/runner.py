import datetime
import math
import traceback as _traceback
import uuid
from concurrent.futures import (
    Executor,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
)
from dataclasses import dataclass, field
from threading import Lock, Timer
from typing import Any, Callable, ClassVar, Literal, Optional

from loguru import logger
from PySide6.QtCore import QObject, Qt, Signal

from logger import resolve_worker_application_log_file_path, setup_worker_logger

jobtype = Literal["thread", "process"]
jobstatus = Literal["pending", "running", "completed", "cancelled", "failed"]
jobpriority = Literal["low", "medium", "high"]
jobtimeout = Literal["none", "short", "medium", "long"]
jobpreflight = Callable[[], bool]


class CancelledError(Exception):
    pass


@dataclass(frozen=True)
class JobError:
    """
    Error of a job execution
    """

    message: str = field(
        metadata={"description": "The message of the error"}, default=""
    )
    traceback: str = field(
        metadata={"description": "The traceback of the error"}, default=""
    )
    return_code: Optional[int] = field(
        metadata={"description": "The return code of the error"}, default=None
    )
    timestamp: datetime.datetime = field(
        metadata={"description": "The timestamp of the error"},
        default=datetime.datetime.now(),
    )
    exception: Optional[BaseException] = field(
        metadata={"description": "Original exception raised by the worker"},
        default=None,
    )
    exception_type: str = field(
        metadata={"description": "Qualified name of the original exception type"},
        default="",
    )
    origin: str = field(
        metadata={"description": "Async job name that produced this failure"},
        default="",
    )


def _job_error_from_exception(*, job_name: str, exc: Exception) -> JobError:
    """Build a :class:`JobError` that preserves the original exception and job origin."""
    return JobError(
        message=f"Job failed: {job_name}: {exc!s}",
        traceback=_traceback.format_exc(),
        return_code=getattr(exc, "returncode", None),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        exception=exc,
        exception_type=type(exc).__qualname__,
        origin=job_name,
    )


def _job_error_from_timeout(*, job_name: str, timeout: float) -> JobError:
    """Build a timeout failure that preserves origin and exception metadata."""
    exception = TimeoutError(f"Job timed out after {timeout:g} seconds")
    return JobError(
        message=f"Job timed out after {timeout:g} seconds: {job_name}",
        traceback="",
        return_code=None,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        exception=exception,
        exception_type=type(exception).__qualname__,
        origin=job_name,
    )


@dataclass(frozen=True)
class ProgressEvent:
    """
    Event of a job progress
    """

    value: Optional[float | int] = field(
        metadata={"description": "The value of the progress"}, default=None
    )
    message: Optional[str] = field(
        metadata={"description": "The message of the progress"}, default=None
    )
    metadata: Optional[dict[str, Any]] = field(
        metadata={"description": "The metadata of the progress"}, default=None
    )


@dataclass
class CancelToken:
    """
    Token to cancel a job execution
    """

    __slots__ = ("_cancelled",)

    def __init__(self):
        self._cancelled: bool = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def throw_if_cancelled(self) -> None:
        if self._cancelled:
            raise CancelledError("The job has been cancelled")


@dataclass
class JobSpecification:
    """
    Specification of a job execution
    """

    name: str = field(metadata={"description": "The name of the job"}, default="")
    description: str = field(
        metadata={"description": "The description of the job"}, default=""
    )
    fn: Callable[..., Any] | None = field(
        metadata={"description": "The function to execute"}, default=None
    )
    args: tuple[Any, ...] = field(
        metadata={"description": "The positional arguments to pass to the function"},
        default=(),
    )
    kwargs: dict[str, Any] = field(
        metadata={"description": "The keyworded arguments to pass to the function"},
        default_factory=dict,
    )
    timeout: float | None = field(
        metadata={"description": "The timeout of the job"}, default=None
    )
    priority: int = field(
        metadata={"description": "The priority of the job"}, default=0
    )
    coalesce_key: Optional[str] = field(
        metadata={"description": "The key to coalesce the job"}, default=None
    )  # Submitting a job while there is already one running with the same coalesce key will cancel the previous job (the job still run to completion, here "cancel" means that the result will be discarded)
    type: jobtype = field(
        metadata={"description": "The executor type of the job"}, kw_only=True
    )
    at_most_once: bool = field(
        metadata={"description": "At most one job running with the same coalesce key"},
        default=False,
    )
    preflight: jobpreflight | None = field(
        metadata={
            "description": "Optional gate evaluated before a worker is opened; "
            "False skips submission quietly"
        },
        default=None,
    )

    def __post_init__(self) -> None:
        if self.timeout is not None and (
            not math.isfinite(self.timeout) or self.timeout <= 0
        ):
            raise ValueError("Job timeout must be a positive finite number of seconds")


@dataclass(frozen=True)
class JobHandler:
    """
    Handler of a job execution (opaque reference for cancel and signal binding).
    """

    job_id: str = field(metadata={"description": "The id of the job"}, default="")
    name: str = field(metadata={"description": "The name of the job"}, default="")
    cancel_token: CancelToken = field(
        metadata={"description": "The token to cancel the job"},
        default_factory=CancelToken,
    )
    coalesce_key: str | None = field(
        metadata={"description": "The coalescing key owned by this job"},
        default=None,
    )


class JobHandlerSignals(QObject):
    """
    Signals of the job handler
    """

    Progress = Signal(ProgressEvent)
    Completed = Signal(object)
    Cancelled = Signal()
    Failed = Signal(JobError)


@dataclass(frozen=True, slots=True)
class _CompletedProposal:
    result: object


@dataclass(frozen=True, slots=True)
class _CancelledProposal:
    pass


@dataclass(frozen=True, slots=True)
class _FailedProposal:
    error: JobError


_TerminalProposal = _CompletedProposal | _CancelledProposal | _FailedProposal


def _observe_future(
    future: Future[Any],
    *,
    pool_name: str,
    job_id: str,
    job: JobSpecification,
    cancel_token: CancelToken,
    propose_terminal: Callable[[str, _TerminalProposal], None],
) -> None:
    """Emit exactly one terminal outcome, independently enforcing the deadline."""
    state_lock = Lock()
    terminal_emitted = False
    deadline_timer: Timer | None = None
    timeout = job.timeout

    def _claim_terminal() -> bool:
        nonlocal terminal_emitted
        with state_lock:
            if terminal_emitted:
                return False
            terminal_emitted = True
            timer = deadline_timer
        if timer is not None:
            timer.cancel()
        return True

    def _on_done(completed_future: Future[Any]) -> None:
        if not _claim_terminal():
            logger.debug(
                "Late async job result discarded",
                job_id=job_id,
                name=job.name,
                pool=pool_name,
            )
            return
        if cancel_token.is_cancelled():
            logger.debug(
                "Cancelled async job result discarded",
                job_id=job_id,
                name=job.name,
                pool=pool_name,
            )
            propose_terminal(job_id, _CancelledProposal())
            return
        try:
            result = completed_future.result()
        except Exception as error:
            propose_terminal(
                job_id,
                _FailedProposal(
                    _job_error_from_exception(job_name=job.name, exc=error)
                ),
            )
            return
        logger.debug(
            "Async job completed",
            job_id=job_id,
            name=job.name,
            pool=pool_name,
            result_type=type(result).__name__,
        )
        propose_terminal(job_id, _CompletedProposal(result))

    def _on_timeout() -> None:
        if timeout is None:
            return
        if not _claim_terminal():
            return
        future.cancel()
        if cancel_token.is_cancelled():
            logger.debug(
                "Cancelled async job reached its deadline",
                job_id=job_id,
                name=job.name,
                pool=pool_name,
                timeout_s=timeout,
            )
            propose_terminal(job_id, _CancelledProposal())
            return
        logger.warning(
            "Async job deadline exceeded",
            job_id=job_id,
            name=job.name,
            pool=pool_name,
            timeout_s=timeout,
        )
        propose_terminal(
            job_id,
            _FailedProposal(
                _job_error_from_timeout(job_name=job.name, timeout=timeout)
            ),
        )

    future.add_done_callback(_on_done)
    if timeout is None:
        return

    timer = Timer(timeout, _on_timeout)
    timer.daemon = True
    with state_lock:
        if terminal_emitted:
            return
        deadline_timer = timer
    timer.start()


class _ExecutorPool:
    """Shared executor submission, observation, and shutdown behavior."""

    __slots__ = ("_max_workers", "_executor")
    _display_name: ClassVar[str]
    _pool_name: ClassVar[str]

    def __init__(self, max_workers: Optional[int] = None) -> None:
        self._max_workers = max_workers
        try:
            self._executor = self._create_executor(max_workers)
        except (NotImplementedError, OSError, PermissionError) as e:
            logger.error(
                f"{self._display_name} pool initialization failed",
                error=e,
            )
            raise RuntimeError(
                f"Failed to initialize {self._pool_name} pool on this system"
            ) from e
        logger.debug(
            f"{self._display_name} pool initialized",
            max_workers=max_workers,
        )

    def _create_executor(self, max_workers: int | None) -> Executor:
        raise NotImplementedError

    def submit(
        self,
        job_id: str,
        job: JobSpecification,
        cancel_token: CancelToken,
        emit_progress: Callable[[str, ProgressEvent], None],
        propose_terminal: Callable[[str, _TerminalProposal], None],
    ) -> Future[Any]:
        """Submit work and attach the shared terminal observer."""
        if job.fn is None:
            raise ValueError("JobSpecification.fn must be set (callable)")
        fn = job.fn
        logger.debug(
            f"{self._display_name} job queued",
            job_id=job_id,
            name=job.name,
            timeout_s=job.timeout,
            fn=getattr(fn, "__qualname__", repr(fn)),
        )
        fut: Future[Any] = self._executor.submit(fn, *job.args, **job.kwargs)

        _observe_future(
            fut,
            pool_name=self._pool_name,
            job_id=job_id,
            job=job,
            cancel_token=cancel_token,
            propose_terminal=propose_terminal,
        )
        return fut

    def shutdown(self) -> None:
        """Request non-blocking executor shutdown and cancel queued work."""
        logger.debug(
            f"{self._display_name} pool shutdown requested",
            cancel_futures=True,
        )
        self._executor.shutdown(wait=False, cancel_futures=True)
        logger.debug(
            f"{self._display_name} pool shutdown completed",
            max_workers=self._max_workers,
        )


class ProcessPool(_ExecutorPool):
    """
    Process pool to execute jobs (CPU-heavy work, e.g. map creation).
    """

    __slots__ = ()
    _display_name = "Process"
    _pool_name = "process"

    def _create_executor(self, max_workers: int | None) -> Executor:
        worker_log_path = resolve_worker_application_log_file_path(process_id="{pid}")
        logger.debug(
            "Opening process pool",
            max_workers=max_workers,
            path=str(worker_log_path),
        )
        return ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=setup_worker_logger,
        )


class ThreadPool(_ExecutorPool):
    """Thread pool for I/O-bound or quick work."""

    __slots__ = ()
    _display_name = "Thread"
    _pool_name = "thread"

    def _create_executor(self, max_workers: int | None) -> Executor:
        return ThreadPoolExecutor(max_workers=max_workers)


class RunnerSignals(QObject):
    """
    Signals of the async runner
    """

    Progress = Signal(str, ProgressEvent)
    Completed = Signal(str, object)
    Cancelled = Signal(str)
    Failed = Signal(str, JobError)


class AsyncRunner(QObject):
    """
    Async runner to execute jobs (e.g. map creation). Dispatches to process or
    thread pool based on job specification; emits Qt signals on the main thread.
    """

    _progress_ready = Signal(str, ProgressEvent)
    _terminal_ready = Signal(str, object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._signals: RunnerSignals = RunnerSignals(self)
        try:
            self._thread_pool: ThreadPool = ThreadPool()
        except RuntimeError as e:
            logger.error(
                "Async runner thread pool initialization failed",
                error=e,
            )
            raise RuntimeError(
                "Failed to initialize async runner on this system"
            ) from e
        try:
            self._process_pool: _ExecutorPool = ProcessPool()
        except RuntimeError as e:
            logger.warning(
                "Process pool unavailable; process jobs will use the thread pool",
                error=e,
            )
            # Process pool unavailable; thread pool was initialized above.
            self._process_pool = ThreadPool()
        logger.debug(
            "Async runner initialized",
            process_pool=type(self._process_pool).__name__,
            thread_pool=type(self._thread_pool).__name__,
        )
        self.history: dict[str, tuple[JobHandler, JobHandlerSignals]] = {}
        self._coalesce_latest: dict[str, str] = {}
        self._progress_ready.connect(
            self._emit_progress_safe,
            Qt.ConnectionType.QueuedConnection,
        )
        self._terminal_ready.connect(
            self._commit_terminal,
            Qt.ConnectionType.QueuedConnection,
        )

    @property
    def signals(self) -> RunnerSignals:
        """Expose runner-level signals for connections."""
        return self._signals

    def submit(self, job: JobSpecification) -> JobHandler | None:
        """Validate, register, and dispatch a job, or return ``None`` if skipped."""
        if job.fn is None:
            raise ValueError("JobSpecification.fn must be set (callable)")
        if not self._passes_preflight(job):
            return None

        job_handler = self._register_job(job)
        if job_handler is None:
            return None

        self._dispatch(job.type, job, job_handler)
        return job_handler

    def _passes_preflight(self, job: JobSpecification) -> bool:
        """Return whether submission may proceed, logging an expected skip."""
        if job.preflight is None or job.preflight():
            return True
        logger.debug(
            "Async job submission skipped",
            name=job.name,
            coalesce_key=job.coalesce_key,
            job_type=job.type,
            reason="preflight",
        )
        return False

    def _register_job(self, job: JobSpecification) -> JobHandler | None:
        """Create a handle and reserve its active/coalescing state."""
        job_handler = JobHandler(
            job_id=uuid.uuid4().hex,
            name=job.name,
            cancel_token=CancelToken(),
            coalesce_key=job.coalesce_key,
        )
        if not self._reserve_coalescing_slot(job, job_handler):
            return None
        self.history[job_handler.job_id] = (job_handler, JobHandlerSignals())
        return job_handler

    def _reserve_coalescing_slot(
        self, job: JobSpecification, job_handler: JobHandler
    ) -> bool:
        """Apply at-most-once or latest-wins policy for a keyed job."""
        key = job.coalesce_key
        if key is None:
            return True

        latest_job_id = self._coalesce_latest.get(key)
        active_job_id = (
            latest_job_id
            if latest_job_id is not None and latest_job_id in self.history
            else None
        )
        if active_job_id is not None and job.at_most_once:
            logger.debug(
                "Async job submission skipped",
                coalesce_key=key,
                reason="at_most_once",
            )
            return False
        if active_job_id is not None:
            logger.debug(
                "Previous coalesced async job superseded",
                coalesce_key=key,
                previous_job_id=active_job_id,
                new_job_id=job_handler.job_id,
                name=job.name,
            )
            self.cancel(active_job_id)
        self._coalesce_latest[key] = job_handler.job_id
        return True

    def _dispatch(
        self,
        job_type: jobtype,
        job: JobSpecification,
        job_handler: JobHandler,
    ) -> None:
        """Send a registered job to its resolved executor pool."""
        logger.debug(
            "Async job submitted",
            job_id=job_handler.job_id,
            name=job.name,
            job_type=job_type,
            coalesce_key=job.coalesce_key,
        )
        pool = self._thread_pool if job_type == "thread" else self._process_pool
        pool.submit(
            job_handler.job_id,
            job,
            job_handler.cancel_token,
            self._marshal_progress,
            self._marshal_terminal,
        )

    def _marshal_progress(self, job_id: str, progress: ProgressEvent) -> None:
        self._progress_ready.emit(job_id, progress)

    def _marshal_terminal(self, job_id: str, proposal: _TerminalProposal) -> None:
        self._terminal_ready.emit(job_id, proposal)

    def shutdown(self) -> None:
        """Shutdown process and thread pools."""
        logger.info("Async runner shutdown started")
        self._process_pool.shutdown()
        self._thread_pool.shutdown()

    def cancel(self, job_id: str) -> None:
        """Mark job as cancelled (next completion callback will emit Cancelled)."""
        tup = self.history.get(job_id)
        if tup:
            logger.debug(
                "Async job cancellation requested",
                job_id=job_id,
                name=tup[0].name,
            )
            tup[0].cancel_token.cancel()
        else:
            logger.debug(
                "Async job cancellation ignored because the job is no longer active",
                job_id=job_id,
            )

    def bind_handle_signals(self, handle: JobHandler) -> JobHandlerSignals:
        """
        Return per-job signals for this handle. Use in controller:
        hs = runner.bind_handle_signals(handle); hs.Completed.connect(...)
        """
        return self.history[handle.job_id][1]

    def _emit_progress_safe(self, job_id: str, evt: ProgressEvent) -> None:
        """Emit progress on main thread (runner + handle signals)."""
        self._signals.Progress.emit(job_id, evt)
        tup = self.history.get(job_id)
        if tup:
            tup[1].Progress.emit(evt)

    def _commit_terminal(self, job_id: str, proposal: _TerminalProposal) -> None:
        """Commit one terminal outcome using the latest main-thread job state."""
        tup = self.history.get(job_id)
        if tup is None:
            logger.debug(
                "Late async terminal proposal discarded",
                job_id=job_id,
                proposal_type=type(proposal).__name__,
            )
            return

        handle, handle_signals = tup
        is_superseded = (
            handle.coalesce_key is not None
            and self._coalesce_latest.get(handle.coalesce_key) != job_id
        )
        if handle.cancel_token.is_cancelled() or is_superseded:
            proposal = _CancelledProposal()

        self._cleanup(handle)

        if isinstance(proposal, _CompletedProposal):
            logger.debug(
                "Async job completion emitted",
                job_id=job_id,
                name=handle.name,
                result_type=type(proposal.result).__name__,
            )
            self._signals.Completed.emit(job_id, proposal.result)
            handle_signals.Completed.emit(proposal.result)
            return

        if isinstance(proposal, _FailedProposal):
            error = proposal.error
            logger.error(
                "Async job failed",
                job_id=job_id,
                name=handle.name,
                message=error.message,
                return_code=error.return_code,
                traceback=error.traceback or None,
            )
            self._signals.Failed.emit(job_id, error)
            handle_signals.Failed.emit(error)
            return

        logger.debug(
            "Async job cancellation emitted",
            job_id=job_id,
            name=handle.name,
        )
        self._signals.Cancelled.emit(job_id)
        handle_signals.Cancelled.emit()

    def _cleanup(self, handle: JobHandler) -> None:
        """Remove a terminal job and its current coalescing entry."""
        job_id = handle.job_id
        self.history.pop(job_id, None)
        key = handle.coalesce_key
        if key is not None and self._coalesce_latest.get(key) == job_id:
            logger.debug(
                "Async job coalescing state cleared",
                job_id=job_id,
                coalesce_key=key,
            )
            del self._coalesce_latest[key]
        logger.debug("Async job history cleared", job_id=job_id)
