import datetime
import traceback as _traceback
import uuid
from concurrent.futures import (
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
)
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

from loguru import logger
from PySide6.QtCore import QObject, Qt, Signal

from logger import resolve_worker_application_log_file_path, setup_worker_logger

jobtype = Literal["auto", "thread", "process"]
jobstatus = Literal["pending", "running", "completed", "cancelled", "failed"]
jobpriority = Literal["low", "medium", "high"]
jobcoalescekey = Literal["none", "location", "network", "device"]
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
    timeout: Optional[int] = field(
        metadata={"description": "The timeout of the job"}, default=None
    )
    priority: int = field(
        metadata={"description": "The priority of the job"}, default=0
    )
    coalesce_key: Optional[str] = field(
        metadata={"description": "The key to coalesce the job"}, default=None
    )  # Submitting a job while there is already one running with the same coalesce key will cancel the previous job (the job still run to completion, here "cancel" means that the result will be discarded)
    type: jobtype = field(
        metadata={"description": "The type of the job"}, default="auto"
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


class JobHandlerSignals(QObject):
    """
    Signals of the job handler
    """

    Progress = Signal(ProgressEvent)
    Completed = Signal(object)
    Cancelled = Signal()
    Failed = Signal(JobError)


class ProcessPool:
    """
    Process pool to execute jobs (CPU-heavy work, e.g. map creation).
    """

    __slots__ = ("_max_workers", "_executor")

    def __init__(self, max_workers: Optional[int] = None) -> None:
        try:
            self._max_workers: int | None = max_workers
            worker_log_path = resolve_worker_application_log_file_path(
                process_id="{pid}"
            )
            logger.debug(
                "Opening process pool",
                max_workers=max_workers,
                path=str(worker_log_path),
            )
            self._executor: ProcessPoolExecutor = ProcessPoolExecutor(
                max_workers=max_workers,
                initializer=setup_worker_logger,
            )
        except (NotImplementedError, OSError, PermissionError) as e:
            logger.error(
                "Process pool initialization failed",
                error=e,
            )
            raise RuntimeError(
                "Failed to initialize process pool on this system"
            ) from e
        logger.debug(
            "Process pool initialized",
            max_workers=max_workers,
        )

    def submit(
        self,
        job_id: str,
        job: JobSpecification,
        cancel_token: CancelToken,
        emit_progress: Callable[[str, ProgressEvent], None],
        emit_completed: Callable[[str, object], None],
        emit_cancelled: Callable[[str], None],
        emit_failed: Callable[[str, JobError], None],
    ) -> Future[Any]:
        """
        Submit a job to the process pool. Callbacks run in the executor's thread;
        callers must marshal to the main thread if needed (e.g. for Qt signals).
        """
        if job.fn is None:
            raise ValueError("JobSpecification.fn must be set (callable)")
        fn = job.fn
        logger.debug(
            "Process job queued",
            job_id=job_id,
            name=job.name,
            timeout_s=job.timeout,
            fn=getattr(fn, "__qualname__", repr(fn)),
        )
        fut: Future[Any] = self._executor.submit(fn, *job.args, **job.kwargs)

        def _on_done(f: Future[Any]) -> None:
            if cancel_token.is_cancelled():
                logger.debug(
                    "Cancelled process job callback skipped",
                    job_id=job_id,
                    name=job.name,
                )
                emit_cancelled(job_id)
                return
            try:
                result = (
                    f.result(timeout=job.timeout)
                    if job.timeout is not None
                    else f.result()
                )
                logger.debug(
                    "Process job completed",
                    job_id=job_id,
                    name=job.name,
                    result_type=type(result).__name__,
                )
                emit_completed(job_id, result)
            except FuturesTimeoutError:
                logger.warning(
                    "Process job timed out while collecting its result",
                    job_id=job_id,
                    name=job.name,
                    timeout_s=job.timeout,
                )
                emit_failed(
                    job_id,
                    JobError(
                        message=f"Job timed out: {job.name}",
                        traceback="",
                        return_code=None,
                        timestamp=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )
            except Exception as e:
                emit_failed(
                    job_id,
                    _job_error_from_exception(job_name=job.name, exc=e),
                )

        fut.add_done_callback(_on_done)
        return fut

    def shutdown(self) -> None:
        """
        Shutdown the process pool
        """
        logger.debug("Process pool shutdown requested", cancel_futures=True)
        if self._executor is not None:  # check if the executor is initialized
            self._executor.shutdown(wait=False, cancel_futures=True)
        else:
            logger.debug("Process pool shutdown skipped because no executor exists")
        logger.debug(
            "Process pool shutdown completed",
            max_workers=self._max_workers,
        )


class ThreadPool:
    """
    Thread pool to execute jobs (I/O or quick tasks; same callback contract as ProcessPool).
    """

    __slots__ = ("_max_workers", "_executor")

    def __init__(self, max_workers: Optional[int] = None) -> None:
        try:
            self._max_workers: int | None = max_workers
            self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
                max_workers=max_workers
            )
        except (NotImplementedError, OSError, PermissionError) as e:
            logger.error(
                "Thread pool initialization failed",
                error=e,
            )
            raise RuntimeError("Failed to initialize thread pool on this system") from e
        logger.debug(
            "Thread pool initialized",
            max_workers=max_workers,
        )

    def submit(
        self,
        job_id: str,
        job: JobSpecification,
        cancel_token: CancelToken,
        emit_progress: Callable[[str, ProgressEvent], None],
        emit_completed: Callable[[str, object], None],
        emit_cancelled: Callable[[str], None],
        emit_failed: Callable[[str, JobError], None],
    ) -> Future[Any]:
        """
        Submit a job to the thread pool.
        """
        if job.fn is None:
            raise ValueError("JobSpecification.fn must be set (callable)")
        fn = job.fn
        logger.debug(
            "Thread job queued",
            job_id=job_id,
            name=job.name,
            timeout_s=job.timeout,
            fn=getattr(fn, "__qualname__", repr(fn)),
        )
        fut: Future[Any] = self._executor.submit(fn, *job.args, **job.kwargs)

        def _on_done(f: Future[Any]) -> None:
            if cancel_token.is_cancelled():
                logger.debug(
                    "Cancelled thread job callback skipped",
                    job_id=job_id,
                    name=job.name,
                )
                emit_cancelled(job_id)
                return
            try:
                result = (
                    f.result(timeout=job.timeout)
                    if job.timeout is not None
                    else f.result()
                )
                logger.debug(
                    "Thread job completed",
                    job_id=job_id,
                    name=job.name,
                    result_type=type(result).__name__,
                )
                emit_completed(job_id, result)
            except FuturesTimeoutError:
                logger.warning(
                    "Thread job timed out while collecting its result",
                    job_id=job_id,
                    name=job.name,
                    timeout_s=job.timeout,
                )
                emit_failed(
                    job_id,
                    JobError(
                        message=f"Job timed out: {job.name}",
                        traceback="",
                        return_code=None,
                        timestamp=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )
            except Exception as e:
                emit_failed(
                    job_id,
                    _job_error_from_exception(job_name=job.name, exc=e),
                )

        fut.add_done_callback(_on_done)
        return fut

    def shutdown(self) -> None:
        """Shutdown the thread pool."""
        logger.debug("Thread pool shutdown requested", cancel_futures=True)
        if self._executor is not None:  # check if the executor is initialized
            self._executor.shutdown(wait=False, cancel_futures=True)
        else:
            logger.debug("Thread pool shutdown skipped because no executor exists")
        logger.debug(
            "Thread pool shutdown completed",
            max_workers=self._max_workers,
        )


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
    _completed_ready = Signal(str, object)
    _cancelled_ready = Signal(str)
    _failed_ready = Signal(str, JobError)

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
            self._process_pool: ProcessPool | ThreadPool = ProcessPool()
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
        self._completed_ready.connect(
            self._emit_completed_safe,
            Qt.ConnectionType.QueuedConnection,
        )
        self._cancelled_ready.connect(
            self._emit_cancelled_safe,
            Qt.ConnectionType.QueuedConnection,
        )
        self._failed_ready.connect(
            self._emit_failed_safe,
            Qt.ConnectionType.QueuedConnection,
        )

    @property
    def signals(self) -> RunnerSignals:
        """Expose runner-level signals for connections."""
        return self._signals

    def submit(self, job: JobSpecification) -> JobHandler | None:
        """
        Submit a job to the async runner. Validates spec and dispatches to
        process or thread pool according to _resolve_job_type.
        Returns:
            JobHandler | None: JobHandler for the job. This can be used to cancel the job. None if the job was not submitted.
        """
        if job.fn is None:
            raise ValueError("JobSpecification.fn must be set (callable)")

        if job.preflight is not None and not job.preflight():
            logger.debug(
                "Async job submission skipped",
                name=job.name,
                coalesce_key=job.coalesce_key,
                job_type=job.type,
                reason="preflight",
            )
            return None

        job_id: str = uuid.uuid4().hex
        cancel_token = CancelToken()
        job_handler = JobHandler(
            job_id=job_id, name=job.name, cancel_token=cancel_token
        )
        job_handler_signals = JobHandlerSignals()

        if job.coalesce_key is not None:
            latest_job = self._coalesce_latest.get(job.coalesce_key)
            if latest_job and latest_job in self.history:
                # "At most one" coalescing
                if job.at_most_once:
                    logger.debug(
                        "Async job submission skipped",
                        coalesce_key=job.coalesce_key,
                        reason="at_most_once",
                    )
                    return None
                logger.debug(
                    "Previous coalesced async job superseded",
                    coalesce_key=job.coalesce_key,
                    previous_job_id=latest_job,
                    new_job_id=job_id,
                    name=job.name,
                )
                # "Latest wins" coalescing
                self.cancel(
                    latest_job
                )  # Cancel the previous job (emits Cancelled signal at the end of the job)
            self._coalesce_latest[job.coalesce_key] = (
                job_id  # Update the latest job id for this coalesce key
            )

        self.history[job_id] = (job_handler, job_handler_signals)

        def _marshal_progress(_job_id: str, _progress: ProgressEvent) -> None:
            self._progress_ready.emit(_job_id, _progress)

        def _marshal_completed(_job_id: str, _result: object) -> None:
            self._completed_ready.emit(_job_id, _result)

        def _marshal_cancelled(_job_id: str) -> None:
            self._cancelled_ready.emit(_job_id)

        def _marshal_failed(_job_id: str, _error: JobError) -> None:
            self._failed_ready.emit(_job_id, _error)

        job_type = self._resolve_job_type(job)
        logger.debug(
            "Async job submitted",
            job_id=job_id,
            name=job.name,
            job_type=job_type,
            coalesce_key=job.coalesce_key,
        )
        if job_type == "process":
            self._process_pool.submit(
                job_id,
                job,
                cancel_token,
                _marshal_progress,
                _marshal_completed,
                _marshal_cancelled,
                _marshal_failed,
            )
        elif job_type == "thread":
            self._thread_pool.submit(
                job_id,
                job,
                cancel_token,
                _marshal_progress,
                _marshal_completed,
                _marshal_cancelled,
                _marshal_failed,
            )
        else:
            raise ValueError(f"Invalid job type: {job_type}")

        return job_handler

    def shutdown(self) -> None:
        """Shutdown process and thread pools."""
        logger.info("Async runner shutdown started")
        self._process_pool.shutdown()
        self._thread_pool.shutdown()

    def _resolve_job_type(self, job_spec: JobSpecification) -> jobtype:
        """
        Resolve execution type from spec. When type is "auto", choose process vs
        thread from task semantics: map/network/heavy work -> process; location/
        device quick updates -> thread.
        """
        if job_spec.type == "thread":
            return "thread"
        if job_spec.type == "process":
            return "process"
        if job_spec.type == "auto":
            name_lower = (job_spec.name or "").lower()
            key = (job_spec.coalesce_key or "").lower()
            # Map creation and network-related work: CPU/heavy -> process
            if "map" in name_lower or key == "network" or key == "none":
                return "process"
            # Location/device updates: typically I/O or quick -> thread
            if key in ("location", "device"):
                return "thread"
            # Default: heavier work in process to keep UI responsive
            return "process"
        raise ValueError(f"Invalid job type: {job_spec.type!r}")

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

    def _emit_completed_safe(self, job_id: str, result: Any) -> None:
        """Emit completed on main thread and cleanup."""
        tup = self.history.get(job_id)
        job_name = tup[0].name if tup else ""
        logger.debug(
            "Async job completion emitted",
            job_id=job_id,
            name=job_name,
            result_type=type(result).__name__,
        )
        self._signals.Completed.emit(job_id, result)
        if tup:
            tup[1].Completed.emit(result)
        self._cleanup(job_id)

    def _emit_cancelled_safe(self, job_id: str) -> None:
        """Emit cancelled on main thread and cleanup."""
        tup = self.history.get(job_id)
        job_name = tup[0].name if tup else ""
        logger.debug(
            "Async job cancellation emitted",
            job_id=job_id,
            name=job_name,
        )
        self._signals.Cancelled.emit(job_id)
        if tup:
            tup[1].Cancelled.emit()
        self._cleanup(job_id)

    def _emit_failed_safe(self, job_id: str, error: JobError) -> None:
        """Emit failed on main thread and cleanup."""
        tup = self.history.get(job_id)
        job_name = tup[0].name if tup else ""
        logger.error(
            "Async job failed",
            job_id=job_id,
            name=job_name,
            message=error.message,
            return_code=error.return_code,
            traceback=error.traceback or None,
        )
        self._signals.Failed.emit(job_id, error)
        tup = self.history.get(job_id)
        if tup:
            tup[1].Failed.emit(error)
        self._cleanup(job_id)

    def _cleanup(self, job_id: str) -> None:
        """Remove job from history and from coalesce key if it is the latest."""
        self.history.pop(job_id, None)
        for key, latest_id in list(self._coalesce_latest.items()):
            if latest_id == job_id:
                logger.debug(
                    "Async job coalescing state cleared",
                    job_id=job_id,
                    coalesce_key=key,
                )
                del self._coalesce_latest[key]
                break
        logger.debug("Async job history cleared", job_id=job_id)
