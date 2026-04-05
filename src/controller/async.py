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
from PySide6.QtCore import QObject, QTimer, Signal

jobtype = Literal["auto", "thread", "process"]
jobstatus = Literal["pending", "running", "completed", "cancelled", "failed"]
jobpriority = Literal["low", "medium", "high"]
jobcoalescekey = Literal["none", "location", "network", "device"]
jobtimeout = Literal["none", "short", "medium", "long"]


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
    fn: Callable[..., Any] = field(
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
    )
    type: jobtype = field(
        metadata={"description": "The type of the job"}, default="auto"
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

    __slots__ = ("_executor",)

    def __init__(self, max_workers: Optional[int] = None) -> None:
        self._executor: ProcessPoolExecutor = ProcessPoolExecutor(
            max_workers=max_workers
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
        fut: Future[Any] = self._executor.submit(job.fn, *job.args, **job.kwargs)

        def _on_done(f: Future[Any]) -> None:
            if cancel_token.is_cancelled():
                emit_cancelled(job_id)
                return
            try:
                result = (
                    f.result(timeout=job.timeout)
                    if job.timeout is not None
                    else f.result()
                )
                emit_completed(job_id, result)
            except FuturesTimeoutError:
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
                    JobError(
                        message=f"Job failed: {job.name}: {e!s}",
                        traceback=_traceback.format_exc(),
                        return_code=getattr(e, "returncode", None),
                        timestamp=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )

        fut.add_done_callback(_on_done)
        return fut

    def shutdown(self) -> None:
        """
        Shutdown the process pool
        """
        self._executor.shutdown(wait=False, cancel_futures=True)


class ThreadPool:
    """
    Thread pool to execute jobs (I/O or quick tasks; same callback contract as ProcessPool).
    """

    __slots__ = ("_executor",)

    def __init__(self, max_workers: Optional[int] = None) -> None:
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=max_workers)

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
        fut: Future[Any] = self._executor.submit(job.fn, *job.args, **job.kwargs)

        def _on_done(f: Future[Any]) -> None:
            if cancel_token.is_cancelled():
                emit_cancelled(job_id)
                return
            try:
                result = (
                    f.result(timeout=job.timeout)
                    if job.timeout is not None
                    else f.result()
                )
                emit_completed(job_id, result)
            except FuturesTimeoutError:
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
                    JobError(
                        message=f"Job failed: {job.name}: {e!s}",
                        traceback=_traceback.format_exc(),
                        return_code=getattr(e, "returncode", None),
                        timestamp=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )

        fut.add_done_callback(_on_done)
        return fut

    def shutdown(self) -> None:
        """Shutdown the thread pool."""
        self._executor.shutdown(wait=False, cancel_futures=True)


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

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._signals: RunnerSignals = RunnerSignals(self)
        self._process_pool: ProcessPool = ProcessPool()
        self._thread_pool: ThreadPool = ThreadPool()
        self.history: dict[str, tuple[JobHandler, JobHandlerSignals]] = {}
        self._coalesce_latest: dict[str, str] = {}

    @property
    def signals(self) -> RunnerSignals:
        """Expose runner-level signals for connections."""
        return self._signals

    def submit(self, job: JobSpecification) -> JobHandler:
        """
        Submit a job to the async runner. Validates spec and dispatches to
        process or thread pool according to _resolve_job_type.
        """
        if job.fn is None:
            raise ValueError("JobSpecification.fn must be set (callable)")

        job_id: str = uuid.uuid4().hex
        cancel_token = CancelToken()
        job_handler = JobHandler(
            job_id=job_id, name=job.name, cancel_token=cancel_token
        )
        job_handler_signals = JobHandlerSignals()
        self.history[job_id] = (job_handler, job_handler_signals)

        if job.coalesce_key is not None:
            latest_job = self._coalesce_latest.get(job.coalesce_key)
            if latest_job and latest_job in self.history:
                self.cancel(latest_job)
            self._coalesce_latest[job.coalesce_key] = job_id

        def _marshal_progress(_job_id: str, _progress: ProgressEvent) -> None:
            QTimer.singleShot(0, lambda: self._emit_progress_safe(_job_id, _progress))

        def _marshal_completed(_job_id: str, _result: object) -> None:
            QTimer.singleShot(0, lambda: self._emit_completed_safe(_job_id, _result))

        def _marshal_cancelled(_job_id: str) -> None:
            QTimer.singleShot(0, lambda: self._emit_cancelled_safe(_job_id))

        def _marshal_failed(_job_id: str, _error: JobError) -> None:
            QTimer.singleShot(0, lambda: self._emit_failed_safe(_job_id, _error))

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
            tup[0].cancel_token.cancel()

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
        logger.debug("Async job completed", job_id=job_id)
        self._signals.Completed.emit(job_id, result)
        tup = self.history.get(job_id)
        if tup:
            tup[1].Completed.emit(result)
        self._cleanup(job_id)

    def _emit_cancelled_safe(self, job_id: str) -> None:
        """Emit cancelled on main thread and cleanup."""
        logger.debug("Async job cancelled", job_id=job_id)
        self._signals.Cancelled.emit(job_id)
        tup = self.history.get(job_id)
        if tup:
            tup[1].Cancelled.emit()
        self._cleanup(job_id)

    def _emit_failed_safe(self, job_id: str, error: JobError) -> None:
        """Emit failed on main thread and cleanup."""
        logger.error(
            "Async job failed",
            job_id=job_id,
            message=error.message,
            traceback=error.traceback,
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
                del self._coalesce_latest[key]
                break
