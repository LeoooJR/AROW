"""
Shared main-thread failure helpers for :class:`~core.work.core_runtime_work.CoreRuntimeWork`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.signals import CoreSignal, ErrorRaisedPayload

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint


def emit_core_error_raised(
    model_entrypoint: ModelEntrypoint,
    *,
    source: str,
    message: str,
    error: BaseException | None = None,
) -> None:
    """Emit a recoverable domain error on the core signal bus (Qt main thread)."""
    payload_error = error if isinstance(error, Exception) else None
    model_entrypoint._signal_bus.emit(
        CoreSignal.ERROR_RAISED,
        ErrorRaisedPayload(source=source, message=message, error=payload_error),
    )
