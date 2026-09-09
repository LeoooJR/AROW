"""ADB failure classification, retry policies, and Tenacity orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Final, Literal

from tenacity import (
    Retrying,
    retry_if_exception,
    retry_if_result,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
    wait_fixed,
)

from core.adb.command import (
    AdbCommandResult,
    AdbCommandResultStatus,
    AdbCommandSpec,
    AdbRetryPolicy,
    _redacted_log_value,
)
from core.adb.exceptions import AdbClientException, AdbServerException
from logger import logger

_RETRYABLE_ADB_MESSAGE_FRAGMENTS: Final[tuple[str, ...]] = (
    "protocol fault",
    "connection reset",
    "error: closed",
    "broken pipe",
    "connection refused",
    "cannot connect",
    "no connection could be made",
    "failed to connect",
    "device offline",
    "device not found",
    "daemon not running",
    "server version mismatch",
    "timed out",
    "timeout",
)

_PERMANENT_ADB_MESSAGE_FRAGMENTS: Final[tuple[str, ...]] = (
    "wrong pairing code",
    "wrong",
    "invalid",
    "failed to authenticate",
    "incorrect",
    "pairing code",
    "unauthorized",
    "permission denied",
    "insufficient permissions",
    "failed to run adb binary",
)

AdbRetryScope = Literal["client", "server"]
AdbAttempt = Callable[[float], AdbCommandResult]


@dataclass(frozen=True)
class _AdbRetryProfile:
    """Per-command Tenacity stop/wait boundaries and subprocess timeout."""

    stop: Any
    wait: Any
    timeout_seconds: float


def _message_is_retryable_adb_failure(message: str) -> bool:
    """True when ADB output points to a transient transport or daemon issue."""
    message = message.casefold()
    for fragment in _PERMANENT_ADB_MESSAGE_FRAGMENTS:
        if fragment in message:
            return False
    for fragment in _RETRYABLE_ADB_MESSAGE_FRAGMENTS:
        if fragment in message:
            return True
    return False


def _is_retryable_adb_exception(exc: BaseException) -> bool:
    """Return whether a translated ADB exception is likely transient."""
    if isinstance(exc, OSError):
        return False
    if not isinstance(exc, (AdbClientException, AdbServerException)):
        return False
    return _message_is_retryable_adb_failure(str(exc))


def adb_status_from_process(
    *, return_code: int, output: str = "", error: str = ""
) -> AdbCommandResultStatus:
    """Map a completed ADB process to its retry-aware result status."""
    if return_code == 0:
        return AdbCommandResultStatus.SUCCESS
    combined = f"{output}\n{error}".strip()
    if _message_is_retryable_adb_failure(combined):
        return AdbCommandResultStatus.TRANSIENT_ERROR
    return AdbCommandResultStatus.ERROR


def adb_status_from_timeout() -> AdbCommandResultStatus:
    """Return the explicit timeout result status."""
    return AdbCommandResultStatus.TIMEOUT


def _is_retryable_adb_result(result: AdbCommandResult) -> bool:
    """Return whether an ADB result should enter another retry attempt."""
    if result.status in (
        AdbCommandResultStatus.TIMEOUT,
        AdbCommandResultStatus.TRANSIENT_ERROR,
    ):
        return True
    if result.status != AdbCommandResultStatus.SUCCESS:
        return _message_is_retryable_adb_failure(f"{result.output}\n{result.error}")
    return False


def return_last_adb_retry_outcome(retry_state: Any) -> AdbCommandResult:
    """Return the final result while preserving exhausted exception behavior."""
    outcome = retry_state.outcome
    if outcome is None:
        raise RuntimeError("ADB retry finished without an outcome")
    if outcome.failed:
        raise outcome.exception()
    return outcome.result()


def _adb_failure_message(
    command: AdbCommandSpec[object], result: AdbCommandResult
) -> str:
    """Build one consistent exception message from a non-success result."""
    detail = (result.error or result.output or result.status.name).strip()
    return f"Failed to execute command: {command.argv}: {detail}"


def raise_client_for_result(
    command: AdbCommandSpec[object], result: AdbCommandResult
) -> None:
    """Raise the client exception for a non-success result."""
    if result.status != AdbCommandResultStatus.SUCCESS:
        raise AdbClientException(_adb_failure_message(command, result))


def raise_server_for_result(
    command: AdbCommandSpec[object], result: AdbCommandResult
) -> None:
    """Raise the server exception for a non-success result."""
    if result.status != AdbCommandResultStatus.SUCCESS:
        raise AdbServerException(_adb_failure_message(command, result))


def retry_profile_for(command: AdbCommandSpec[object]) -> _AdbRetryProfile:
    """Select the optimized retry boundaries for an ADB command."""
    if command.retry_policy is AdbRetryPolicy.PAIR:
        return _AdbRetryProfile(
            stop=stop_after_attempt(3) | stop_after_delay(8),
            wait=wait_exponential_jitter(initial=0.3, max=2.0, jitter=0.2),
            timeout_seconds=15.0,
        )
    if command.retry_policy is AdbRetryPolicy.KILL_SERVER:
        return _AdbRetryProfile(
            stop=stop_after_attempt(2) | stop_after_delay(3),
            wait=wait_fixed(0.5),
            timeout_seconds=5.0,
        )
    if command.retry_policy is AdbRetryPolicy.DAEMON:
        return _AdbRetryProfile(
            stop=stop_after_attempt(3) | stop_after_delay(5),
            wait=wait_exponential_jitter(initial=0.2, max=1.5, jitter=0.1),
            timeout_seconds=10.0,
        )
    if command.retry_policy is AdbRetryPolicy.CLIENT:
        return _AdbRetryProfile(
            stop=stop_after_attempt(2) | stop_after_delay(3),
            wait=wait_exponential_jitter(initial=0.15, max=1.0, jitter=0.1),
            timeout_seconds=8.0,
        )
    return _AdbRetryProfile(
        stop=stop_after_attempt(3) | stop_after_delay(5),
        wait=wait_exponential_jitter(initial=0.2, max=1.5, jitter=0.1),
        timeout_seconds=10.0,
    )


def timeout_seconds_for(command: AdbCommandSpec[object]) -> float:
    """Return the subprocess timeout without applying the command's retry policy."""
    return retry_profile_for(command).timeout_seconds


def _make_adb_retry_before(
    *,
    scope: AdbRetryScope,
    command_name: str,
    phone_id: str | None,
) -> Callable[[Any], None]:
    """Build the Tenacity callback that logs attempt starts."""

    def _before(retry_state: Any) -> None:
        elapsed = retry_state.seconds_since_start
        logger.debug(
            "ADB retry attempt started",
            scope=scope,
            command=command_name,
            phone_id=_redacted_log_value(phone_id),
            attempt=retry_state.attempt_number,
            elapsed_s=round(elapsed, 3) if elapsed is not None else 0.0,
        )

    return _before


def _make_adb_retry_after(
    *,
    scope: AdbRetryScope,
    command_name: str,
    phone_id: str | None,
) -> Callable[[Any], None]:
    """Build the Tenacity callback that logs attempt outcomes."""

    def _after(retry_state: Any) -> None:
        outcome = retry_state.outcome
        failed = outcome is not None and outcome.failed
        error = str(outcome.exception()) if failed else None
        result = None if outcome is None or failed else outcome.result()
        result_status = getattr(getattr(result, "status", None), "name", None)
        elapsed = retry_state.seconds_since_start
        logger.debug(
            "ADB retry attempt completed",
            scope=scope,
            command=command_name,
            phone_id=_redacted_log_value(phone_id),
            attempt=retry_state.attempt_number,
            elapsed_s=round(elapsed, 3) if elapsed is not None else 0.0,
            failed=failed,
            result_status=result_status,
            error=error,
        )

    return _after


def execute_with_adb_retry(
    command: AdbCommandSpec[object],
    *,
    scope: AdbRetryScope,
    phone_id: str | None,
    attempt: AdbAttempt,
) -> AdbCommandResult:
    """Execute an ADB attempt callable under the command's retry policy."""
    profile = retry_profile_for(command)
    retryer = Retrying(
        stop=profile.stop,
        wait=profile.wait,
        retry=retry_if_exception(_is_retryable_adb_exception)
        | retry_if_result(_is_retryable_adb_result),
        reraise=True,
        before=_make_adb_retry_before(
            scope=scope,
            command_name=command.argv[0],
            phone_id=phone_id,
        ),
        after=_make_adb_retry_after(
            scope=scope,
            command_name=command.argv[0],
            phone_id=phone_id,
        ),
        retry_error_callback=return_last_adb_retry_outcome,
    )
    return retryer(attempt, profile.timeout_seconds)
