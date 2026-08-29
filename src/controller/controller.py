from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from controller.cron import CronJob, CronManager
from controller.runner import (
    AsyncRunner,
    JobError,
    JobHandler,
    JobSpecification,
    ProgressEvent,
    jobtype,
)
from core.entrypoint import ModelEntrypoint
from gui.windows import MainWindow
from logger import logger


class Controller(ABC):
    """Controller for the application."""

    def __init__(
        self,
        model_entrypoint: ModelEntrypoint,
        view: MainWindow,
        *,
        runner: AsyncRunner | None = None,
        defer_signal_connect: bool = False,
    ) -> None:
        """Initialize the controller.

        Args:
            model_entrypoint: Core runtime entrypoint for the application.
            view: View for the application.
            runner: If provided, use this :class:`AsyncRunner` (e.g. single shared
                instance from the application controller). If omitted, create one.
            defer_signal_connect: If True, do not call ``_connect_view_signals`` /
                ``_connect_model_signals`` here so a subclass can construct child
                objects first, then call those hooks (see :class:`AppController`).
        """
        self._model_entrypoint: ModelEntrypoint = model_entrypoint
        self._view: MainWindow | None = view
        self._runner: AsyncRunner = runner if runner is not None else AsyncRunner(view)
        self._cron_manager = CronManager(self._submit_cron_job)
        if not defer_signal_connect:
            self._connect_view_signals()
            self._connect_model_signals()

    @abstractmethod
    def _connect_view_signals(self):
        """
        Connect view signals to controller methods
        """
        ...

    @abstractmethod
    def _connect_model_signals(self):
        """
        Connect model signals to controller methods
        """
        ...

    #### Getters / Setters ####

    @property
    def view(self) -> MainWindow:
        """Get the view for the application."""
        if self._view is None:
            raise RuntimeError("view is not available")
        return self._view

    @view.setter
    def view(self, view: MainWindow | None) -> None:
        """Set the view for the application."""
        self._view = view

    @property
    def model_entrypoint(self) -> ModelEntrypoint:
        """Get the core runtime entrypoint for the application."""
        return self._model_entrypoint

    @model_entrypoint.setter
    def model_entrypoint(self, model_entrypoint: ModelEntrypoint) -> None:
        """Set the core runtime entrypoint for the application."""
        self._model_entrypoint = model_entrypoint

    @property
    def runner(self) -> AsyncRunner:
        """Get the asynchronous runner for the application."""
        return self._runner

    @property
    def cron_manager(self) -> CronManager:
        """Get the recurring async job manager for the application."""
        return self._cron_manager

    def _submit_job_specification(
        self,
        specification: JobSpecification,
        *,
        on_completed: Callable[[Any], None] | None = None,
        on_failed: Callable[[Any], None] | None = None,
        on_cancelled: Callable[[], None] | None = None,
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> JobHandler | None:
        """Submit one specification and bind its main-thread lifecycle callbacks."""
        handle = self.runner.submit(specification)
        if handle is None:
            return None
        handle_signals = self.runner.bind_handle_signals(handle)

        if on_progress is not None:
            handle_signals.Progress.connect(on_progress)
        if on_completed is not None:
            handle_signals.Completed.connect(on_completed)
        if on_cancelled is not None:
            handle_signals.Cancelled.connect(on_cancelled)
        if on_failed is not None:
            handle_signals.Failed.connect(on_failed)

        logger.debug(
            "Model entrypoint job submitted",
            controller_type=type(self).__name__,
            model_entrypoint_type=type(self.model_entrypoint).__name__,
            job_id=handle.job_id,
            job_name=specification.name,
            job_type=specification.type,
            coalesce_key=specification.coalesce_key,
        )
        return handle

    def _submit_cron_job(self, job: CronJob) -> JobHandler | None:
        """Submit a recurring declaration through the shared async runner."""
        return self._submit_job_specification(
            job.specification,
            on_completed=job.on_completed,
            on_failed=job.on_failed,
            on_cancelled=job.on_cancelled,
            on_progress=job.on_progress,
        )

    def _submit_model_entrypoint_async_call(
        self,
        *,
        name: str,
        fn: Callable[..., Any],
        job_type: jobtype,
        description: str = "",
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        on_completed: Callable[[object], None] | None = None,
        on_failed: Callable[[JobError], None] | None = None,
        on_cancelled: Callable[[], None] | None = None,
        on_progress: Callable[[ProgressEvent], None] | None = None,
        timeout: float | None = None,
        priority: int = 0,
        coalesce_key: str | None = None,
        at_most_once: bool = False,
        preflight: Callable[[], bool] | None = None,
    ) -> JobHandler | None:
        """
        Submit a model-entrypoint async job and bind any provided callbacks.

        Completed callbacks are invoked by AsyncRunner on the Qt main thread,
        which makes this helper the standard entry point for future controller
        -> model entrypoint async orchestration.

        Args:
            name: Name of the job.
            fn: Function to execute.
            description: Description of the job.
            args: Arguments to pass to the function.
            kwargs: Keyword arguments to pass to the function.
            on_completed: Callback to execute when the job is completed.
            on_failed: Callback to execute when the job fails.
            on_cancelled: Callback to execute when the job is cancelled.
            on_progress: Callback to execute when the job progresses.
            job_type: Executor type of the job (thread or process).
            timeout: Timeout for the job.
            priority: Priority of the job (0-100).
            coalesce_key: Key to coalesce the job (none, location, network, device).
            at_most_once: At most one job running with the same coalesce key.
            preflight: Optional gate evaluated before a worker is opened; False skips
                submission quietly without job callbacks.
        Returns:
            JobHandler | None: JobHandler for the job. This can be used to cancel the job. None if the job was not submitted.
        """
        job = JobSpecification(
            name=name,
            description=description or name,
            fn=fn,
            args=args,
            kwargs={} if kwargs is None else kwargs,
            timeout=timeout,
            priority=priority,
            coalesce_key=coalesce_key,
            type=job_type,
            at_most_once=at_most_once,
            preflight=preflight,
        )
        return self._submit_job_specification(
            job,
            on_completed=on_completed,
            on_failed=on_failed,
            on_cancelled=on_cancelled,
            on_progress=on_progress,
        )
